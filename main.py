from tkinter import Image
from fastapi import FastAPI, UploadFile, File, HTTPException # type: ignore
from pydantic import BaseModel # type: ignore
from pymongo import MongoClient
from bson.objectid import ObjectId
from bson import Binary
import pandas as pd
from typing import Dict, Any
import PyPDF2
import os
import requests
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware # type: ignore
load_dotenv()  
app = FastAPI()

origins = [
    "http://localhost.com",
    "https://localhost.com",
    "http://localhost",
    "http://localhost:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)



class Query(BaseModel):
    question: str

data_store: Dict[str, Any] = {}
mongo_client = MongoClient(os.environ.get("DBURL"))  
db = mongo_client["AnalyZer"]  
collection = db["Analyser"] 
# collection = db['images']


def process_excel(file_path: str) -> Dict[str, Any]:
    try:
        df = pd.read_excel(file_path, engine='openpyxl')
    except Exception:
        try:
            df = pd.read_csv(file_path)
        except Exception as e:
            raise Exception(f"Failed to read file: {e}")
    
    data = df.to_dict(orient='records')
    return data

def process_pdf(file_path: str) -> str:
    text = ""
    with open(file_path, 'rb') as pdf_file:
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        for page_num in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_num]
            text += page.extract_text()
    return text


@app.post("/upload_file/{org_id}")
async def upload_file(org_id: str, file: UploadFile = File(...)):
    if not file.filename.endswith(('.xlsx', '.xls', '.pdf','.png', '.jpg', '.jpeg', '.gif')):
        raise HTTPException(status_code=400, detail="Unsupported file type")

    file_path = f"temp_files/{file.filename}"
    os.makedirs("temp_files", exist_ok=True)
    with open(file_path, "wb") as f:
        f.write(await file.read())

    if file.filename.endswith(('.xlsx', '.xls')):
        data = process_excel(file_path)
    elif file.filename.endswith('.pdf'):
        data = process_pdf(file_path)
    elif file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
        data = process_image(file_path)
    
    data_to_insert = {"org_id": org_id, "data": data}
    collection.insert_one(data_to_insert)

    os.remove(file_path)

    return {
        "message": "File successfully processed and data stored",
        "Data": data
    }


     

@app.post("/query/{org_id}")
async def query(org_id: str, query: Query):
    org_data = collection.find_one({"org_id": org_id})
    if not org_data:
        raise HTTPException(status_code=404, detail="Organization not found")
    
    if "chat_history" not in org_data:
        org_data["chat_history"] = []
        
    API_URL = os.environ.get("HFURL")
    Token = os.environ.get("TOKENHF")
    headers = {"Authorization": f"Bearer {Token}"}
    


    def query_hf(payload):
        response = requests.post(API_URL, headers=headers, json=payload)
        return response.json()

    payload = {
        "inputs": {
            "question": query.question,
            "context": str(org_data)
        }
    }

    response = query_hf(payload)
    generated_answer = response.get('answer', 'No answer found')

    org_data["chat_history"].append({"type": "question", "text": query.question})
    org_data["chat_history"].append({"type": "answer", "text": generated_answer})
    collection.update_one({"org_id": org_id}, {"$set": {"chat_history": org_data["chat_history"]}})
    return {"answer": generated_answer, "chat_history": org_data["chat_history"]}

@app.get("/getAllOrganization")
async def getAllOrganization():
    all_data = list(collection.find({}))
    print(all_data)
    
    for data in all_data:
        data["_id"] = str(data["_id"])  
    return all_data

@app.get("/getOrgById/{org_id}")
async def getOrgById(org_id: str):
    try:
        data = collection.find_one({"_id": ObjectId(org_id)})
        if not data:
            raise HTTPException(status_code=404, detail="Organization not found")
        data["_id"] = str(data["_id"])  
        return data
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

if __name__ == "__main__":
    import uvicorn # type: ignore
    uvicorn.run(app, host="0.0.0.0", port=8000)