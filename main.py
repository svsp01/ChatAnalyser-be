from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
from pymongo import MongoClient
import pandas as pd
from typing import Dict, Any
import PyPDF2
import os
import requests


app = FastAPI()

class Query(BaseModel):
    question: str

data_store: Dict[str, Any] = {}
mongo_client = MongoClient(os.environ.get("DBURL"))  
db = mongo_client["AnalyZer"]  
collection = db["Analyser"] 

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
    with open(file_path, "rb") as file:
        pdf_reader = PyPDF2.PdfFileReader(file)
        num_pages = pdf_reader.numPages
        for page_number in range(num_pages):
            page = pdf_reader.getPage(page_number)
            text += page.extractText()
    return text


@app.post("/upload_file/{org_id}")
async def upload_file(org_id: str, file: UploadFile = File(...)):
    if not file.filename.endswith(('.xlsx', '.xls', '.pdf')):
        raise HTTPException(status_code=400, detail="Unsupported file type")

    file_path = f"temp_files/{file.filename}"
    os.makedirs("temp_files", exist_ok=True)
    with open(file_path, "wb") as f:
        f.write(await file.read())

    if file.filename.endswith(('.xlsx', '.xls')):
        data = process_excel(file_path)
    elif file.filename.endswith('.pdf'):
        data = process_pdf(file_path)
    
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
    
    # input_text = f"Organization Data: {org_data}. Question: {query.question}"

    API_URL = os.environ.get("HFURL")
    Token = os.environ.get("TOKENHF")
    headers = {"Authorization": f"Bearer {Token}"}

    def query_hf(payload):
        response = requests.post(API_URL, headers=headers, json=payload)
        return response.json()

    payload = {
        "inputs": {
            "question": query.question,
            "context": org_data
        }
    }

    response = query_hf(payload)
    generated_answer = response.get('answer', 'No answer found')

    return {"answer": generated_answer}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)