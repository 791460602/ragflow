import threading
from typing import List, Dict
from .schemas import NewsSource, NewsSourceCreate, NewsHistoryItem
import datetime

# 新增：引入SDK
try:
    from ragflow_sdk.modules.dataset import Dataset
    import io
except ImportError:
    Dataset = None  # 兼容无SDK环境

# 内存存储
_news_sources: Dict[int, NewsSource] = {}
_news_history: List[NewsHistoryItem] = []
_id_lock = threading.Lock()
_next_source_id = 1
_next_history_id = 1

def get_news_sources() -> List[NewsSource]:
    return list(_news_sources.values())

def add_news_source(data: NewsSourceCreate) -> NewsSource:
    global _next_source_id
    with _id_lock:
        source_id = _next_source_id
        _next_source_id += 1
    source = NewsSource(id=source_id, **data.dict())
    _news_sources[source_id] = source
    return source

def delete_news_source(source_id: int) -> bool:
    return _news_sources.pop(source_id, None) is not None

def add_news_history(source_name: str, title: str, status: str) -> NewsHistoryItem:
    global _next_history_id
    with _id_lock:
        history_id = _next_history_id
        _next_history_id += 1
    item = NewsHistoryItem(
        id=history_id,
        sourceName=source_name,
        title=title,
        status=status,
        createdAt=datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    )
    _news_history.append(item)
    return item

def get_news_history() -> List[NewsHistoryItem]:
    return list(_news_history)

# 新增：通过SDK上传新闻到知识库
def save_news_to_kb_with_sdk(news_list, kb_id, sdk_client):
    if Dataset is None:
        raise ImportError('ragflow_sdk 未安装')
    dataset = Dataset(id=kb_id, client=sdk_client)
    document_list = []
    for news in news_list:
        document_list.append({
            "display_name": news['title'] + ".txt",
            "blob": io.BytesIO(news['content'].encode('utf-8'))
        })
    dataset.upload_documents(document_list) 