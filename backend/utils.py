
import os
import pymongo
import minio
from minio.error import S3Error
import psycopg2
import pika
import json
import fitz
import uuid
import datetime
from dotenv import dotenv_values
config = dotenv_values(".env")

from sentence_transformers import SentenceTransformer
from transformers import BartForConditionalGeneration, BartTokenizer

########### Processings ############

embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
tokenizer = BartTokenizer.from_pretrained("facebook/bart-large-cnn")
generator_model = BartForConditionalGeneration.from_pretrained("facebook/bart-large-cnn")


def get_answer_from_retrieved_documents(query_msg):
    try:
        query_embedding = create_embeddings(query_msg)
        search_results = semantic_search(query_embedding)

        final_results = process_search_results(search_results)
        if final_results:
            most_similar_file = max(final_results.items(), key=lambda x: x[1]["similarity_score"])
            context = most_similar_file[1]["content"]
            # context = " ".join([row[4] for row in search_results])
            # context = search_results[0][4]
            # context = " ".join([row[4] for row in search_results])
            if not context.strip():
                
                return {
                    "response": [],
                    "answer": "Relevant documents found but no readable content available.",
                    "file_name": ""
                }
            
            # Concatenate the query and the retrieved documents to form the input for the generator
            input_text = f"Query: {query_msg}; Context: {context}"

            # Tokenize the input text for the generator
            inputs = tokenizer(input_text, return_tensors="pt", truncation=True, padding=True, max_length=1024)

            # Generate an answer using the generator model
            outputs = generator_model.generate(inputs['input_ids'], max_length=200, num_beams=4, early_stopping=True)
            
            # Decode and return the answer
            answer = tokenizer.decode(outputs[0], skip_special_tokens=True)
            
            # Format the results for API response
            results = [{"similarity": row[2], "chunk_info":row[5], "file_name": database.mongo_client.get_doc(row[0]).get('file_name')} for row in search_results]
            
            return {
                "response": results,
                "answer": answer,
                "file_name": most_similar_file[0]
            }
        else:
            return {
                "response": [],
                "answer": "No relevant documents found.",
                "file_name": ""
            }
    except Exception as e:
        raise Exception(e)
    
def process_search_results(search_result):
    grouped_results = {}

    for doc_id, embedding, similarity, file_name, content, chunk_info in search_result:
        chunk_order = int(chunk_info.split("_chunk_")[1])
        if file_name not in grouped_results:
            grouped_results[file_name] = {"chunks": {}}
        grouped_results[file_name]["chunks"][chunk_order] = (content, similarity)

    final_result = {}
    for file_name, data in grouped_results.items():
        sorted_chunks = sorted(data["chunks"].items())
        merged_content = " ".join(chunk[1][0] for chunk in sorted_chunks)
        average_similarity = sum(chunk[1][1] for chunk in sorted_chunks) / len(sorted_chunks)

        final_result[file_name] = {
            "content": merged_content,
            "similarity_score": average_similarity
        }

    return final_result

def create_embeddings(text):
    embeddings = embedding_model.encode(text)
    return embeddings

# Function to perform semantic search using cosine similarity
def semantic_search(query_embedding):
    try:
        query_embedding_list = query_embedding.tolist()

        # Explicitly cast to array and use the pgvector syntax
        query_embedding_array = f'[{", ".join(map(str, query_embedding_list))}]'  
        
        # Perform a cosine similarity search using pgvector in Postgres
        database.postgres_client.execute("""
            SELECT mongo_doc_id, embedding, 1 - (embedding <=> %s::vector) AS cosine_similarity, file_name, content, chunk_info
            FROM embeddings
            ORDER BY cosine_similarity DESC LIMIT 10;
        """, (query_embedding_array,))

        results = database.postgres_client.cur.fetchall()
        return results

    except Exception as e:
        print(f"Error during semantic search: {e}")
        return []
    finally:
        database.postgres_client.cur_close()



################ DB ##################
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
    
    def get_list_files(self, limit=None):
        if limit:
            files_list = list(self.col.find({}, {"_id": 0}).limit(limit))
        else:
            files_list = list(self.col.find({}, {"_id": 0}))
        return files_list
    
    def insert_doc(self, mongo_doc):
        return self.col.insert_one(mongo_doc)
    
    def update_status(self, mongo_doc_id, status):
        self.col.update_one({"id": mongo_doc_id}, {"$set": {"status": status}})

    def file_uploaded(self, file_name, file_extension):
        mongo_doc = {
            "id": str(uuid.uuid4()),
            "file_name": file_name,
            "file_extension": file_extension,
            "created_at": datetime.datetime.utcnow(),
            "status": "uploaded"
        }
        self.insert_doc(mongo_doc)
        return mongo_doc

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
                    mongo_doc_id VARCHAR(40) NOT NULL,
                    file_name VARCHAR(512) NOT NULL,
                    chunk_info VARCHAR(512) NOT NULL,
                    content VARCHAR(2048) NOT NULL,
                    embedding VECTOR(384)
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
            raise Exception(e)
        
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

def upload_file_to_mongo(file, file_name, file_extension):
    try:
        database.minio_client.upload_file(file_name, file)
        mongo_doc = database.mongo_client.file_uploaded(file_name, file_extension)
        database.rmq_client.send_msg_mongo_doc(mongo_doc_id = mongo_doc["id"], status = "uploaded")
    except S3Error as e:
        print("Error: Minio file upload issue")
        raise Exception(e)
    except Exception as e:
        raise Exception(e)

def getfiles():
    files = database.mongo_client.get_list_files(limit=10)
    return files


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