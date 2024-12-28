FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./requirements.txt
RUN pip install -r requirements.txt
COPY templates ./templates
COPY app.py ./app.py
COPY worker.py ./worker.py
COPY utils.py ./utils.py
COPY .env_docker ./.env
EXPOSE 5000