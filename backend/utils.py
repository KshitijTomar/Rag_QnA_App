
import pymongo
import minio
import os
import psycopg2
import pika
import json
import fitz
from sentence_transformers import SentenceTransformer
from dotenv import dotenv_values
config = dotenv_values(".env")

embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

def create_embeddings(text):
    embeddings = embedding_model.encode(text)
    return embeddings

class MongoDB:
    conn = None
    db = None
    col = None
    def __init__(self):
        config = dotenv_values(".env")
        env_db=config.get("MONGO_DB")
        env_col=config.get("MONGO_COLLECTION")
        print(env_db)
        self.conn = pymongo.MongoClient(config.get("MONGO_URL"))
        self.db = self.conn[env_db]
        self.col= self.db[env_col]
        
    def get_doc(self, mongo_doc_id):
        return self.col.find_one({"id": mongo_doc_id})
    
    def insert_doc(self, mongo_doc):
        return self.col.insert_one(mongo_doc)
    
    def update_status(self, mongo_doc_id, status):
        self.col.update_one({"id": mongo_doc_id}, {"$set": {"status": status}})

class Minio:
    client = None
    bucket_name = None

    def __init__(self):
        config = dotenv_values(".env")
        self.bucket_name = config.get("MINIO_BUCKET_NAME")
        self.create_conn()
        self.check_bucket_n_create()

    def create_conn(self):
        config = dotenv_values(".env")
        self.client = minio.Minio(
            endpoint=config.get("MINIO_URL_PORT"),
            access_key=config.get("MINIO_ACCESS_KEY"),
            secret_key=config.get("MINIO_SECRET_KEY"),
            secure=False
        )
    
    def check_bucket_n_create(self):
        if not self.client.bucket_exists(self.bucket_name):
            self.client.make_bucket(self.bucket_name)
            print(f"Bucket '{self.bucket_name}' created successfully.")
    
    def upload_file(self, file_name, file):
        self.check_bucket_n_create()
        self.client.put_object(
            self.bucket_name, 
            file_name, 
            file, 
            length=-1, 
            part_size=10*1024*1024
        )

    def get_file(self, file_name):
        return self.client.get_object(self.bucket_name, file_name)
    
class Postgres:
    conn = None
    cur = None

    def __init__(self):
        self.create_conn_cur()

    def create_conn_cur(self):
        if not self.conn:
            self.create_conn()
        self.cur = self.conn.cursor()


    def create_conn(self):
        config = dotenv_values(".env")
        self.conn =  psycopg2.connect(
            user=config.get("POSTGRES_USER"),
            password=config.get("POSTGRES_PASSWORD"),
            host=config.get("POSTGRES_HOST"),
            port=config.get("POSTGRES_PORT"),
            database=config.get("POSTGRES_DB")
        )

    def execute(self, query, vars=None):
        self.create_conn_cur()
        self.cur.execute(query, vars)

    def execute_embed(self, query, vars=None):
        try:
            self.create_conn_cur()
            self.cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            self.cur.execute("""
                CREATE TABLE IF NOT EXISTS public.embeddings (
                    id SERIAL PRIMARY KEY,
                    mongo_doc_id UUID NOT NULL,
                    embedding vector(384)
                );
            """)
            self.cur.execute(query,vars)
            self.conn.commit()
            self.cur_close()
            return True
        except Exception as e:
            print(f"Error inserting embedding: {e}")
            if self.conn:
                self.conn.rollback()
            self.cur_close()
            return False
        
    def cur_close(self):
        if self.cur:
            self.cur.close()
        
    def conn_close(self):
        if self.conn:
            self.conn.close()

class RMQ:
    rabbitmq_host = None
    queue = None
    connection = None
    channel = None
    
    def __init__(self):
        config = dotenv_values(".env")
        self.rabbitmq_host = config.get("RMQ_HOST")
        self.queue = config.get("RMQ_QUEUE")
    
    def send_msg(self, message):
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host=self.rabbitmq_host))
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue=self.queue)

        # Send the message to the queue
        self.channel.basic_publish(
            exchange='',
            routing_key=self.queue,
            body=message
        )
        self.connection.close()
        return f"Message sent to RMQ: {message}"

    def send_msg_mongo_doc(self, mongo_doc_id, status):
        message = json.dumps({
            "mongo_doc_id": mongo_doc_id,
            "status": status
        })
        return self.send_msg(message)
    
    def rmq_start_listening(self, on_message_callback):
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host=self.rabbitmq_host))
        self.channel = self.connection.channel()
        self.channel.queue_declare(queue=self.queue)
        self.channel.basic_consume(queue=self.queue, on_message_callback=on_message_callback, auto_ack=True)
        print("Worker is waiting for messages.")
        self.channel.start_consuming()

class Database:
    mongo_client = None
    minio_client = None
    postgres_client = None
    rmq_client = None

    def __init__(self):
        self.mongo_client = MongoDB()
        self.minio_client = Minio()
        self.postgres_client = Postgres()
        self.rmq_client = RMQ()

database = Database()

#### PDF ######

# PDF Text Extraction
def extract_text_from_pdf(file_obj):
    pdf_file = fitz.open(stream=file_obj.read(), filetype="pdf")
    text = ""

    # Loop through each page of the PDF
    for page_num in range(pdf_file.page_count):
        page = pdf_file.load_page(page_num)
        text += page.get_text()

    return text