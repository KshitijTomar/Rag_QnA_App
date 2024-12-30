from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

from utils import get_answer_from_retrieved_documents, upload_file_to_mongo, getfiles

app = Flask(__name__)
CORS(app, origins=["http://localhost:5000", "http://localhost:8000", "http://127.0.0.1:5000", "http://127.0.0.1:8000"])

    
@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    app.run(host='0.0.0.0')