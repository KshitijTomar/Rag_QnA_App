# RAG model python

## Simple frontend
A simple HTML page with js (script section) to handle interactivity in same html
1. upload file:
    - file upload input box, to take file ask api to upload it to minio
    - list/table of uploaded file with its status
        - status = "failed/uploaded/embedding/completed"
    - a refresh button (rest call) to check mongo doc status of the file
2. a search query  with search button , on hit rest call to api to trigger rmq for search
3. a readable only textbox for the query response

## Simple API
API should be able tohandle Mongo doc creation and fetch
1. upload file by frontend: handle file upload to minio. file upload to minio needs to be mentioned into a new mongo doc.
2. rest call to get list/table of uploaded file with its status (limit 25) (refresh button)
3. search api rest call to trigger rmq for search for python worker to provide result, response will be the query result.


## Flow file uplaod and embedding gen and storage:

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

## References:
- https://dev.to/stephenc222/how-to-use-postgresql-to-store-and-query-vector-embeddings-h4b
- https://github.com/pgvector/pgvector
- https://www.youtube.com/watch?v=pIGRwMjhMaQ&ab_channel=MervinPraison
- https://stackoverflow.com/questions/77205123/how-do-i-slim-down-sberts-sentencer-transformer-library