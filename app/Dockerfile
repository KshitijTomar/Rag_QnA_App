FROM python:3.11.2-slim-bullseye
WORKDIR /app
RUN pip install --upgrade pip
RUN pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
RUN pip install sentence-transformers
COPY requirements.txt ./requirements.txt
RUN pip install -r requirements.txt
COPY templates ./templates
COPY flask_app.py ./flask_app.py
COPY fastapi_app.py ./fastapi_app.py
COPY worker.py ./worker.py
COPY utils.py ./utils.py
COPY .env_docker ./.env