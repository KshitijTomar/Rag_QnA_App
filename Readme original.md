# RAG-based Q&A Application with Document Management

## Introduction
This application manages users, documents, and ingestion processes while incorporating a Retrieval-Augmented Generation (RAG) system for Q&A. It includes a Python Fastapi backend for RAG functionality, a Python Flask frontend for document upload, RAG query entry with/without file selection. 

## Steps:
1. Git clone the project
2. Run commnad:  
    > docker-compose up -d
3. Wait for the setup to complete, might take 5 mins.
4. Open 
    > http://localhost:5000
5. Upload Rag Documents (Have added some sample documents in "test-data" folder)
6. Search for a result and the output will be visible in frontend. <br>For more response based info you can use fastapi docs ("/docs")


## Architecture Overview
![system_structure](https://static.pingcap.com/files/2024/06/04184615/image-4.png)

### Simple frontend
A simple HTML page with js (script section) to handle basic interactivity in same html and view results.
1. upload file:
    - file upload input box, to take file ask api to upload it to minio
    - list/table of uploaded file with its status
        - status = "failed/uploaded/embedding/completed"
    - a refresh button (rest call) to check mongo doc status of the file
2. a search query  with search button , on hit rest call to api to trigger rmq for search
3. a readable only textbox for the query response
4. a dropdown for file selection.

### Simple API
API should be able to handle Mongo doc creation and fetch
1. upload file by frontend: handle file upload to minio. file upload to minio needs to be mentioned into a new mongo doc.
2. rest call to get list/table of uploaded file with its status (limit 25) (refresh button)
3. search api rest call to trigger rmq for search for python worker to provide result, response will be the query result.
4. embedding api (or a sepearate worker that is connected to RabbitMQ) takes the minio uploaded file, divide text into chunks, embed chunks and save embeddings to a VectorDB (postgres here) for later query answer generator.

### Worker
To handle the potentially large volume of data as outlined in the assignment document, I have implemented a dedicated Python worker. The worker operates on an MQTT-based queue system to ensure efficient processing while remaining decoupled from the API. The workflow is as follows:

1. Trigger and Initial Setup:
    - Upon file upload, the API triggers the initial queue.
    - The file's status in MongoDB is updated to "uploaded."
2. Worker Processing:
    - The Python worker retrieves the file from MinIO as specified in the corresponding MongoDB document.
    - The file is processed through the following steps:
        - Data Chunking: The file is divided into manageable chunks.
        - Embedding Generation: Each chunk is converted into embeddings.
        - Database Storage: The embeddings are stored in the PostgreSQL database.
3. Status Updates:
    - Once processing is successfully completed, the status in MongoDB is updated to "completed."
    - If any exceptions occur during processing, the status is updated to "failed," ensuring transparency and error tracking.

## Flow file upload and embedding gen and storage:

1. file uploaded on frontend
2. (API) file moved to minio 
    - bucket:"py-rag-input-files"
    - file name: "(file_name).(extension)"
3. (API) mongo entry created in db "py-rag" collection "input":
    - status = "failed/uploaded/embedding/completed"
    ```JSON
    {
        id: _uuid,
        file_name: "(file_name).(extension)",
        file_extension: "(extension)",
        file_type: "text/txt/pdf/excel/csv",
        created_at: "(date_and_time)",
        status: "uploaded",
    }
    ```
4. (API) RMQ generated for python worker to pick: 
    - required fields: mongo_doc_id, status of mongo_doc
5. (Python-RAG) 
    - pick RMQ if any
    - if status=="uploaded"
        - fetch file from minio bucket "py-rag-input-files"
        - create embeddings in chunks
        - change mongo_doc status to "embedding"
        - store embeddings to postgres db "py-rag" table "embeddings"
            - should link with mongo_doc of db "py-rag" collection "input"
        - change mongo_doc status to "completed"
        - if fails, change mongo_doc status to "failed"
    - if status=="failed", try embedding again once


## Flow QnA:

1. (API) send RMQ with query_msg to queue "py-rag-query"
2. (API) mongo entry created "py-rag-query":
    {
        id: _uuid,
        query_msg: "",
        created_at: _date_and_time,
        response: ""
    }
3. (Python-RAG) 
    - takes query_msg from RMQ
    - sementic search to get response
    - give one proper response
    - also give other top 5 hits
4. Answer generation from a selected file
    - populate list of files, for user to select, and query with file_name

## Explaining Text Embedding and Summarization:

### SentenceTransformer for Text Embedding
*Library:* sentence_transformers <br>
*Model:* all-MiniLM-L6-v2 <br>
This is a lightweight and efficient model from the Sentence Transformers library.It generates dense vector embeddings for input text, suitable for tasks like semantic similarity, clustering, or search.

### BART for Text Summarization
*Library:* transformers (Hugging Face)<br>
*Tokenizer:* BartTokenizer<br>
Converts text into tokens that can be understood by the BART model.



## References:
- https://dev.to/stephenc222/how-to-use-postgresql-to-store-and-query-vector-embeddings-h4b
- https://github.com/pgvector/pgvector
- https://github.com/ShawhinT/YouTube-Blog/blob/main/LLMs/text-embeddings/2-semantic-search.ipynb
- https://www.sbert.net/docs/sentence_transformer/pretrained_models.html
- https://colab.research.google.com/gist/alejandro-ao/47db0b8b9d00b10a96ab42dd59d90b86/langchain-multimodal.ipynb#scrollTo=22c22e3f-42fb-4a4a-a87a-89f10ba8ab99
- https://www.youtube.com/watch?v=pIGRwMjhMaQ&ab_channel=MervinPraison
- https://stackoverflow.com/questions/77205123/how-do-i-slim-down-sberts-sentencer-transformer-library