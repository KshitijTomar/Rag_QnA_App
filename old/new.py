from datasets import load_dataset
import pandas as pd
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.decomposition import PCA
from sklearn.metrics import DistanceMetric
import pymongo
import minio
import os
import psycopg2
import json

embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

class MongoDB:
    def __init__(self):
        self.conn = pymongo.MongoClient(os.getenv("MONGO_URL"))
        self.db = self._conn["py-rag"]
        self.coll_input = self.db["input"]
        self.coll_embeddings = self.db["embeddings"]

class Postgres:
    conn = None
    cur = None

    def __init__(self):
        self.conn =  psycopg2.connect(
            user="myuser",
            password="mypassword",
            host="localhost",
            port=5432,  # The port you exposed in docker-compose.yml
            database="mydb"
        )
        self.cur = self.conn.cursor()
        
    def execute(self, query):
        self.cur.execute(query)



database = None
class Database:
    mongo_client = None
    minio_client = None
    postgres_client = None

    def __init__(self):
        self.mongo_client = MongoDB()
        self.minio_client = minio.Minio(
                endpoint=os.getenv("MINIO_URL_PORT"),
                access_key=os.getenv("MINIO_ACCESS_KEY"),
                secret_key=os.getenv("MINIO_SECRET_KEY"),
                secure=False
            )
        self.postgres_client = Postgres()


def get_embedding(text: str) -> list[float]:
    if not text.strip():
        print("Attempted to get embedding for empty text.")
        return []

    embedding = embedding_model.encode(text)

    # return embedding.tolist()
    return json.dumps(embedding.numpy().tolist()[0])


def get_dataset_movies():
    dataset = load_dataset("AIatMongoDB/embedded_movies")
    dataset_df = pd.DataFrame(dataset['train'])
    dataset_df = dataset_df.dropna(subset=['plot'])
    dataset_df = dataset_df.drop(columns=['plot_embedding'])
    return dataset_df

def query_input(embedding_model, embedding_arr, query = "I need a movie with peniless"):
    query_embedding = embedding_model.encode(query)
    dist = DistanceMetric.get_metric('euclidean') # other distances: manhattan, chebyshev
    dist_arr = dist.pairwise(embedding_arr, query_embedding.reshape(1, -1)).flatten()
    idist_arr_sorted = np.argsort(dist_arr)
    return idist_arr_sorted

def main():
    print("db init")
    database = Database()
    print("getting dataframe")
    df = get_dataset_movies()
    print("embedding dataset")
    embedding_arr = embedding_model.encode(df['plot'].to_list())
    print("query input")
    idist = query_input(embedding_model, embedding_arr, "I need a movie with peniless")
    print("output")
    print(df.iloc[idist[0]])
    print(df.iloc[idist[:10]])


def main2():
    print("db init")
    database = Database()
    print("getting dataframe")
    
    # Sample data
    data = [
        "Titanic: The story of the 1912 sinking of the largest luxury liner ever built",
        "The Lion King: Lion cub and future king Simba searches for his identity",
        "Avatar: A marine is dispatched to the moon Pandora on a unique mission"
    ]
    # Ingest data into Atlas
    inserted_doc_count = 0
    for text in data:
        embedding = get_embedding(text)
        database.postgres_client.execute(
            "INSERT INTO items (content, embedding) VALUES (%s, %s)",
            (text, embedding)
        )
        inserted_doc_count += 1

    print("embedding dataset")
    df["embedding"] = df["fullplot"].apply(get_embedding)

    results = query_vector_search(database, query = "ocean tragedy")

    # Print results
    for i in results:
        print(i)



main()
