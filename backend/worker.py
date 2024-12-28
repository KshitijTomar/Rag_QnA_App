import pika
import json
import os
from minio import Minio
from minio.error import S3Error
import psycopg2
from sentence_transformers import SentenceTransformer
from pymongo import MongoClient
import uuid
import fitz

# Setup MongoDB, MinIO, PostgreSQL, and RabbitMQ
client = MongoClient('mongodb://localhost:27017')
db = client['py-rag']
input_collection = db['input']

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

embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

connection = pika.BlockingConnection(pika.ConnectionParameters('localhost'))
channel = connection.channel()
channel.queue_declare(queue='py-rag-query')

def callback(ch, method, properties, body):
    message = json.loads(body)
    
    if 'mongo_doc_id' in message:
        mongo_doc_id = message['mongo_doc_id']
        status = message['status']
        
        if status == "uploaded":
            # Fetch file from MinIO

            try:
                mongo_doc = input_collection.find_one({"id": mongo_doc_id})
                if mongo_doc is None:
                    raise ValueError(f"Document with ID {mongo_doc_id} not found.")
                
                # Get the file_name from the MongoDB document
                file_name = mongo_doc.get("file_name")
                file_extension = mongo_doc.get("file_extension")

                if not file_name:
                    raise ValueError(f"File name not found in MongoDB document with ID {mongo_doc_id}.")
                
                file_obj = minio_client.get_object("py-rag-input-files", file_name)
                
                if file_extension.lower() == "pdf":
                    # If it's a PDF, extract the text from the PDF file
                    file_content = extract_text_from_pdf(file_obj)
                elif file_extension.lower() in ["txt", "csv", "excel"]:
                    # If it's a text, CSV, or Excel file, directly read the content
                    file_content = file_obj.read().decode("utf-8")
                else:
                    raise ValueError("Unsupported file type for embedding.")
                                    
                # Start embedding process
                embeddings = create_embeddings(file_content)
                
                # Update MongoDB status
                input_collection.update_one({"id": mongo_doc_id}, {"$set": {"status": "embedding"}})
                
                try:
                    # Store embeddings in PostgreSQL (pgvector)
                    cursor = pg_conn.cursor()

                    # Create embeddings table if it doesn't exist
                    
                    cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
                    cursor.execute("""
                        CREATE TABLE IF NOT EXISTS public.embeddings (
                            id SERIAL PRIMARY KEY,
                            mongo_doc_id UUID NOT NULL,
                            embedding vector(384)
                        );
                    """)
                    cursor.execute("INSERT INTO embeddings (mongo_doc_id, embedding) VALUES (%s, %s)",
                                (mongo_doc_id, embeddings.tolist()))
                    pg_conn.commit()
                    
                    input_collection.update_one({"id": mongo_doc_id}, {"$set": {"status": "completed"}})
                except Exception as e:
                    # Rollback the transaction in case of error
                    if pg_conn:
                        pg_conn.rollback()
                    print(f"Error inserting embedding: {e}")
                    input_collection.update_one({"id": mongo_doc_id}, {"$set": {"status": "failed"}})

                finally:
                    # Close cursor and connection
                    if cursor:
                        cursor.close()
                
                # Update MongoDB to 'completed'

            except S3Error as e:
                # Handle any S3-related errors
                print({"error": f"Failed to fetch file from MinIO: {e.message}"})
            except ValueError as e:
                # Handle custom errors (like document or file name not found)
                print({"error": str(e)})
            except Exception as e:
                # Handle other unexpected errors
                print({"error": f"An unexpected error occurred: {str(e)}"})
    elif 'query_msg' in message:
        query_msg = message['query_msg']
        # Perform semantic search here and get response (dummy)
        response = f"Top result for query: {query_msg}"
        
        # Update query response in MongoDB
        query_id = message["query_id"]
        db["queries"].update_one({"id": query_id}, {"$set": {"response": response}})


# PDF Text Extraction Function using PyMuPDF
def extract_text_from_pdf(file_obj):
    # Open the PDF file using PyMuPDF (fitz)
    pdf_file = fitz.open(stream=file_obj.read(), filetype="pdf")
    text = ""

    # Loop through each page of the PDF
    for page_num in range(pdf_file.page_count):
        page = pdf_file.load_page(page_num)
        text += page.get_text()

    return text


# Embedding Creation Function
def create_embeddings(text):
    embeddings = embedding_model.encode(text)
    return embeddings


channel.basic_consume(queue='py-rag-query', on_message_callback=callback, auto_ack=True)

print("Worker is waiting for messages.")
channel.start_consuming()
