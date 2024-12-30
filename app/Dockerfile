FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./requirements.txt
RUN pip install -r requirements.txt
COPY templates ./templates
COPY flask_app.py ./flask_app.py
COPY fastapi_app.py ./fastapi_app.py
COPY worker.py ./worker.py
COPY utils.py ./utils.py
COPY .env_docker ./.env