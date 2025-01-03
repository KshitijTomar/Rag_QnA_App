# RAG-based Q&A Application with Document Management

**Creator:** Kshitij Tomar
**EMAIL:** kshtjtomar40@gmail.com
**Phone:** +91-9891562247

## Introduction
This application manages users, documents, and ingestion processes while incorporating a **Retrieval-Augmented Generation (RAG)** system for Q&A. It includes:
1. **Python FastAPI backend** for RAG functionality.
2. **Python Flask frontend** for document upload and query handling (with/without file selection).

---

## Setup Instructions
1. Clone the repository:
    ```bash
    git clone <repository_url>
    ```
2. Start the application using:
    ```bash
    docker-compose up -d
    ```
3. Wait approximately 5 minutes for the setup to complete.
4. Access the application at:
    ```
    http://localhost:5000
    ```
5. Upload RAG documents (sample documents available in the `test-data` folder).
6. Use the search functionality to query data. Results will be displayed on the frontend.  
   For detailed responses, explore the FastAPI documentation at `/docs`.

---

## Architecture Overview

![System Architecture](https://static.pingcap.com/files/2024/06/04184615/image-4.png)

### Frontend Features
A simple HTML page with JavaScript (in-script section) provides basic interactivity:
1. **File Upload**:
    - Input box to upload files, which are sent to MinIO via API.
    - Displays a list/table of uploaded files with their statuses:
        - `failed`, `uploaded`, `embedding`, or `completed`.
    - Includes a refresh button to fetch the latest status from MongoDB.
2. **Search Query**:
    - Input box for entering search queries.
    - Dropdown for selecting specific files (optional).
    - Search button triggers a REST API call to RabbitMQ for processing.
3. **Query Response Display**:
    - Read-only text box to display the query results.

---

### Backend API
The API handles MongoDB document creation, file uploads, and querying:
1. **File Upload**:
    - Uploads files to MinIO.
    - Creates an entry in MongoDB for the file.
2. **File Status**:
    - Retrieves a list of uploaded files with their statuses (limit: 25).
3. **Search API**:
    - Sends a search query to RabbitMQ for processing.
    - Returns the generated response.
4. **Embedding API**:
    - Processes files from MinIO:
        - Chunks text.
        - Generates embeddings.
        - Stores embeddings in PostgreSQL.
        - Updates MongoDB status.

---

## Workflow

### File Upload and Embedding Generation
1. **Frontend**:
    - Uploads the file.
2. **API**:
    - Moves the file to MinIO (bucket: `py-rag-input-files`).
    - Creates a MongoDB entry in the `py-rag` database, `input` collection:
        ```json
        {
            "id": "uuid",
            "file_name": "example.txt",
            "file_extension": "txt",
            "file_type": "text",
            "created_at": "date_and_time",
            "status": "uploaded"
        }
        ```
3. **RabbitMQ**:
    - Sends a message with `mongo_doc_id` and status to the queue.
4. **Python Worker**:
    - Processes the file:
        - Fetches it from MinIO.
        - Creates embeddings.
        - Stores embeddings in PostgreSQL (`py-rag.embeddings` table).
        - Updates MongoDB status to `completed` or `failed`.

### Q&A Workflow
1. **API**:
    - Sends a query message to the RabbitMQ `py-rag-query` queue.
    - Creates a MongoDB entry in the `py-rag` database, `query` collection:
        ```json
        {
            "id": "uuid",
            "query_msg": "Your question here",
            "created_at": "date_and_time",
            "response": ""
        }
        ```
2. **Python Worker**:
    - Processes the query:
        - Performs a semantic search.
        - Returns a response along with the top 5 hits.

---

## Text Embedding and Summarization

### Text Embedding
- **Library**: `sentence_transformers`  
- **Model**: `all-MiniLM-L6-v2`  
- **Features**: Lightweight and efficient, generates dense vector embeddings for semantic similarity, clustering, and search.

### Text Summarization
- **Library**: `transformers` (Hugging Face)  
- **Model**: `BART`  
- **Tokenizer**: `BartTokenizer`  
- **Features**: Converts text into tokens for summarization tasks.

---

## References
- [Storing and Querying Embeddings with PostgreSQL](https://dev.to/stephenc222/how-to-use-postgresql-to-store-and-query-vector-embeddings-h4b)
- [pgvector GitHub](https://github.com/pgvector/pgvector)
- [Semantic Search with SBERT](https://github.com/ShawhinT/YouTube-Blog/blob/main/LLMs/text-embeddings/2-semantic-search.ipynb)
- [SentenceTransformer Pretrained Models](https://www.sbert.net/docs/sentence_transformer/pretrained_models.html)
- [LangChain Multimodal Demo](https://colab.research.google.com/gist/alejandro-ao/47db0b8b9d00b10a96ab42dd59d90b86/langchain-multimodal.ipynb)
- [YouTube Guide: Semantic Search](https://www.youtube.com/watch?v=pIGRwMjhMaQ&ab_channel=MervinPraison)
- [Optimizing SentenceTransformer](https://stackoverflow.com/questions/77205123/how-do-i-slim-down-sberts-sentencer-transformer-library)
