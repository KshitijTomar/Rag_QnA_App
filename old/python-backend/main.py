from fastapi import FastAPI, HTTPException, UploadFile
import uvicorn
import asyncio
from pydantic import BaseModel
from transformers import AutoTokenizer, AutoModel, UploadFile
import torch
import numpy as np

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Text

app = FastAPI()
Base = declarative_base()

class Item(BaseModel):
    name: str
    price: float
    is_offer: bool|None
    
class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    content = Column(Text)
    embedding = Column(Text)

@app.get("/")
async def root():
    return {"message": "Document Ingestion and Q&A Backend"}


# Load the model
tokenizer = AutoTokenizer.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")
model = AutoModel.from_pretrained("sentence-transformers/all-MiniLM-L6-v2")

def generate_embedding(text):
    inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True)
    outputs = model(**inputs)
    return outputs.last_hidden_state.mean(dim=1).detach().numpy().tolist()

@app.post("/ingest")
def ingest_document(title: str, content: str):
    # embedding = generate_embedding(content)
    # Save to database logic here
    # return {"message": "Document ingested successfully", "embedding": embedding}
    return {"message": "Document ingested successfully", "title": title, "content": content}

@app.post("/qa")
async def ask_question(question: str):
    question_embedding = generate_embedding(question)
    # Retrieve relevant documents based on embeddings
    relevant_docs = "Mock retrieval logic"
    return {"answer": "Generated answer", "relevant_docs": relevant_docs}


# if __name__ == '__main__':
#     app.run(debug=True, host='0.0.0.0', port=8000)

# if __name__ == "__main__":
#     config = uvicorn.Config("main:app", host='0.0.0.0', port=8000, log_level="info")
#     server = uvicorn.Server(config)
#     server.run()

#     uvicorn.run("main:app", host='0.0.0.0', port=8000, log_level="info")


async def main():
    config = uvicorn.Config("main:app", host='0.0.0.0', port=8000, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())