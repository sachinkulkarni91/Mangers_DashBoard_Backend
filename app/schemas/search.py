from pydantic import BaseModel
from typing import List, Optional


class User(BaseModel):
    sys_id: str
    name: Optional[str] = None
    user_name: Optional[str] = None
    email: Optional[str] = None

    class Config:
        extra = 'allow'  # allow arbitrary additional fields when requesting all


class Location(BaseModel):
    sys_id: str
    name: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None

    class Config:
        extra = 'allow'


class UserSearchResults(BaseModel):
    result: List[User]


class LocationSearchResults(BaseModel):
    result: List[Location]
