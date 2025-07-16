from pydantic import BaseModel
from typing import List, Optional

class NewsSource(BaseModel):
    id: int
    name: str
    url: str
    remark: Optional[str] = None

class NewsSourceCreate(BaseModel):
    name: str
    url: str
    remark: Optional[str] = None

class NewsFetchRequest(BaseModel):
    source_ids: List[int]

class NewsHistoryItem(BaseModel):
    id: int
    sourceName: str
    title: str
    status: str
    createdAt: str 