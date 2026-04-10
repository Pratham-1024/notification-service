from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import Optional


class UserCreate(BaseModel):
    email : str
    password : str 


class UserResponse(BaseModel):
    id : UUID
    email : str
    is_active : bool
    created_at : datetime

    # For response schemas that come from DB objects, add:
    class Config:
        from_attributes = True  # allows reading from SQLAlchemy objects


class Token(BaseModel):
    access_token : str
    token_type : str

class TokenData(BaseModel):
    user_id : Optional[str] = None





