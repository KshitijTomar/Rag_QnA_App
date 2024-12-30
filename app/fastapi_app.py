from fastapi import FastAPI
from fastapi import HTTPException, File, UploadFile, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
from utils import get_answer_from_retrieved_documents, upload_file_to_mongo, getfiles
import uvicorn

app = FastAPI()

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
    return {"message": "Hello World"}


# API to get file status (mongo)
@app.get("/api/files")
async def get_files():
    try:
        files = getfiles()
        return {"files": files}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Error retrieving files: {str(e)}")


# API to Upload file to Mongo and trigger RMQ
@app.post("/api/upload")
async def upload_file(file: Optional[UploadFile] = File(None)):
    if not file:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No file provided")
    if file.filename == '':
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No file selected")

    file_name = file.filename
    file_extension = file_name.split('.')[-1]

    try:
        # Call the function to handle file upload
        upload_file_to_mongo(file.file, file_name, file_extension)
        return {"message": "File uploaded successfully!"}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to upload file: {str(e)}")


# API for search query
@app.post("/api/search")
async def search_query(request: Request):
    data = await request.json()
    query_msg = data.get("query_msg", "")

    if not query_msg:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No query message provided")

    try:
        result = get_answer_from_retrieved_documents(query_msg)
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