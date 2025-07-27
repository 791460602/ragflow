#
#  Copyright 2024 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
import re
import traceback
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any

from api.db import LLMType, StatusEnum
from api.db.db_models import NewsSource, NewsTask, NewsContent, Knowledgebase, Document
from api.db.services.common_service import CommonService
from api.db.services.document_service import DocumentService
from api.db.services.knowledgebase_service import KnowledgebaseService
from api.utils import get_uuid
from api.db.db_models import DB


class NewsSourceService(CommonService):
    model = NewsSource

    @classmethod
    @DB.connection_context()
    def get_by_tenant_id(cls, tenant_id: str, page: int = 1, page_size: int = 20, 
                        name: Optional[str] = None, status: Optional[str] = None):
        """根据租户ID获取新闻源列表"""
        query = cls.model.select().where(cls.model.tenant_id == tenant_id)
        
        if name:
            query = query.where(cls.model.name.contains(name))
        if status:
            query = query.where(cls.model.status == status)
            
        query = query.order_by(cls.model.create_time.desc())
        
        # 分页
        total = query.count()
        sources = query.paginate(page, page_size)
        
        return [cls.to_dict(source) for source in sources], total

    @classmethod
    @DB.connection_context()
    def create_source(cls, tenant_id: str, user_id: Optional[str] = None, **kwargs):
        """创建新闻源"""
        source_id = kwargs.get('id', get_uuid())
        
        # 如果没有提供user_id，使用tenant_id作为默认值
        if user_id is None:
            user_id = tenant_id
        
        source_data = {
            'id': source_id,
            'tenant_id': tenant_id,
            'user_id': user_id,
            'name': kwargs.get('name'),
            'url': kwargs.get('url'),
            'remark': kwargs.get('remark', ''),
            'status': kwargs.get('status', 'active'),
            'fetch_config': kwargs.get('fetch_config', {})
        }
        
        source = cls.model.create(**source_data)
        return cls.to_dict(source)

    @classmethod
    @DB.connection_context()
    def update_source(cls, source_id: str, tenant_id: str, **kwargs):
        """更新新闻源"""
        source = cls.model.select().where(cls.model.id == source_id).first()
        if not source or source.tenant_id != tenant_id:
            raise ValueError("News source not found")
            
        update_data = {}
        for field in ['name', 'url', 'remark', 'status', 'fetch_config']:
            if field in kwargs:
                update_data[field] = kwargs[field]
                
        if update_data:
            cls.model.update(**update_data).where(
                cls.model.id == source_id
            ).execute()
            
        return cls.to_dict(cls.model.select().where(cls.model.id == source_id).first())

    @classmethod
    @DB.connection_context()
    def update_statistics(cls, source_id: str, **stats):
        """更新新闻源统计信息"""
        update_data = {}
        if 'total_articles' in stats:
            update_data['total_articles'] = stats['total_articles']
        if 'last_fetch_time' in stats:
            update_data['last_fetch_time'] = stats['last_fetch_time']
            
        if update_data:
            cls.model.update(**update_data).where(
                cls.model.id == source_id
            ).execute()

    @classmethod
    def to_dict(cls, obj):
        """转换为字典"""
        if not obj:
            return None
            
        # 直接从模型对象创建字典
        result = {}
        for field_name in obj._meta.fields.keys():
            field_value = getattr(obj, field_name, None)
            result[field_name] = field_value
        
        # 添加时间戳字段
        if hasattr(obj, 'create_time') and obj.create_time:
            result['create_time'] = obj.create_time.isoformat() if hasattr(obj.create_time, 'isoformat') else str(obj.create_time)
        if hasattr(obj, 'update_time') and obj.update_time:
            result['update_time'] = obj.update_time.isoformat() if hasattr(obj.update_time, 'isoformat') else str(obj.update_time)
            
        # 确保JSON字段正确序列化
        if hasattr(obj, 'fetch_config') and obj.fetch_config:
            result['fetch_config'] = obj.fetch_config
        else:
            result['fetch_config'] = {}
            
        return result


class NewsTaskService(CommonService):
    model = NewsTask

    @classmethod
    @DB.connection_context()
    def get_by_tenant_id(cls, tenant_id: str, page: int = 1, page_size: int = 20,
                        task_name: Optional[str] = None, status: Optional[str] = None):
        """根据租户ID获取任务列表"""
        query = cls.model.select().where(cls.model.tenant_id == tenant_id)
        
        if task_name:
            query = query.where(cls.model.task_name.contains(task_name))
        if status:
            query = query.where(cls.model.status == status)
            
        query = query.order_by(cls.model.create_time.desc())
        
        # 分页
        total = query.count()
        tasks = query.paginate(page, page_size)
        
        return [cls.to_dict(task) for task in tasks], total

    @classmethod
    @DB.connection_context()
    def create_task(cls, tenant_id: str, user_id: Optional[str] = None, **kwargs):
        """创建新闻抓取任务"""
        # 验证知识库是否存在
        kb_id = kwargs.get('kb_id')
        if kb_id:
            success, kb = KnowledgebaseService.get_by_id(kb_id)
            if not success or not kb:
                raise ValueError("Knowledge base not found")
            
        task_id = kwargs.get('id', get_uuid())
        
        # 如果没有提供user_id，使用tenant_id作为默认值
        if user_id is None:
            user_id = tenant_id
        
        task_data = {
            'id': task_id,
            'tenant_id': tenant_id,
            'user_id': user_id,
            'task_name': kwargs.get('task_name'),
            'kb_id': kb_id,
            'source_ids': kwargs.get('source_ids', []),
            'auto_parse': kwargs.get('auto_parse', True),
            'max_articles_per_source': kwargs.get('max_articles_per_source', 10),
            'crawler_config': kwargs.get('crawler_config', {
                'type': 'demo',
                'timeout': 300,
                'output_format': 'markdown'
            }),
            'status': 'pending'
        }
        
        task = cls.model.create(**task_data)
        return cls.to_dict(task)

    @classmethod
    @DB.connection_context()
    def update_task(cls, task_id: str, tenant_id: str, **kwargs):
        """更新任务"""
        task = cls.model.select().where(cls.model.id == task_id).first()
        if not task or task.tenant_id != tenant_id:
            raise ValueError("Task not found")
            
        update_data = {}
        for field in ['task_name', 'source_ids', 'auto_parse', 
                     'max_articles_per_source', 'crawler_config']:
            if field in kwargs:
                update_data[field] = kwargs[field]
                
        if update_data:
            cls.model.update(**update_data).where(
                cls.model.id == task_id
            ).execute()
            
        return cls.to_dict(cls.model.select().where(cls.model.id == task_id).first())

    @classmethod
    @DB.connection_context()
    def update_task_status(cls, task_id: str, status: str, **kwargs):
        """更新任务状态"""
        update_data = {'status': status}
        
        if 'last_run_time' in kwargs:
            update_data['last_run_time'] = kwargs['last_run_time']
        if 'statistics' in kwargs:
            update_data['statistics'] = kwargs['statistics']
        if 'error_message' in kwargs:
            update_data['error_message'] = kwargs['error_message']
            
        cls.model.update(**update_data).where(
            cls.model.id == task_id
        ).execute()

    @classmethod
    @DB.connection_context()
    def get_pending_tasks(cls, limit: int = 10):
        """获取待执行的任务"""
        tasks = cls.model.select().where(
            cls.model.status == 'pending'
        ).limit(limit)
        
        return [cls.to_dict(task) for task in tasks]

    @classmethod
    def to_dict(cls, obj):
        """转换为字典"""
        if not obj:
            return None
            
        # 直接从模型对象创建字典
        result = {}
        for field_name in obj._meta.fields.keys():
            field_value = getattr(obj, field_name, None)
            result[field_name] = field_value
        
        # 添加时间戳字段
        if hasattr(obj, 'create_time') and obj.create_time:
            result['create_time'] = obj.create_time.isoformat() if hasattr(obj.create_time, 'isoformat') else str(obj.create_time)
        if hasattr(obj, 'update_time') and obj.update_time:
            result['update_time'] = obj.update_time.isoformat() if hasattr(obj.update_time, 'isoformat') else str(obj.update_time)
        
        # 确保JSON字段正确序列化
        if hasattr(obj, 'source_ids') and obj.source_ids:
            result['source_ids'] = obj.source_ids
        else:
            result['source_ids'] = []
            
        if hasattr(obj, 'crawler_config') and obj.crawler_config:
            result['crawler_config'] = obj.crawler_config
        else:
            result['crawler_config'] = {}
            
        if hasattr(obj, 'statistics') and obj.statistics:
            result['statistics'] = obj.statistics
        else:
            result['statistics'] = {
                'total_articles': 0,
                'success_count': 0,
                'failed_count': 0,
                'skipped_count': 0
            }
            
        return result


class NewsContentService(CommonService):
    model = NewsContent

    @classmethod
    @DB.connection_context()
    def get_by_task_id(cls, task_id: str, page: int = 1, page_size: int = 20):
        """根据任务ID获取新闻内容"""
        query = cls.model.select().where(cls.model.task_id == task_id)
        query = query.order_by(cls.model.fetch_time.desc())
        
        total = query.count()
        contents = query.paginate(page, page_size)
        
        return [cls.to_dict(content) for content in contents], total

    @classmethod
    @DB.connection_context()
    def get_by_source_id(cls, source_id: str, page: int = 1, page_size: int = 20):
        """根据新闻源ID获取内容"""
        query = cls.model.select().where(cls.model.source_id == source_id)
        query = query.order_by(cls.model.fetch_time.desc())
        
        total = query.count()
        contents = query.paginate(page, page_size)
        
        return [cls.to_dict(content) for content in contents], total

    @classmethod
    @DB.connection_context()
    def create_content(cls, tenant_id: str, user_id: Optional[str] = None, **kwargs):
        """创建新闻内容"""
        content_id = kwargs.get('id', get_uuid())
        
        # 如果没有提供user_id，使用tenant_id作为默认值
        if user_id is None:
            user_id = tenant_id
        
        content_data = {
            'id': content_id,
            'tenant_id': tenant_id,
            'user_id': user_id,
            'task_id': kwargs.get('task_id'),
            'source_id': kwargs.get('source_id'),
            'document_id': kwargs.get('document_id'),
            'original_url': kwargs.get('original_url'),
            'author': kwargs.get('author'),
            'publish_time': kwargs.get('publish_time'),
            'fetch_time': kwargs.get('fetch_time', int(datetime.now().timestamp() * 1000)),
            'category': kwargs.get('category'),
            'tags': kwargs.get('tags', []),
            'summary': kwargs.get('summary'),
            'content_hash': kwargs.get('content_hash'),
            'word_count': kwargs.get('word_count', 0)
        }
        
        content = cls.model.create(**content_data)
        return cls.to_dict(content)

    @classmethod
    @DB.connection_context()
    def get_statistics_by_time_range(cls, tenant_id: str, start_time: int, end_time: int):
        """获取时间范围内的统计数据"""
        query = cls.model.select().where(
            (cls.model.tenant_id == tenant_id) &
            (cls.model.fetch_time >= start_time) &
            (cls.model.fetch_time <= end_time)
        )
        
        total_count = query.count()
        
        # 按新闻源统计
        source_stats = {}
        for content in query:
            source_id = content.source_id
            if source_id not in source_stats:
                source_stats[source_id] = 0
            source_stats[source_id] += 1
            
        return {
            'total_articles': total_count,
            'source_distribution': source_stats,
            'time_range': {
                'start': start_time,
                'end': end_time
            }
        }

    @classmethod
    @DB.connection_context()
    def check_duplicate(cls, content_hash: str) -> bool:
        """检查内容是否重复"""
        exists = cls.model.select().where(
            cls.model.content_hash == content_hash
        ).exists()
        return exists

    @classmethod
    def to_dict(cls, obj):
        """转换为字典"""
        if not obj:
            return None
            
        # 直接从模型对象创建字典
        result = {}
        for field_name in obj._meta.fields.keys():
            field_value = getattr(obj, field_name, None)
            result[field_name] = field_value
        
        # 添加时间戳字段
        if hasattr(obj, 'create_time') and obj.create_time:
            result['create_time'] = obj.create_time.isoformat() if hasattr(obj.create_time, 'isoformat') else str(obj.create_time)
        if hasattr(obj, 'update_time') and obj.update_time:
            result['update_time'] = obj.update_time.isoformat() if hasattr(obj.update_time, 'isoformat') else str(obj.update_time)
        
        # 确保JSON字段正确序列化
        if hasattr(obj, 'tags') and obj.tags:
            result['tags'] = obj.tags
        else:
            result['tags'] = []
            
        return result
