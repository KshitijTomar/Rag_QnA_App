import json
from minio.error import S3Error

from utils import database as db
from utils import extract_text_from_pdf, create_embeddings
from transformers import AutoTokenizer
tokenizer = AutoTokenizer.from_pretrained("bert-base-uncased")

def chunk_text(text, max_tokens=512):
    tokens = tokenizer.encode(text, add_special_tokens=False)
    for i in range(0, len(tokens), max_tokens):
        yield tokenizer.decode(tokens[i:i + max_tokens])

def callback(ch, method, properties, body):
    try:
        message = json.loads(body)
        
        if 'mongo_doc_id' in message:
            mongo_doc_id = message.get('mongo_doc_id')
            status = message.get('status')
        
            if mongo_doc_id is None:
                raise ValueError(f"Document with ID {mongo_doc_id} not found.")
            if status:
                if status != "uploaded":
                    raise ValueError(f"status is not 'uploaded'")
            
            mongo_doc = db.mongo_client.get_doc(mongo_doc_id)

            if not status:
                status = mongo_doc.get("status")
            file_name = mongo_doc.get("file_name")
            file_extension = mongo_doc.get("file_extension")

            if status != "uploaded":
                raise ValueError(f"status is not 'uploaded'")

            if not status:
                    raise ValueError(f"Status not found in MongoDB document with ID {mongo_doc_id}.")
            if not file_name:
                raise ValueError(f"File name not found in MongoDB document with ID {mongo_doc_id}.")
            
            file_obj = db.minio_client.get_file(file_name)
            
            if file_extension.lower() == "pdf":
                file_content = extract_text_from_pdf(file_obj)
            elif file_extension.lower() in ["txt", "csv", "xls", "xlsx"]:
                file_content = file_obj.read().decode("utf-8")
            else:
                raise ValueError("Unsupported file type for embedding.")
                                
            db.mongo_client.update_status(mongo_doc_id, status="embedding")

            for chunk_index, chunk in enumerate(chunk_text(file_content, max_tokens=100)):
                embedding = create_embeddings(chunk)
                db.postgres_client.execute_embed("INSERT INTO embeddings (mongo_doc_id, file_name, chunk_info, content, embedding) VALUES (%s, %s, %s, %s, %s)",(mongo_doc_id, f"{file_name}", f"_chunk_{chunk_index}", chunk, embedding.tolist()))
            
            db.mongo_client.update_status(mongo_doc_id, status="completed")

    except S3Error as e:
        print({"error": f"Failed to fetch file from MinIO: {e.message}"})
        db.mongo_client.update_status(mongo_doc_id, status="failed")
    except ValueError as e:
        print({"error": str(e)})
        db.mongo_client.update_status(mongo_doc_id, status="failed")
    except Exception as e:
        print({"error": f"An unexpected error occurred: {str(e)}"})
        db.mongo_client.update_status(mongo_doc_id, status="failed")

db.rmq_client.rmq_start_listening(on_message_callback=callback)
