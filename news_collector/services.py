"""
新闻抓取系统服务层

提供业务逻辑处理，连接API和底层模块
现在使用数据库存储替代内存存储
"""

import logging

# 导入数据库服务层
from .db_services import (
    initialize_news_manager,
    get_news_manager,
    get_knowledge_bases,
    get_knowledge_base,
    create_knowledge_base,
    get_news_sources,
    get_news_source,
    create_news_source,
    update_news_source,
    delete_news_source,
    get_news_tasks,
    get_news_task,
    create_news_task,
    update_news_task,
    delete_news_task,
    execute_news_task,
    get_news_contents,
    get_news_content,
    delete_news_content,
    get_statistics_overview,
    get_source_statistics
)

logger = logging.getLogger(__name__)

# 所有函数都直接代理到数据库服务层
# 这样保持了API的兼容性，同时使用数据库存储

# 这个文件现在作为一个代理层，所有实际的实现都在db_services.py中
# 如果需要添加额外的业务逻辑（如缓存、权限检查等），可以在这里添加
