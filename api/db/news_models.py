#
#  新闻收集器数据库模型
#
#  定义新闻源、抓取任务和新闻内容的数据库表结构
#

from peewee import CharField, TextField, IntegerField, BooleanField, JSONField
from api.db.db_models import DataBaseModel


class NewsSource(DataBaseModel):
    """新闻源模型"""
    id = CharField(max_length=32, primary_key=True)
    name = CharField(max_length=128, null=False, help_text="新闻源名称", index=True)
    url = TextField(null=False, help_text="新闻源URL")
    remark = TextField(null=True, help_text="备注信息")
    status = CharField(max_length=16, null=False, default="active", help_text="状态: active|inactive", index=True)
    user_id = CharField(max_length=32, null=False, help_text="创建用户ID", index=True)
    tenant_id = CharField(max_length=32, null=False, help_text="租户ID", index=True)
    
    # 抓取配置
    fetch_config = JSONField(null=False, default={
        "selector": None,  # CSS选择器
        "encoding": "utf-8",  # 页面编码
        "timeout": 30,  # 超时时间
        "headers": {}  # 请求头
    }, help_text="抓取配置")
    
    # 统计信息
    total_articles = IntegerField(default=0, help_text="总文章数")
    last_fetch_time = IntegerField(null=True, help_text="最后抓取时间戳", index=True)
    
    def __str__(self):
        return self.name
    
    class Meta:
        db_table = "news_source"


class NewsTask(DataBaseModel):
    """新闻抓取任务模型"""
    id = CharField(max_length=32, primary_key=True)
    task_name = CharField(max_length=128, null=False, help_text="任务名称", index=True)
    kb_id = CharField(max_length=32, null=False, help_text="关联知识库ID", index=True)
    user_id = CharField(max_length=32, null=False, help_text="创建用户ID", index=True)
    tenant_id = CharField(max_length=32, null=False, help_text="租户ID", index=True)
    
    # 任务配置
    source_ids = JSONField(null=False, default=[], help_text="新闻源ID列表")
    auto_parse = BooleanField(default=True, help_text="是否自动解析到知识库")
    max_articles_per_source = IntegerField(default=10, help_text="每个源最大抓取文章数")
    
    # 任务状态
    status = CharField(max_length=16, null=False, default="pending", 
                      help_text="状态: pending|running|completed|failed", index=True)
    last_run_time = IntegerField(null=True, help_text="最后运行时间戳", index=True)
    
    # 统计信息
    statistics = JSONField(null=False, default={
        "total_articles": 0,
        "success_count": 0,
        "failed_count": 0,
        "skipped_count": 0
    }, help_text="执行统计")
    
    # 错误信息
    error_message = TextField(null=True, help_text="错误信息")
    
    def __str__(self):
        return self.task_name
    
    class Meta:
        db_table = "news_task"


class NewsContent(DataBaseModel):
    """新闻内容模型"""
    id = CharField(max_length=32, primary_key=True)
    task_id = CharField(max_length=32, null=False, help_text="关联任务ID", index=True)
    source_id = CharField(max_length=32, null=False, help_text="新闻源ID", index=True)
    kb_id = CharField(max_length=32, null=True, help_text="知识库ID", index=True)
    user_id = CharField(max_length=32, null=False, help_text="用户ID", index=True)
    tenant_id = CharField(max_length=32, null=False, help_text="租户ID", index=True)
    
    # 新闻内容
    title = CharField(max_length=512, null=False, help_text="新闻标题", index=True)
    content = TextField(null=True, help_text="新闻正文")
    summary = TextField(null=True, help_text="摘要")
    url = TextField(null=False, help_text="原文URL")
    author = CharField(max_length=128, null=True, help_text="作者")
    
    # 时间信息
    publish_time = IntegerField(null=True, help_text="发布时间戳", index=True)
    fetch_time = IntegerField(null=False, help_text="抓取时间戳", index=True)
    
    # 处理状态
    parse_status = CharField(max_length=16, null=False, default="pending", 
                           help_text="解析状态: pending|parsed|failed", index=True)
    doc_id = CharField(max_length=32, null=True, help_text="关联文档ID", index=True)
    
    # 内容特征
    content_hash = CharField(max_length=64, null=True, help_text="内容哈希值（用于去重）", index=True)
    word_count = IntegerField(default=0, help_text="字数统计")
    
    def __str__(self):
        return self.title
    
    class Meta:
        db_table = "news_content"
