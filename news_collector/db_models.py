"""
新闻抓取系统数据库模型

基于RAGFlow项目的数据库模式，使用Peewee ORM
"""

from peewee import *
from playhouse.pool import PooledMySQLDatabase
from api.db.db_models import BaseModel, JSONField, ListField
from api.db import StatusEnum
from api import settings
import enum


class NewsSourceStatus(enum.Enum):
    """新闻源状态"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    DISABLED = "disabled"


class TaskStatus(enum.Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ParseStatus(enum.Enum):
    """解析状态"""
    PENDING = "pending"
    PARSING = "parsing"
    PARSED = "parsed"
    FAILED = "failed"


class NewsSource(BaseModel):
    """新闻源表"""
    f_id = CharField(max_length=32, primary_key=True)
    f_name = CharField(max_length=255, index=True)
    f_url = TextField()
    f_remark = TextField(null=True)
    f_status = CharField(max_length=20, default=NewsSourceStatus.ACTIVE.value, index=True)
    f_selector_config = JSONField(default={})
    f_last_crawl_time = BigIntegerField(null=True, index=True)
    f_total_articles = IntegerField(default=0)
    f_success_count = IntegerField(default=0)
    f_failure_count = IntegerField(default=0)

    class Meta:
        table_name = "news_source"
        indexes = (
            (("f_name", "f_url"), False),  # 组合索引
        )


class NewsTask(BaseModel):
    """新闻抓取任务表"""
    f_id = CharField(max_length=32, primary_key=True)
    f_task_name = CharField(max_length=255, index=True)
    f_kb_id = CharField(max_length=32, index=True)  # 关联的知识库ID
    f_source_ids = ListField(default=[])  # 新闻源ID列表
    f_status = CharField(max_length=20, default=TaskStatus.PENDING.value, index=True)
    f_auto_parse = BooleanField(default=True)
    f_max_articles_per_source = IntegerField(default=10)
    f_schedule_config = JSONField(default={})  # 调度配置（定时任务等）
    f_last_run_time = BigIntegerField(null=True, index=True)
    f_next_run_time = BigIntegerField(null=True, index=True)
    f_statistics = JSONField(default={})
    f_error_message = TextField(null=True)

    class Meta:
        table_name = "news_task"
        indexes = (
            (("f_kb_id", "f_status"), False),
            (("f_last_run_time", "f_next_run_time"), False),
        )


class NewsContent(BaseModel):
    """新闻内容表"""
    f_id = CharField(max_length=32, primary_key=True)
    f_source_id = CharField(max_length=32, index=True)
    f_task_id = CharField(max_length=32, index=True, null=True)
    f_title = CharField(max_length=500, index=True)
    f_content = TextField()
    f_content_text = TextField()  # 纯文本内容
    f_url = TextField(index=True)
    f_author = CharField(max_length=100, null=True)
    f_publish_time = BigIntegerField(null=True, index=True)
    f_crawl_time = BigIntegerField(index=True)
    f_parse_status = CharField(max_length=20, default=ParseStatus.PENDING.value, index=True)
    f_ragflow_doc_id = CharField(max_length=32, null=True, index=True)  # RAGFlow文档ID
    f_tags = ListField(default=[])  # 标签列表
    f_metadata = JSONField(default={})  # 元数据
    f_fingerprint = CharField(max_length=64, unique=True, index=True)  # 内容指纹，用于去重

    class Meta:
        table_name = "news_content"
        indexes = (
            (("f_source_id", "f_publish_time"), False),
            (("f_task_id", "f_crawl_time"), False),
            (("f_parse_status", "f_crawl_time"), False),
        )


class NewsKnowledgeBase(BaseModel):
    """新闻知识库关联表"""
    f_id = CharField(max_length=32, primary_key=True)
    f_kb_id = CharField(max_length=32, index=True)  # RAGFlow知识库ID
    f_kb_name = CharField(max_length=255, index=True)
    f_description = TextField(null=True)
    f_auto_parse = BooleanField(default=True)
    f_parse_method = CharField(max_length=50, default="naive")
    f_total_articles = IntegerField(default=0)
    f_parsed_articles = IntegerField(default=0)
    f_last_update_time = BigIntegerField(null=True, index=True)

    class Meta:
        table_name = "news_knowledge_base"


class NewsHistory(BaseModel):
    """新闻抓取历史记录表"""
    f_id = CharField(max_length=32, primary_key=True)
    f_task_id = CharField(max_length=32, index=True)
    f_source_id = CharField(max_length=32, index=True)
    f_start_time = BigIntegerField(index=True)
    f_end_time = BigIntegerField(null=True, index=True)
    f_status = CharField(max_length=20, index=True)
    f_articles_found = IntegerField(default=0)
    f_articles_new = IntegerField(default=0)
    f_articles_updated = IntegerField(default=0)
    f_articles_failed = IntegerField(default=0)
    f_error_message = TextField(null=True)
    f_execution_log = TextField(null=True)

    class Meta:
        table_name = "news_history"
        indexes = (
            (("f_task_id", "f_start_time"), False),
            (("f_source_id", "f_start_time"), False),
        )


# 表映射字典，用于动态获取模型类
NEWS_TABLES = {
    "news_source": NewsSource,
    "news_task": NewsTask,
    "news_content": NewsContent,
    "news_knowledge_base": NewsKnowledgeBase,
    "news_history": NewsHistory,
}


def create_news_tables():
    """创建新闻抓取系统相关的数据库表"""
    from api.db.db_models import DB
    
    with DB.connection_context():
        # 创建所有新闻相关表
        tables = [NewsSource, NewsTask, NewsContent, NewsKnowledgeBase, NewsHistory]
        DB.create_tables(tables, safe=True)
        
        print("News collector database tables created successfully")


def drop_news_tables():
    """删除新闻抓取系统相关的数据库表（谨慎使用）"""
    from api.db.db_models import DB
    
    with DB.connection_context():
        tables = [NewsHistory, NewsContent, NewsTask, NewsSource, NewsKnowledgeBase]
        DB.drop_tables(tables, safe=True)
        
        print("News collector database tables dropped")


def get_news_model_by_table_name(table_name: str):
    """根据表名获取模型类"""
    return NEWS_TABLES.get(table_name)


def init_news_database():
    """初始化新闻抓取系统数据库"""
    try:
        create_news_tables()
        print("✅ News collector database initialized successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to initialize news collector database: {e}")
        return False
