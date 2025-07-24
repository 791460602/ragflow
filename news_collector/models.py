"""
新闻抓取系统数据模型

定义了新闻源、任务、内容等核心数据结构
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class ScheduleType(Enum):
    """调度类型枚举"""
    MANUAL = "manual"
    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"


class NewsStatus(Enum):
    """新闻状态枚举"""
    ACTIVE = "active"
    INACTIVE = "inactive"


class ParseStatus(Enum):
    """解析状态枚举"""
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


@dataclass
class SelectorConfig:
    """网页选择器配置"""
    title_selector: str = "h1"
    content_selector: str = ".content, .article-content, .post-content"
    time_selector: str = ".time, .publish-time, .date"
    author_selector: str = ".author, .writer"
    link_selector: str = "a"
    
    def to_dict(self) -> Dict[str, str]:
        return {
            "title_selector": self.title_selector,
            "content_selector": self.content_selector,
            "time_selector": self.time_selector,
            "author_selector": self.author_selector,
            "link_selector": self.link_selector
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, str]) -> 'SelectorConfig':
        return cls(
            title_selector=data.get("title_selector", "h1"),
            content_selector=data.get("content_selector", ".content"),
            time_selector=data.get("time_selector", ".time"),
            author_selector=data.get("author_selector", ".author"),
            link_selector=data.get("link_selector", "a")
        )


@dataclass
class NewsSource:
    """新闻源数据模型"""
    id: Optional[int] = None
    name: str = ""
    url: str = ""
    remark: str = ""
    status: NewsStatus = NewsStatus.ACTIVE
    selector_config: SelectorConfig = field(default_factory=SelectorConfig)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    news_count: int = 0
    last_task_id: Optional[int] = None
    last_run_status: Optional[str] = None
    last_run_time: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "remark": self.remark,
            "status": self.status.value,
            "selector_config": self.selector_config.to_dict(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "news_count": self.news_count,
            "last_task_id": self.last_task_id,
            "last_run_status": self.last_run_status,
            "last_run_time": self.last_run_time.isoformat() if self.last_run_time else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NewsSource':
        """从字典创建实例"""
        instance = cls()
        instance.id = data.get("id")
        instance.name = data.get("name", "")
        instance.url = data.get("url", "")
        instance.remark = data.get("remark", "")
        instance.status = NewsStatus(data.get("status", "active"))
        instance.selector_config = SelectorConfig.from_dict(data.get("selector_config", {}))
        
        # 处理日期时间字段
        if data.get("created_at"):
            instance.created_at = datetime.fromisoformat(data["created_at"])
        if data.get("updated_at"):
            instance.updated_at = datetime.fromisoformat(data["updated_at"])
        if data.get("last_run_time"):
            instance.last_run_time = datetime.fromisoformat(data["last_run_time"])
            
        instance.news_count = data.get("news_count", 0)
        instance.last_task_id = data.get("last_task_id")
        instance.last_run_status = data.get("last_run_status")
        
        return instance


@dataclass
class NewsTask:
    """新闻抓取任务数据模型"""
    id: Optional[int] = None
    task_name: str = ""
    kb_id: str = ""
    source_ids: List[int] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    auto_parse: bool = True
    schedule_type: ScheduleType = ScheduleType.MANUAL
    schedule_time: Optional[str] = None
    schedule_days: List[int] = field(default_factory=list)
    max_articles_per_source: int = 100
    success_count: int = 0
    failed_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    run_log: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "task_name": self.task_name,
            "kb_id": self.kb_id,
            "source_ids": self.source_ids,
            "status": self.status.value,
            "auto_parse": self.auto_parse,
            "schedule_type": self.schedule_type.value,
            "schedule_time": self.schedule_time,
            "schedule_days": self.schedule_days,
            "max_articles_per_source": self.max_articles_per_source,
            "success_count": self.success_count,
            "failed_count": self.failed_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "run_log": self.run_log
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NewsTask':
        """从字典创建实例"""
        instance = cls()
        instance.id = data.get("id")
        instance.task_name = data.get("task_name", "")
        instance.kb_id = data.get("kb_id", "")
        instance.source_ids = data.get("source_ids", [])
        instance.status = TaskStatus(data.get("status", "pending"))
        instance.auto_parse = data.get("auto_parse", True)
        instance.schedule_type = ScheduleType(data.get("schedule_type", "manual"))
        instance.schedule_time = data.get("schedule_time")
        instance.schedule_days = data.get("schedule_days", [])
        instance.max_articles_per_source = data.get("max_articles_per_source", 100)
        instance.success_count = data.get("success_count", 0)
        instance.failed_count = data.get("failed_count", 0)
        instance.run_log = data.get("run_log", [])
        
        # 处理日期时间字段
        if data.get("created_at"):
            instance.created_at = datetime.fromisoformat(data["created_at"])
        if data.get("updated_at"):
            instance.updated_at = datetime.fromisoformat(data["updated_at"])
        if data.get("finished_at"):
            instance.finished_at = datetime.fromisoformat(data["finished_at"])
            
        return instance


@dataclass
class NewsContent:
    """新闻内容数据模型"""
    id: Optional[int] = None
    title: str = ""
    content_html: str = ""
    content_text: str = ""
    summary: str = ""
    url: str = ""
    publish_time: Optional[datetime] = None
    status: NewsStatus = NewsStatus.ACTIVE
    parse_status: ParseStatus = ParseStatus.PENDING
    document_id: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    source_id: Optional[int] = None
    kb_id: str = ""
    task_id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "title": self.title,
            "content_html": self.content_html,
            "content_text": self.content_text,
            "summary": self.summary,
            "url": self.url,
            "publish_time": self.publish_time.isoformat() if self.publish_time else None,
            "status": self.status.value,
            "parse_status": self.parse_status.value,
            "document_id": self.document_id,
            "tags": self.tags,
            "metadata": self.metadata,
            "source_id": self.source_id,
            "kb_id": self.kb_id,
            "task_id": self.task_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'NewsContent':
        """从字典创建实例"""
        instance = cls()
        instance.id = data.get("id")
        instance.title = data.get("title", "")
        instance.content_html = data.get("content_html", "")
        instance.content_text = data.get("content_text", "")
        instance.summary = data.get("summary", "")
        instance.url = data.get("url", "")
        instance.status = NewsStatus(data.get("status", "active"))
        instance.parse_status = ParseStatus(data.get("parse_status", "pending"))
        instance.document_id = data.get("document_id")
        instance.tags = data.get("tags", [])
        instance.metadata = data.get("metadata", {})
        instance.source_id = data.get("source_id")
        instance.kb_id = data.get("kb_id", "")
        instance.task_id = data.get("task_id")
        
        # 处理日期时间字段
        if data.get("publish_time"):
            instance.publish_time = datetime.fromisoformat(data["publish_time"])
        if data.get("created_at"):
            instance.created_at = datetime.fromisoformat(data["created_at"])
        if data.get("updated_at"):
            instance.updated_at = datetime.fromisoformat(data["updated_at"])
            
        return instance


@dataclass 
class KnowledgeBase:
    """知识库数据模型"""
    id: str = ""
    name: str = ""
    description: str = ""
    chunk_method: str = "naive"
    status: NewsStatus = NewsStatus.ACTIVE
    document_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "chunk_method": self.chunk_method,
            "status": self.status.value,
            "document_count": self.document_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'KnowledgeBase':
        """从字典创建实例"""
        instance = cls()
        instance.id = data.get("id", "")
        instance.name = data.get("name", "")
        instance.description = data.get("description", "")
        instance.chunk_method = data.get("chunk_method", "naive")
        instance.status = NewsStatus(data.get("status", "active"))
        instance.document_count = data.get("document_count", 0)
        
        # 处理日期时间字段
        if data.get("created_at"):
            instance.created_at = datetime.fromisoformat(data["created_at"])
        if data.get("updated_at"):
            instance.updated_at = datetime.fromisoformat(data["updated_at"])
            
        return instance
