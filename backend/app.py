import datetime
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
import uuid
from pymongo import MongoClient
from minio import Minio
import json
from minio.error import S3Error
import pika

from sentence_transformers import SentenceTransformer
import psycopg2
import numpy as np

app = Flask(__name__)

# Enable CORS for all routes
CORS(app, origins=["http://localhost:5000"])

# MongoDB setup
client = MongoClient('mongodb://localhost:27017/')
db = client['py-rag']
input_collection = db['input']
def get_mongo_doc(mongo_doc_id):
    return input_collection.find_one({"id": mongo_doc_id})

embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

# Embedding Creation Function
def create_embeddings(text):
    embeddings = embedding_model.encode(text)
    return embeddings

# MinIO setup
minio_client = Minio(
    "localhost:9000", 
    access_key="minio", 
    secret_key="minio123", 
    secure=False
)

pg_conn = psycopg2.connect(
    dbname="py-rag",
    user="user",
    password="password",
    host="localhost",
    port="5432"
)
# RabbitMQ setup
rabbitmq_host = 'localhost'
queue_name = 'py-rag-query'

# File upload configuration
UPLOAD_FOLDER = 'uploads/'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER



def send_rmq_message(mongo_doc_id, status):
    try:
        # Establish a connection to RabbitMQ
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=rabbitmq_host))
        channel = connection.channel()

        # Declare the queue (if not already declared)
        channel.queue_declare(queue=queue_name)

        # Create the message
        message = json.dumps({
            "mongo_doc_id": mongo_doc_id,
            "status": status
        })

        # Send the message to the queue
        channel.basic_publish(
            exchange='',
            routing_key=queue_name,
            body=message
        )
        print(f"Message sent to RMQ: {message}")
        connection.close()
    
    except Exception as e:
        print(f"Failed to send message to RMQ: {e}")

# Serve the index.html template
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"message": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"message": "No selected file"}), 400

    file_name = secure_filename(file.filename)
    file_extension = file_name.split('.')[-1]

    # Define the bucket name
    bucket_name = "py-rag-input-files"

    try:
        # Check if the bucket exists
        if not minio_client.bucket_exists(bucket_name):
            # If bucket doesn't exist, create it
            minio_client.make_bucket(bucket_name)
            print(f"Bucket '{bucket_name}' created successfully.")

        # Upload to MinIO
        minio_client.put_object(
            bucket_name, 
            file_name, 
            file, 
            length=-1, 
            part_size=10*1024*1024
        )

        # Create MongoDB entry
        mongo_doc = {
            "id": str(uuid.uuid4()),
            "file_name": file_name,
            "file_extension": file_extension,
            "created_at": datetime.datetime.utcnow(),  # You can use datetime for timestamp
            "status": "uploaded"
        }
        input_collection.insert_one(mongo_doc)

        # Send RMQ message with the created mongo_doc_id and status
        send_rmq_message(mongo_doc["id"], "uploaded")

        return jsonify({"message": "File uploaded successfully!"})

    except S3Error as e:
        # Handle any S3 error
        return jsonify({"message": f"Failed to upload file: {e.message}"}), 500

# API to get file status
@app.route('/api/files', methods=['GET'])
def get_files():
    files = list(input_collection.find({}, {"_id": 0}))
    return jsonify({"files": files})

# API for search query
@app.route('/api/search', methods=['POST'])
def search_query():
    query_data = request.json
    query_msg = query_data.get("query_msg", "")

    if not query_msg:
        return jsonify({"error": "No query message provided"}), 400

    # Generate embedding for the query message
    query_embedding = create_embeddings(query_msg)

    # Connect to PostgreSQL (replace with your actual credentials)
    try:
        # Perform the semantic search
        search_results = semantic_search(query_embedding, pg_conn)

        if search_results:
            # Format the results as JSON
            results = [{"id": row[0], "content": row[1], "similarity": row[2], "file_name": get_mongo_doc(row[0]).get('file_name')} for row in search_results]
            return jsonify({"response": results})

        else:
            return jsonify({"response": "No results found for the query."})

    except Exception as e:
        return jsonify({"error": f"Error occurred: {str(e)}"}), 500

# Function to perform semantic search using cosine similarity
def semantic_search(query_embedding, pg_conn):
    try:
        
        if not pg_conn:
            pg_conn = psycopg2.connect(
                dbname="py-rag",
                user="user",
                password="password",
                host="localhost",
                port="5432"
            )
        cur = pg_conn.cursor()
        query_embedding_list = query_embedding.tolist()
        # Explicitly cast to array and use the pgvector syntax
        query_embedding_array = f'[{", ".join(map(str, query_embedding_list))}]'  # Convert list to PostgreSQL array format
        
        # Perform a cosine similarity search using pgvector in Postgres
        cur.execute("""
            SELECT mongo_doc_id, embedding, 1 - (embedding <=> %s::vector) AS cosine_similarity
            FROM embeddings
            ORDER BY cosine_similarity DESC LIMIT 5;
        """, (query_embedding_array,))

        # Fetch and print the results
        results = cur.fetchall()
        return results

    except Exception as e:
        print(f"Error during semantic search: {e}")
        return []
    finally:
        if cur:
            cur.close()
    
if __name__ == '__main__':
    app.run(debug=True)
