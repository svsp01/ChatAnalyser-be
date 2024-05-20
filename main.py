from fastapi import FastAPI, HTTPException, Depends, status, File, UploadFile
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from prisma import Prisma
from datetime import datetime, timedelta
from typing import List

SECRET_KEY = "7w7q7e8sa5dfwef6asdfaef3adsf4wefasd6"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

class Token(BaseModel):
    access_token: str
    token_type: str
    user: dict

class TokenData(BaseModel):
    email: str | None = None

class User(BaseModel):
    username: str
    email: str

class UserInDB(User):
    hashed_password: str

class UserCreate(BaseModel):
    username: str
    email: str
    password: str

class FileSchema(BaseModel):
    filename: str
    content: str

# Password Hashing
pwd_context = CryptContext(schemes=["bcrypt"])

# OAuth2 Scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# FastAPI App
app = FastAPI()
prisma = Prisma()

@app.on_event("startup")
async def startup():
    await prisma.connect()

@app.on_event("shutdown")
async def shutdown():
    await prisma.disconnect()

# Utility Functions
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_user_by_email(email: str):
    user = await prisma.user.find_unique(where={"email": email})
    if user:
        return UserInDB(**user.dict())

async def authenticate_user(email: str, password: str):
    user = await get_user_by_email(email)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        token_data = TokenData(email=email)
    except JWTError:
        raise credentials_exception
    user = await get_user_by_email(email=token_data.email)
    if user is None:
        raise credentials_exception
    return user

# Routes
@app.post("/signup/", response_model=User)
async def create_user(user: UserCreate):
    hashed_password = user.password
    user_data = {
        "username": user.username,
        "email": user.email,
        "hashed_password": hashed_password
    }
    db_user = await prisma.user.create(data=user_data)
    print(db_user)
    return db_user
@app.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer", "user": user.dict()}

@app.post("/upload/", response_model=FileSchema)
async def upload_file(file: UploadFile, current_user: User = Depends(get_current_user)):
    content = await file.read()
    file_data = {
        "filename": file.filename,
        "content": content.decode("utf-8"),
        "userId": current_user.id
    }
    db_file = await prisma.file.create(data=file_data)
    return db_file

@app.get("/files/{file_id}", response_model=FileSchema)
async def read_file(file_id: str, current_user: User = Depends(get_current_user)):
    file = await prisma.file.find_unique(where={"id": file_id})
    if file is None or file.userId != current_user.id:
        raise HTTPException(status_code=404, detail="File not found")
    return file

@app.get("/search/", response_model=List[FileSchema])
async def search_files(query: str, current_user: User = Depends(get_current_user)):
    files = await prisma.file.find_many(where={"filename": {"contains": query}})
    return files

@app.get("/preview/{file_id}", response_model=FileSchema)
async def preview_file(file_id: str, current_user: User = Depends(get_current_user)):
    file = await prisma.file.find_unique(where={"id": file_id})
    if file is None or file.userId != current_user.id:
        raise HTTPException(status_code=404, detail="File not found")
    return file
