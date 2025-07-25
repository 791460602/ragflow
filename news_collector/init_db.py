"""
新闻系统数据库初始化脚本

创建必要的数据库表
"""

import logging
from api.db import DB
from .db_models import (
    NewsSource,
    NewsTask,
    NewsContent,
    NewsKnowledgeBase,
    NewsHistory
)

logger = logging.getLogger(__name__)

def create_news_tables():
    """创建新闻系统相关的数据库表"""
    try:
        with DB.connection_context():
            # 创建所有表
            tables = [
                NewsKnowledgeBase,
                NewsSource,
                NewsTask,
                NewsContent,
                NewsHistory
            ]
            
            for table in tables:
                if not table.table_exists():
                    table.create_table()
                    logger.info(f"Created table: {table._meta.table_name}")
                else:
                    logger.info(f"Table already exists: {table._meta.table_name}")
                    
        logger.info("News database tables initialization completed")
        return True
        
    except Exception as e:
        logger.error(f"Failed to create news tables: {e}")
        return False

def drop_news_tables():
    """删除新闻系统相关的数据库表（谨慎使用）"""
    try:
        with DB.connection_context():
            tables = [
                NewsHistory,
                NewsContent,
                NewsTask,
                NewsSource,
                NewsKnowledgeBase
            ]
            
            for table in tables:
                if table.table_exists():
                    table.drop_table()
                    logger.warning(f"Dropped table: {table._meta.table_name}")
                    
        logger.warning("News database tables dropped")
        return True
        
    except Exception as e:
        logger.error(f"Failed to drop news tables: {e}")
        return False

if __name__ == "__main__":
    # 直接运行此脚本时创建表
    logging.basicConfig(level=logging.INFO)
    create_news_tables()
