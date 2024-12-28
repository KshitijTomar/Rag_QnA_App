import datetime
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from werkzeug.utils import secure_filename
import uuid
from minio.error import S3Error

from utils import database as db
from utils import create_embeddings

app = Flask(__name__)
CORS(app, origins=["http://localhost:5000"])


@app.route('/')
def index():
    return render_template('index.html')

# API to Upload file to minio and trigger RMQ for worker to handle
@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"message": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"message": "No selected file"}), 400

    file_name = secure_filename(file.filename)
    file_extension = file_name.split('.')[-1]

    try:
        db.minio_client.upload_file(file_name, file)

        mongo_doc = {
            "id": str(uuid.uuid4()),
            "file_name": file_name,
            "file_extension": file_extension,
            "created_at": datetime.datetime.utcnow(),
            "status": "uploaded"
        }
        db.mongo_client.insert_doc(mongo_doc)

        db.rmq_client.send_msg_mongo_doc(mongo_doc_id = mongo_doc["id"], status = "uploaded")

        return jsonify({"message": "File uploaded successfully!"})

    except S3Error as e:
        return jsonify({"message": f"Failed to upload file: {e.message}"}), 500

# API to get file status (mongo)
@app.route('/api/files', methods=['GET'])
def get_files():
    files = list(db.mongo_client.col.find({}, {"_id": 0}))
    return jsonify({"files": files})

# API for search query
@app.route('/api/search', methods=['POST'])
def search_query():
    query_msg = request.json.get("query_msg", "")

    if not query_msg:
        return jsonify({"error": "No query message provided"}), 400

    query_embedding = create_embeddings(query_msg)

    try:
        search_results = semantic_search(query_embedding)

        if search_results:
            results = [{
                "id": row[0], 
                "content": row[1], 
                "similarity": row[2], 
                "file_name": db.mongo_client.get_doc(row[0]).get('file_name')
                } for row in search_results]
            return jsonify({"response": results})

        else:
            return jsonify({"response": "No results found for the query."})

    except Exception as e:
        return jsonify({"error": f"Error occurred: {str(e)}"}), 500

# Function to perform semantic search using cosine similarity
def semantic_search(query_embedding):
    try:
        query_embedding_list = query_embedding.tolist()

        # Explicitly cast to array and use the pgvector syntax
        query_embedding_array = f'[{", ".join(map(str, query_embedding_list))}]'  
        
        # Perform a cosine similarity search using pgvector in Postgres
        db.postgres_client.execute("""
            SELECT mongo_doc_id, embedding, 1 - (embedding <=> %s::vector) AS cosine_similarity
            FROM embeddings
            ORDER BY cosine_similarity DESC LIMIT 5;
        """, (query_embedding_array,))

        results = db.postgres_client.cur.fetchall()
        return results

    except Exception as e:
        print(f"Error during semantic search: {e}")
        return []
    finally:
        db.postgres_client.cur_close()
    
if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
