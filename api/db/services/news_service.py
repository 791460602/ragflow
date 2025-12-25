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

from common.constants import LLMType, StatusEnum
from api.db.db_models import NewsSource, NewsTask, NewsContent, Knowledgebase, Document
from api.db.services.common_service import CommonService
from api.db.services.document_service import DocumentService
from api.db.services.knowledgebase_service import KnowledgebaseService
from common.misc_utils import get_uuid
from api.db.db_models import DB
# 新增: 导入 hashlib 用于生成内容哈希值
import hashlib
import json
from datetime import datetime  # <--- 确保文件顶部有这行导入语句


class NewsSourceService(CommonService):
    model = NewsSource

    @classmethod
    @DB.connection_context()
    def get_by_tenant_id(cls, tenant_id: str, page: int = 1, page_size: int = 20, 
                        name: Optional[str] = None, status: Optional[str] = None, source_type: Optional[str] = None,
                        source_types: Optional[List[str]] = None):
        """根据租户ID获取新闻源列表"""
        
        # 修改: 默认查询条件增加了 status != 'deleted'
        query = cls.model.select().where(
            (cls.model.tenant_id == tenant_id) & 
            (cls.model.status != 'deleted')
        )
        
        if name:
            query = query.where(cls.model.name.contains(name))
        
        # 修改: 如果外部传入了 status 参数，则使用外部的，否则默认不显示 deleted
        if status:
            query = query.where(cls.model.status == status)
        if source_types:
            query = query.where(cls.model.source_type.in_(source_types))
        elif source_type:
            query = query.where(cls.model.source_type == source_type)
            
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

        st = kwargs.get('source_type', 'unknown')        

        policy_theme = kwargs.get('policy_theme', [])
        if isinstance(policy_theme, str):
            try:
                policy_theme = json.loads(policy_theme)
            except Exception:
                # 单字符串视为单元素列表
                policy_theme = [policy_theme]
        if policy_theme is None:
            policy_theme = []
        if not isinstance(policy_theme, list):
            raise ValueError("policy_theme must be a list")

        region = kwargs.get('region')
        if region is not None and not isinstance(region, str):
            raise ValueError("region must be a string")

        issuer = kwargs.get('issuer')
        if issuer is not None and not isinstance(issuer, str):
            raise ValueError("issuer must be a string")

        source_data = {
            'id': source_id,
            'tenant_id': tenant_id,
            'user_id': user_id,
            'name': kwargs.get('name'),
            'url': kwargs.get('url'),
            'remark': kwargs.get('remark', ''),
            'status': kwargs.get('status', 'active'),
            'fetch_config': kwargs.get('fetch_config', {}),
            'source_type': st,
            'region': region,
            'issuer': issuer,
            'policy_theme': policy_theme
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
            
        # 如果传入需要更新的字段, 做基本校验
        update_data = {}
        allowed_types = {"policy", "news", "other"}
        if 'source_type' in kwargs:
            st = kwargs.get('source_type')
            if st not in allowed_types:
                raise ValueError(f"Invalid source_type: {st}. Allowed: {sorted(list(allowed_types))}")
            update_data['source_type'] = st

        if 'policy_theme' in kwargs:
            pt = kwargs.get('policy_theme')
            if isinstance(pt, str):
                try:
                    pt = json.loads(pt)
                except Exception:
                    pt = [pt]
            if pt is None:
                pt = []
            if not isinstance(pt, list):
                raise ValueError("policy_theme must be a list")
            update_data['policy_theme'] = pt

        if 'region' in kwargs:
            if kwargs.get('region') is not None and not isinstance(kwargs.get('region'), str):
                raise ValueError("region must be a string")
            update_data['region'] = kwargs.get('region')

        if 'issuer' in kwargs:
            if kwargs.get('issuer') is not None and not isinstance(kwargs.get('issuer'), str):
                raise ValueError("issuer must be a string")
            update_data['issuer'] = kwargs.get('issuer')

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

    @classmethod
    @DB.connection_context()
    def get_by_types(cls, tenant_id: str, source_types: List[str]) -> List[dict]:
        if not source_types:
            return []
        query = cls.model.select().where(
            (cls.model.tenant_id == tenant_id) &
            (cls.model.status != 'deleted') &
            (cls.model.source_type.in_(source_types))
        )
        return [cls.to_dict(source) for source in query]


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

    # =================================================================
    # START OF MODIFICATIONS - 重写 create_content 方法
    # =================================================================
    @classmethod
    @DB.connection_context()
    def create_content(cls, tenant_id: str, task_id: str, source_id: str, article_data: Dict[str, Any], user_id: Optional[str] = None, kb_id: Optional[str] = None):
        """
        创建一条新的新闻内容记录并存入数据库。
        重写后包含基于URL和内容哈希的去重检查，以及完整的错误处理。

        :param tenant_id: 租户ID
        :param task_id: 关联的任务ID
        :param source_id: 关联的新闻源ID
        :param article_data: 包含新闻信息的字典，来自爬虫
        :param user_id: 创建者用户ID (可选)
        :return: 创建的 NewsContent 对象或在重复/失败时返回 None
        """
        original_url = article_data.get("url")
        if not original_url:
            print("[DB Service] 错误：文章数据缺少 'url'，无法创建记录。")
            return None

        content_text = article_data.get("content", "")

        # 修改: 增加对 content_text 本身是否为 None 的检查
        if not content_text or not content_text.strip():
            print(f"[DB Service] 跳过：URL '{original_url}' 的内容为空或None。")
            return None
        # 如果内容为空，则不进行存储
        if not content_text.strip():
            print(f"[DB Service] 跳过：URL '{original_url}' 的内容为空。")
            return None
        
        try:
            # 1. 基于 URL 的去重检查
            if cls.model.select().where(cls.model.original_url == original_url).exists():
                print(f"[DB Service] 跳过：URL '{original_url}' 已存在于数据库中。")
                return None
            
            # 2. 基于内容哈希的去重检查
            content_hash = hashlib.sha256(content_text.encode('utf-8')).hexdigest()
            if cls.check_duplicate(content_hash):
                print(f"[DB Service] 跳过：内容哈希值重复 (URL: {original_url})。")
                return None

            # 如果提供了目标知识库 ID，尝试创建一个最小化的 Document 记录
            document_id = None
            if kb_id:
                try:
                    kb_ok, kb = KnowledgebaseService.get_by_id(kb_id)
                    if kb:
                        doc_id = get_uuid()
                        # 生成安全的文档名
                        title = (article_data.get("title") or "").strip()
                        if not title:
                            try:
                                u = (article_data.get("url") or "").strip()
                                if u:
                                    from urllib.parse import urlparse

                                    parsed = urlparse(u)
                                    last_seg = (parsed.path or "").rstrip("/").split("/")[-1]
                                    title = last_seg or parsed.netloc
                            except Exception:
                                title = ""
                        if not title:
                            title = "untitled"
                        sanitized_title = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff_\-\.]", "_", title)[:100]
                        if not sanitized_title.strip("_."):
                            sanitized_title = f"untitled_{datetime.now().strftime('%Y%m%d%H%M%S')}"
                        doc_name = f"{sanitized_title}.json"
                        doc_data = {
                            'id': doc_id,
                            'kb_id': kb_id,
                            'parser_id': kb.parser_id,
                            'parser_config': kb.parser_config,
                            'created_by': tenant_id,
                            'type': 'json',
                            'name': doc_name,
                            'suffix': 'json',
                            'location': '',
                            'size': len(content_text),
                            'source_type': 'local',
                            'tenant_id': tenant_id,
                        }
                        try:
                            doc = DocumentService.insert(doc_data)
                            document_id = getattr(doc, 'id', None)
                        except Exception:
                            # 如果文档插入失败，不阻塞新闻内容的写入
                            document_id = None
                except Exception:
                    document_id = None

            # 准备要插入数据库的数据
            content_data = {
                'id': get_uuid(),
                'tenant_id': tenant_id,
                'user_id': user_id or tenant_id, # 如果user_id未提供，则使用tenant_id作为后备
                'task_id': task_id,
                'source_id': source_id,
                'document_id': document_id,
                'original_url': original_url,
                'title': article_data.get("title", "无标题"),
                'content': content_text,
                'author': article_data.get("author"),
                'publish_time': article_data.get("publication_time"), # 键名来自RecursiveCrawl4AI
                'fetch_time': int(datetime.now().timestamp() * 1000),
                'category': article_data.get("category"),
                'tags': article_data.get("tags", []),
                'summary': article_data.get("summary"),
                'content_hash': content_hash,
                'word_count': len(content_text)
            }
            
            # 3. 创建记录
            new_content = cls.model.create(**content_data)
            print(f"[DB Service] 成功插入记录，URL: {original_url}")
            return cls.to_dict(new_content)

        except Exception as e:
            # 4. 统一的错误处理
            print(f"[DB Service] 数据库操作失败，URL: {original_url}")
            traceback.print_exc()
            return None
    # =================================================================
    # END OF MODIFICATIONS
    # =================================================================

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
        if not content_hash:
            return False
        return cls.model.select().where(
            cls.model.content_hash == content_hash
        ).exists()

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
    
    # vvvvvvvvvv 在此处添加这个新方法 vvvvvvvvvv
    @classmethod
    @DB.connection_context()
    def get_all_content_hashes(cls, tenant_id: str) -> set:
        """高效获取指定租户的所有内容哈希值"""
        query = cls.model.select(cls.model.content_hash).where(
            (cls.model.tenant_id == tenant_id) &
            (cls.model.content_hash.is_null(False))
        )
        return {item.content_hash for item in query}
    # ^^^^^^^^^^^ 添加结束 ^^^^^^^^^^^

    # vvvvvvvvvv 在此处添加这两个新方法 vvvvvvvvvv
    @classmethod
    @DB.connection_context()
    def get_hashes_paginated(cls, tenant_id: str, page: int = 1, page_size: int = 20):
        """(最终修正版) 分页获取内容的简略信息"""
        query = cls.model.select()\
            .where(cls.model.tenant_id == tenant_id)\
            .order_by(cls.model.create_time.desc())

        total = query.count()
        records = query.paginate(page, page_size)

        result = []
        for record in records:
            create_time_iso = None
            # 检查 create_time 是否存在且为整数
            if hasattr(record, 'create_time') and isinstance(record.create_time, int):
                try:
                    # 将毫秒时间戳除以1000转换为秒，然后创建datetime对象
                    dt_object = datetime.fromtimestamp(record.create_time / 1000)
                    create_time_iso = dt_object.isoformat()
                except Exception:
                    # 如果转换失败，则保持为None
                    create_time_iso = str(record.create_time) # fallback to string

            result.append({
                "id": getattr(record, 'id', None),
                "title": getattr(record, 'title', 'No Title'),
                "content_hash": getattr(record, 'content_hash', None),
                "create_time": create_time_iso
            })
            
        return result, total


    @classmethod
    @DB.connection_context()
    def delete_by_tenant_id(cls, tenant_id: str) -> int:
        """根据租户ID删除所有内容记录"""
        query = cls.model.delete().where(cls.model.tenant_id == tenant_id)
        deleted_rows = query.execute()
        return deleted_rows
    # ^^^^^^^^^^^ 添加结束 ^^^^^^^^^^^
