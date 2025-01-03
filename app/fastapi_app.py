from fastapi import FastAPI
from fastapi import HTTPException, File, UploadFile, Request, status
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from utils import get_answer_from_retrieved_documents, upload_file_to_minio_mongo_rmq, getfiles
import uvicorn
from pydantic import BaseModel

app = FastAPI(
    title="Rag_QnA_App",
    version="0.1",
    contact={
        "name": "Kshitij Tomar",
        "email": "kshtjtomar40@gmail.com",
        "phone_no": 9891562247
    }
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5000", "http://localhost:8000", "http://127.0.0.1:5000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    """
    Endpoint that returns a basic welcome message.
    """
    return {"message": "Hello World"}


# API to get file status (mongo)
@app.get("/api/files")
async def get_files():
    """
    Retrieve a list of files stored in MongoDB.
    Returns:
        - files: A list of file metadata retrieved from the database.
    """
    try:
        files = getfiles()
        return {"files": files}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error retrieving files: {str(e)}")


# API to Upload file to Minio and trigger RMQ
@app.post("/api/upload")
async def upload_file(file: Optional[UploadFile] = File(None)):
    """
    Upload a file to Minio.
    Args:
        - file: The file to be uploaded (via multipart form-data).
    Returns:
        - Success message upon successful file upload.
    Raises:
        - 400: If no file is provided or selected.
        - 500: If the file upload process fails.
    """
    if not file:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No file provided")
    if file.filename == '':
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No file selected")

    try:
        # Call the function to handle file upload
        upload_file_to_minio_mongo_rmq(file.file, file.filename)
        return {"message": "File uploaded successfully!"}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to upload file: {str(e)}")


class Search(BaseModel):
    query_msg: str
    file_selection: str | None = None
    
# API for search query
@app.post("/api/search")
async def search_query(search: Search):
    """
    Search for answers in documents based on a query.
    Args:
        - query_msg: The search query text.
        - file_selection: (Optional) Specific file to restrict the search to.
    Returns:
        - response: A detailed response object containing:
            - answer: The extracted answer from documents.
            - file_name: The name of the file containing the answer.
    Raises:
        - 400: If no query message is provided.
        - 500: If an error occurs during the search process.
    """
    query_msg = search.query_msg
    file_selection = search.file_selection

    if not query_msg:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No query message provided")

    try:
        result = get_answer_from_retrieved_documents(query_msg, file_selection)
        return {
            "response": result["response"],
            "answer": result["answer"],
            "file_name": result["file_name"],
        }
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error occurred: {str(e)}")



# Start the FastAPI app
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)