"""
新闻抓取系统数据库模型

使用SQLAlchemy定义数据库表结构
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON, ForeignKey, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

Base = declarative_base()


class SourceStatus(enum.Enum):
    """新闻源状态"""
    ACTIVE = "active"
    INACTIVE = "inactive"


class TaskStatus(enum.Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class ScheduleType(enum.Enum):
    """调度类型"""
    MANUAL = "manual"
    ONCE = "once"
    DAILY = "daily"
    WEEKLY = "weekly"


class NewsStatus(enum.Enum):
    """新闻状态"""
    ACTIVE = "active"
    INACTIVE = "inactive"


class ParseStatus(enum.Enum):
    """解析状态"""
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


class NewsSourceModel(Base):
    """新闻源数据模型"""
    __tablename__ = "news_sources"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, comment="新闻源名称")
    url = Column(String(500), nullable=False, comment="新闻源URL")
    remark = Column(Text, comment="备注")
    status = Column(Enum(SourceStatus), default=SourceStatus.ACTIVE, comment="状态")
    selector_config = Column(JSON, comment="选择器配置")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    news_count = Column(Integer, default=0, comment="新闻数量")
    last_task_id = Column(Integer, ForeignKey("news_tasks.id"), comment="最后执行的任务ID")
    last_run_status = Column(String(50), comment="最后运行状态")
    last_run_time = Column(DateTime, comment="最后运行时间")
    
    # 关系
    tasks = relationship("NewsTaskModel", secondary="task_sources", back_populates="sources")
    news_items = relationship("NewsContentModel", back_populates="source")
    last_task = relationship("NewsTaskModel", foreign_keys=[last_task_id])


class NewsTaskModel(Base):
    """新闻抓取任务数据模型"""
    __tablename__ = "news_tasks"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_name = Column(String(255), nullable=False, comment="任务名称")
    kb_id = Column(String(255), nullable=False, comment="知识库ID")
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING, comment="任务状态")
    auto_parse = Column(Boolean, default=True, comment="是否自动解析")
    schedule_type = Column(Enum(ScheduleType), default=ScheduleType.MANUAL, comment="调度类型")
    schedule_time = Column(String(10), comment="调度时间 HH:MM")
    schedule_days = Column(JSON, comment="调度天数（周几）")
    max_articles_per_source = Column(Integer, default=100, comment="每个源最大文章数")
    success_count = Column(Integer, default=0, comment="成功数量")
    failed_count = Column(Integer, default=0, comment="失败数量")
    run_log = Column(JSON, comment="运行日志")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    finished_at = Column(DateTime, comment="完成时间")
    
    # 关系
    sources = relationship("NewsSourceModel", secondary="task_sources", back_populates="tasks")
    news_items = relationship("NewsContentModel", back_populates="task")


class TaskSourceModel(Base):
    """任务-新闻源关联表"""
    __tablename__ = "task_sources"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(Integer, ForeignKey("news_tasks.id"), nullable=False)
    source_id = Column(Integer, ForeignKey("news_sources.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())


class NewsContentModel(Base):
    """新闻内容数据模型"""
    __tablename__ = "news_contents"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(500), nullable=False, comment="标题")
    content_html = Column(Text, comment="HTML内容")
    content_text = Column(Text, comment="纯文本内容")
    summary = Column(Text, comment="摘要")
    url = Column(String(500), comment="原文URL")
    publish_time = Column(DateTime, comment="发布时间")
    status = Column(Enum(NewsStatus), default=NewsStatus.ACTIVE, comment="状态")
    parse_status = Column(Enum(ParseStatus), default=ParseStatus.PENDING, comment="解析状态")
    document_id = Column(String(255), comment="RAGFlow文档ID")
    tags = Column(JSON, comment="标签")
    metadata = Column(JSON, comment="元数据")
    source_id = Column(Integer, ForeignKey("news_sources.id"), nullable=False, comment="新闻源ID")
    kb_id = Column(String(255), comment="知识库ID")
    task_id = Column(Integer, ForeignKey("news_tasks.id"), comment="任务ID")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    
    # 关系
    source = relationship("NewsSourceModel", back_populates="news_items")
    task = relationship("NewsTaskModel", back_populates="news_items")


class KnowledgeBaseModel(Base):
    """知识库数据模型（用于缓存RAGFlow知识库信息）"""
    __tablename__ = "knowledge_bases"
    
    id = Column(String(255), primary_key=True, comment="知识库ID")
    name = Column(String(255), nullable=False, comment="知识库名称")
    description = Column(Text, comment="描述")
    chunk_method = Column(String(50), default="naive", comment="分块方法")
    status = Column(Enum(NewsStatus), default=NewsStatus.ACTIVE, comment="状态")
    document_count = Column(Integer, default=0, comment="文档数量")
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
