from flask import Flask, render_template
from flask_cors import CORS
from dotenv import dotenv_values

app = Flask(__name__)
CORS(app, origins=["http://localhost:5000", "http://localhost:8000", "http://127.0.0.1:5000", "http://127.0.0.1:8000"])

    
@app.route('/')
def index():
    config = dotenv_values(".env")
    return render_template('index.html', base_url=config.get("API_URL","http://localhost:8000"))

if __name__ == '__main__':
    app.run(host='0.0.0.0')
