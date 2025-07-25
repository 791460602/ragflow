#
#  新闻收集器服务层
#
#  提供新闻源、抓取任务和新闻内容的数据库操作服务
#

import hashlib
import time
from datetime import datetime
from typing import List, Optional, Dict, Any

from api.db import StatusEnum
from api.db.db_models import DB, NewsSource, NewsTask, NewsContent
from api.db.services.common_service import CommonService
from api.db.services.knowledgebase_service import KnowledgebaseService
from api.utils import current_timestamp, get_uuid


class NewsSourceService(CommonService):
    """新闻源服务"""
    model = NewsSource

    @classmethod
    @DB.connection_context()
    def create_source(cls, name: str, url: str, user_id: str, tenant_id: str, 
                     remark: str = "", fetch_config: Dict = None) -> NewsSource:
        """创建新闻源"""
        source_id = get_uuid()
        
        source_data = {
            "id": source_id,
            "name": name,
            "url": url,
            "remark": remark,
            "user_id": user_id,
            "tenant_id": tenant_id,
            "status": "active",
            "fetch_config": fetch_config or {},
            "total_articles": 0,
            "create_time": current_timestamp(),
            "create_date": datetime.now(),
            "update_time": current_timestamp(),
            "update_date": datetime.now()
        }
        
        source = cls.model.create(**source_data)
        return source

    @classmethod
    @DB.connection_context()
    def get_by_user(cls, user_id: str, tenant_id: str, status: str = None) -> List[NewsSource]:
        """获取用户的新闻源列表"""
        query = cls.model.select().where(
            cls.model.user_id == user_id,
            cls.model.tenant_id == tenant_id
        )
        
        if status:
            query = query.where(cls.model.status == status)
            
        return list(query.order_by(cls.model.create_time.desc()))

    @classmethod
    @DB.connection_context()
    def update_source(cls, source_id: str, **kwargs) -> bool:
        """更新新闻源"""
        update_data = {k: v for k, v in kwargs.items() if v is not None}
        update_data["update_time"] = current_timestamp()
        update_data["update_date"] = datetime.now()
        
        return cls.model.update(**update_data).where(
            cls.model.id == source_id
        ).execute() > 0

    @classmethod
    @DB.connection_context()
    def update_statistics(cls, source_id: str, total_articles: int = None, 
                         last_fetch_time: int = None) -> bool:
        """更新统计信息"""
        update_data = {"update_time": current_timestamp(), "update_date": datetime.now()}
        
        if total_articles is not None:
            update_data["total_articles"] = total_articles
        if last_fetch_time is not None:
            update_data["last_fetch_time"] = last_fetch_time
            
        return cls.model.update(**update_data).where(
            cls.model.id == source_id
        ).execute() > 0

    @classmethod
    @DB.connection_context()
    def delete_source(cls, source_id: str, user_id: str) -> bool:
        """删除新闻源（软删除）"""
        return cls.model.update(
            status="deleted",
            update_time=current_timestamp(),
            update_date=datetime.now()
        ).where(
            cls.model.id == source_id,
            cls.model.user_id == user_id
        ).execute() > 0


class NewsTaskService(CommonService):
    """新闻抓取任务服务"""
    model = NewsTask

    @classmethod
    @DB.connection_context()
    def create_task(cls, task_name: str, kb_id: str, source_ids: List[str], 
                   user_id: str, tenant_id: str, auto_parse: bool = True,
                   max_articles_per_source: int = 10) -> NewsTask:
        """创建抓取任务"""
        # 验证知识库是否存在
        success, kb = KnowledgebaseService.get_by_id(kb_id)
        if not success or not kb or kb.tenant_id != tenant_id:
            raise ValueError("知识库不存在或无权限访问")
        
        # 验证新闻源是否存在且属于当前用户
        sources = list(NewsSourceService.model.select().where(
            NewsSourceService.model.id.in_(source_ids),
            NewsSourceService.model.user_id == user_id,
            NewsSourceService.model.tenant_id == tenant_id,
            NewsSourceService.model.status == "active"
        ))
        
        if len(sources) != len(source_ids):
            raise ValueError("部分新闻源不存在或无权限访问")
        
        task_id = get_uuid()
        
        task_data = {
            "id": task_id,
            "task_name": task_name,
            "kb_id": kb_id,
            "user_id": user_id,
            "tenant_id": tenant_id,
            "source_ids": source_ids,
            "auto_parse": auto_parse,
            "max_articles_per_source": max_articles_per_source,
            "status": "pending",
            "statistics": {
                "total_articles": 0,
                "success_count": 0,
                "failed_count": 0,
                "skipped_count": 0
            },
            "create_time": current_timestamp(),
            "create_date": datetime.now(),
            "update_time": current_timestamp(),
            "update_date": datetime.now()
        }
        
        task = cls.model.create(**task_data)
        return task

    @classmethod
    @DB.connection_context()
    def get_by_user(cls, user_id: str, tenant_id: str, status: str = None) -> List[NewsTask]:
        """获取用户的任务列表"""
        query = cls.model.select().where(
            cls.model.user_id == user_id,
            cls.model.tenant_id == tenant_id
        )
        
        if status:
            query = query.where(cls.model.status == status)
            
        return list(query.order_by(cls.model.create_time.desc()))

    @classmethod
    @DB.connection_context()
    def update_task_status(cls, task_id: str, status: str, error_message: str = None,
                          statistics: Dict = None) -> bool:
        """更新任务状态"""
        update_data = {
            "status": status,
            "update_time": current_timestamp(),
            "update_date": datetime.now()
        }
        
        if status == "running":
            update_data["last_run_time"] = current_timestamp()
            
        if error_message is not None:
            update_data["error_message"] = error_message
            
        if statistics is not None:
            update_data["statistics"] = statistics
            
        return cls.model.update(**update_data).where(
            cls.model.id == task_id
        ).execute() > 0

    @classmethod
    @DB.connection_context()
    def get_runnable_tasks(cls) -> List[NewsTask]:
        """获取可运行的任务"""
        return list(cls.model.select().where(
            cls.model.status == "pending"
        ).order_by(cls.model.create_time))


class NewsContentService(CommonService):
    """新闻内容服务"""
    model = NewsContent

    @classmethod
    @DB.connection_context()
    def create_content(cls, task_id: str, source_id: str, title: str, content: str,
                      url: str, user_id: str, tenant_id: str,
                      author: str = None, publish_time: int = None, 
                      summary: str = None, category: str = None,
                      tags: List[str] = None) -> NewsContent:
        """创建新闻内容"""
        content_id = get_uuid()
        
        # 生成内容哈希用于去重
        content_hash = hashlib.md5((title + url).encode('utf-8')).hexdigest()
        
        # 检查是否已存在相同内容
        existing = cls.model.select().where(
            cls.model.content_hash == content_hash,
            cls.model.tenant_id == tenant_id
        ).first()
        
        if existing:
            raise ValueError("内容已存在")
        
        content_data = {
            "id": content_id,
            "task_id": task_id,
            "source_id": source_id,
            "user_id": user_id,
            "tenant_id": tenant_id,
            "original_url": url,
            "author": author,
            "publish_time": publish_time,
            "fetch_time": current_timestamp(),
            "content_hash": content_hash,
            "word_count": len(content) if content else 0,
            "summary": summary,
            "category": category,
            "tags": tags or [],
            "create_time": current_timestamp(),
            "create_date": datetime.now(),
            "update_time": current_timestamp(),
            "update_date": datetime.now()
        }
        
        news = cls.model.create(**content_data)
        return news

    @classmethod
    @DB.connection_context()
    def get_by_user(cls, user_id: str, tenant_id: str, page: int = 1, 
                   page_size: int = 10, source_id: str = None,
                   parsed_only: bool = None) -> tuple:
        """获取用户的新闻内容列表（分页）"""
        query = cls.model.select().where(
            cls.model.user_id == user_id,
            cls.model.tenant_id == tenant_id
        )
        
        if source_id:
            query = query.where(cls.model.source_id == source_id)
            
        if parsed_only is not None:
            if parsed_only:
                # 只获取已解析的（有document_id的）
                query = query.where(cls.model.document_id.is_null(False))
            else:
                # 只获取未解析的（没有document_id的）
                query = query.where(cls.model.document_id.is_null(True))
        
        # 计算总数
        total = query.count()
        
        # 分页查询
        offset = (page - 1) * page_size
        news_list = list(query.order_by(cls.model.create_time.desc())
                        .offset(offset).limit(page_size))
        
        return news_list, total

    @classmethod
    @DB.connection_context()
    def update_document_relation(cls, content_id: str, document_id: str = None) -> bool:
        """更新文档关联（替代原来的parse_status）"""
        update_data = {
            "document_id": document_id,
            "update_time": current_timestamp(),
            "update_date": datetime.now()
        }
            
        return cls.model.update(**update_data).where(
            cls.model.id == content_id
        ).execute() > 0

    @classmethod
    @DB.connection_context()
    def get_statistics(cls, user_id: str, tenant_id: str) -> Dict[str, int]:
        """获取统计信息"""
        # 总内容数
        total_content = cls.model.select().where(
            cls.model.user_id == user_id,
            cls.model.tenant_id == tenant_id
        ).count()
        
        # 已解析数（有document_id的表示已转换为文档）
        parsed_count = cls.model.select().where(
            cls.model.user_id == user_id,
            cls.model.tenant_id == tenant_id,
            cls.model.document_id.is_null(False)
        ).count()
        
        # 待解析数（没有document_id的表示待处理）
        pending_count = cls.model.select().where(
            cls.model.user_id == user_id,
            cls.model.tenant_id == tenant_id,
            cls.model.document_id.is_null(True)
        ).count()
        
        return {
            "total_content": total_content,
            "parsed_count": parsed_count,
            "pending_count": pending_count
        }
