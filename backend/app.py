from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

from utils import get_answer_from_retrieved_documents, upload_file_to_mongo, getfiles

app = Flask(__name__)
CORS(app, origins=["http://localhost:5000"])

    
@app.route('/')
def index():
    return render_template('index.html')

# API to get file status (mongo)
@app.route('/api/files', methods=['GET'])
def get_files():
    files = getfiles()
    return jsonify({"files": files})


# API to Upload file to minio and trigger RMQ for worker to handle
@app.route('/api/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"message": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"message": "No selected file"}), 400

    file_name = file.filename
    file_extension = file_name.split('.')[-1]

    try:
        upload_file_to_mongo(file, file_name, file_extension)
        return jsonify({"message": "File uploaded successfully!"})
    except Exception as e:
        return jsonify({"message": f"Failed to upload file: {e.message}"}), 500



# API for search query
@app.route('/api/search', methods=['POST'])
def search_query():
    query_msg = request.json.get("query_msg", "")

    if not query_msg:
        return jsonify({"error": "No query message provided"}), 400

    try:
        result = get_answer_from_retrieved_documents(query_msg)
        
        return jsonify({
            "response": result['response'],
            "answer": result['answer'],
            "file_name": result['file_name']
        })
        
    except Exception as e:
        return jsonify({"error": f"Error occurred: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)
