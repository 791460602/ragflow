"""
新闻抓取系统数据库服务层

使用RAGFlow的数据库连接和模型，替换内存存储
"""

import asyncio
import threading
import hashlib
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging

# 导入本包内的模块
from .models import (
    NewsSource as NewsSourceModel, NewsTask as NewsTaskModel, 
    NewsContent as NewsContentModel, KnowledgeBase,
    TaskStatus, SelectorConfig, ParseStatus
)
from .manager import NewsManager
from .scraper import NewsScraper

# 导入数据库模型
from .db_models import (
    NewsSource, NewsTask, NewsContent, NewsKnowledgeBase, NewsHistory,
    NewsSourceStatus, TaskStatus as DBTaskStatus, ParseStatus as DBParseStatus,
    create_news_tables
)

# 导入RAGFlow的数据库连接
from api.db.db_models import DB
from api.utils import current_timestamp, timestamp_to_date, get_uuid

logger = logging.getLogger(__name__)

# 全局新闻管理器（需要在初始化时设置RAGFlow客户端）
_news_manager: Optional[NewsManager] = None

# 状态映射
STATUS_MAPPING = {
    # NewsSource状态映射
    "active": NewsSourceStatus.ACTIVE.value,
    "inactive": NewsSourceStatus.INACTIVE.value,
    "disabled": NewsSourceStatus.DISABLED.value,
    
    # Task状态映射
    TaskStatus.PENDING: DBTaskStatus.PENDING.value,
    TaskStatus.RUNNING: DBTaskStatus.RUNNING.value,
    TaskStatus.COMPLETED: DBTaskStatus.COMPLETED.value,
    TaskStatus.FAILED: DBTaskStatus.FAILED.value,
    
    # Parse状态映射
    ParseStatus.PENDING: DBParseStatus.PENDING.value,
    ParseStatus.PARSING: DBParseStatus.PARSING.value,
    ParseStatus.PARSED: DBParseStatus.PARSED.value,
    ParseStatus.FAILED: DBParseStatus.FAILED.value,
}


def initialize_news_manager(ragflow_client):
    """初始化新闻管理器"""
    global _news_manager
    _news_manager = NewsManager(ragflow_client)
    
    # 确保数据库表存在
    try:
        create_news_tables()
        logger.info("News collector database tables ensured")
    except Exception as e:
        logger.warning(f"Failed to create news collector tables: {e}")
    
    logger.info("News manager initialized with RAGFlow client")


def get_news_manager() -> Optional[NewsManager]:
    """获取新闻管理器实例"""
    return _news_manager


def _generate_content_fingerprint(title: str, url: str, content: str) -> str:
    """生成内容指纹用于去重"""
    content_str = f"{title}|{url}|{content[:1000]}"  # 使用标题、URL和前1000字符
    return hashlib.sha256(content_str.encode('utf-8')).hexdigest()


# === 知识库管理 ===

@DB.connection_context()
def get_knowledge_bases() -> List[Dict[str, Any]]:
    """获取所有知识库列表"""
    try:
        kbs = NewsKnowledgeBase.select()
        return [
            {
                "id": kb.f_kb_id,
                "name": kb.f_kb_name,
                "description": kb.f_description,
                "created_at": timestamp_to_date(kb.f_create_time).isoformat(),
                "status": "active",
                "total_articles": kb.f_total_articles,
                "parsed_articles": kb.f_parsed_articles
            }
            for kb in kbs
        ]
    except Exception as e:
        logger.error(f"Failed to get knowledge bases: {e}")
        return []


@DB.connection_context()
def get_knowledge_base(kb_id: str) -> Optional[Dict[str, Any]]:
    """获取单个知识库详情"""
    try:
        kb = NewsKnowledgeBase.get(NewsKnowledgeBase.f_kb_id == kb_id)
        return {
            "id": kb.f_kb_id,
            "name": kb.f_kb_name,
            "description": kb.f_description,
            "created_at": timestamp_to_date(kb.f_create_time).isoformat(),
            "status": "active",
            "total_articles": kb.f_total_articles,
            "parsed_articles": kb.f_parsed_articles
        }
    except NewsKnowledgeBase.DoesNotExist:
        return None
    except Exception as e:
        logger.error(f"Failed to get knowledge base {kb_id}: {e}")
        return None


@DB.connection_context()
def create_knowledge_base(data: Dict[str, Any]) -> Dict[str, Any]:
    """创建知识库"""
    try:
        current_time = current_timestamp()
        
        kb = NewsKnowledgeBase.create(
            f_id=get_uuid(),
            f_kb_id=data["id"],
            f_kb_name=data["name"],
            f_description=data.get("description", ""),
            f_auto_parse=data.get("auto_parse", True),
            f_parse_method=data.get("parse_method", "naive"),
            f_create_time=current_time,
            f_create_date=timestamp_to_date(current_time),
            f_update_time=current_time,
            f_update_date=timestamp_to_date(current_time)
        )
        
        return {
            "id": kb.f_kb_id,
            "name": kb.f_kb_name,
            "description": kb.f_description,
            "created_at": timestamp_to_date(kb.f_create_time).isoformat(),
            "status": "active",
            "total_articles": kb.f_total_articles,
            "parsed_articles": kb.f_parsed_articles
        }
    except Exception as e:
        logger.error(f"Failed to create knowledge base: {e}")
        raise


# === 新闻源管理 ===

@DB.connection_context()
def get_news_sources(page: int = 1, page_size: int = 10) -> Dict[str, Any]:
    """获取新闻源列表（分页）"""
    try:
        query = NewsSource.select().order_by(NewsSource.f_create_time.desc())
        total = query.count()
        
        offset = (page - 1) * page_size
        sources = query.offset(offset).limit(page_size)
        
        return {
            "data": [
                {
                    "id": source.f_id,
                    "name": source.f_name,
                    "url": source.f_url,
                    "remark": source.f_remark,
                    "status": source.f_status,
                    "created_at": timestamp_to_date(source.f_create_time).isoformat(),
                    "updated_at": timestamp_to_date(source.f_update_time).isoformat(),
                    "selector_config": source.f_selector_config,
                    "last_crawl_time": timestamp_to_date(source.f_last_crawl_time).isoformat() if source.f_last_crawl_time else None,
                    "total_articles": source.f_total_articles,
                    "success_count": source.f_success_count,
                    "failure_count": source.f_failure_count
                }
                for source in sources
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }
    except Exception as e:
        logger.error(f"Failed to get news sources: {e}")
        return {"data": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 0}


@DB.connection_context()
def get_news_source(source_id: str) -> Optional[Dict[str, Any]]:
    """获取单个新闻源详情"""
    try:
        source = NewsSource.get(NewsSource.f_id == source_id)
        return {
            "id": source.f_id,
            "name": source.f_name,
            "url": source.f_url,
            "remark": source.f_remark,
            "status": source.f_status,
            "created_at": timestamp_to_date(source.f_create_time).isoformat(),
            "updated_at": timestamp_to_date(source.f_update_time).isoformat(),
            "selector_config": source.f_selector_config,
            "last_crawl_time": timestamp_to_date(source.f_last_crawl_time).isoformat() if source.f_last_crawl_time else None,
            "total_articles": source.f_total_articles,
            "success_count": source.f_success_count,
            "failure_count": source.f_failure_count
        }
    except NewsSource.DoesNotExist:
        return None
    except Exception as e:
        logger.error(f"Failed to get news source {source_id}: {e}")
        return None


@DB.connection_context()
def create_news_source(data: Dict[str, Any]) -> Dict[str, Any]:
    """创建新闻源"""
    try:
        current_time = current_timestamp()
        source_id = get_uuid()
        
        source = NewsSource.create(
            f_id=source_id,
            f_name=data["name"],
            f_url=data["url"],
            f_remark=data.get("remark", ""),
            f_status=STATUS_MAPPING.get(data.get("status", "active"), NewsSourceStatus.ACTIVE.value),
            f_selector_config=data.get("selector_config", {}),
            f_create_time=current_time,
            f_create_date=timestamp_to_date(current_time),
            f_update_time=current_time,
            f_update_date=timestamp_to_date(current_time)
        )
        
        return {
            "id": source.f_id,
            "name": source.f_name,
            "url": source.f_url,
            "remark": source.f_remark,
            "status": source.f_status,
            "created_at": timestamp_to_date(source.f_create_time).isoformat(),
            "updated_at": timestamp_to_date(source.f_update_time).isoformat(),
            "selector_config": source.f_selector_config,
            "total_articles": source.f_total_articles,
            "success_count": source.f_success_count,
            "failure_count": source.f_failure_count
        }
    except Exception as e:
        logger.error(f"Failed to create news source: {e}")
        raise


@DB.connection_context()
def update_news_source(source_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """更新新闻源"""
    try:
        source = NewsSource.get(NewsSource.f_id == source_id)
        
        # 更新字段
        if "name" in data:
            source.f_name = data["name"]
        if "url" in data:
            source.f_url = data["url"]
        if "remark" in data:
            source.f_remark = data["remark"]
        if "status" in data:
            source.f_status = STATUS_MAPPING.get(data["status"], data["status"])
        if "selector_config" in data:
            source.f_selector_config = data["selector_config"]
        
        source.f_update_time = current_timestamp()
        source.f_update_date = timestamp_to_date(source.f_update_time)
        source.save()
        
        return {
            "id": source.f_id,
            "name": source.f_name,
            "url": source.f_url,
            "remark": source.f_remark,
            "status": source.f_status,
            "created_at": timestamp_to_date(source.f_create_time).isoformat(),
            "updated_at": timestamp_to_date(source.f_update_time).isoformat(),
            "selector_config": source.f_selector_config,
            "total_articles": source.f_total_articles,
            "success_count": source.f_success_count,
            "failure_count": source.f_failure_count
        }
    except NewsSource.DoesNotExist:
        return None
    except Exception as e:
        logger.error(f"Failed to update news source {source_id}: {e}")
        raise


@DB.connection_context()
def delete_news_source(source_id: str) -> bool:
    """删除新闻源"""
    try:
        deleted = NewsSource.delete().where(NewsSource.f_id == source_id).execute()
        return deleted > 0
    except Exception as e:
        logger.error(f"Failed to delete news source {source_id}: {e}")
        return False


# === 抓取任务管理 ===

@DB.connection_context()
def get_news_tasks(page: int = 1, page_size: int = 10) -> Dict[str, Any]:
    """获取抓取任务列表（分页）"""
    try:
        query = NewsTask.select().order_by(NewsTask.f_create_time.desc())
        total = query.count()
        
        offset = (page - 1) * page_size
        tasks = query.offset(offset).limit(page_size)
        
        return {
            "data": [
                {
                    "id": task.f_id,
                    "task_name": task.f_task_name,
                    "kb_id": task.f_kb_id,
                    "source_ids": task.f_source_ids,
                    "status": task.f_status,
                    "auto_parse": task.f_auto_parse,
                    "max_articles_per_source": task.f_max_articles_per_source,
                    "created_at": timestamp_to_date(task.f_create_time).isoformat(),
                    "updated_at": timestamp_to_date(task.f_update_time).isoformat(),
                    "last_run_at": timestamp_to_date(task.f_last_run_time).isoformat() if task.f_last_run_time else None,
                    "next_run_at": timestamp_to_date(task.f_next_run_time).isoformat() if task.f_next_run_time else None,
                    "statistics": task.f_statistics,
                    "schedule_config": task.f_schedule_config
                }
                for task in tasks
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }
    except Exception as e:
        logger.error(f"Failed to get news tasks: {e}")
        return {"data": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 0}


@DB.connection_context()
def get_news_task(task_id: str) -> Optional[Dict[str, Any]]:
    """获取单个抓取任务详情"""
    try:
        task = NewsTask.get(NewsTask.f_id == task_id)
        return {
            "id": task.f_id,
            "task_name": task.f_task_name,
            "kb_id": task.f_kb_id,
            "source_ids": task.f_source_ids,
            "status": task.f_status,
            "auto_parse": task.f_auto_parse,
            "max_articles_per_source": task.f_max_articles_per_source,
            "created_at": timestamp_to_date(task.f_create_time).isoformat(),
            "updated_at": timestamp_to_date(task.f_update_time).isoformat(),
            "last_run_at": timestamp_to_date(task.f_last_run_time).isoformat() if task.f_last_run_time else None,
            "next_run_at": timestamp_to_date(task.f_next_run_time).isoformat() if task.f_next_run_time else None,
            "statistics": task.f_statistics,
            "schedule_config": task.f_schedule_config
        }
    except NewsTask.DoesNotExist:
        return None
    except Exception as e:
        logger.error(f"Failed to get news task {task_id}: {e}")
        return None


@DB.connection_context()
def create_news_task(data: Dict[str, Any]) -> Dict[str, Any]:
    """创建抓取任务"""
    try:
        current_time = current_timestamp()
        task_id = get_uuid()
        
        task = NewsTask.create(
            f_id=task_id,
            f_task_name=data["task_name"],
            f_kb_id=data["kb_id"],
            f_source_ids=data["source_ids"],
            f_status=DBTaskStatus.PENDING.value,
            f_auto_parse=data.get("auto_parse", True),
            f_max_articles_per_source=data.get("max_articles_per_source", 10),
            f_schedule_config=data.get("schedule_config", {}),
            f_create_time=current_time,
            f_create_date=timestamp_to_date(current_time),
            f_update_time=current_time,
            f_update_date=timestamp_to_date(current_time)
        )
        
        return {
            "id": task.f_id,
            "task_name": task.f_task_name,
            "kb_id": task.f_kb_id,
            "source_ids": task.f_source_ids,
            "status": task.f_status,
            "auto_parse": task.f_auto_parse,
            "max_articles_per_source": task.f_max_articles_per_source,
            "created_at": timestamp_to_date(task.f_create_time).isoformat(),
            "updated_at": timestamp_to_date(task.f_update_time).isoformat(),
            "statistics": task.f_statistics,
            "schedule_config": task.f_schedule_config
        }
    except Exception as e:
        logger.error(f"Failed to create news task: {e}")
        raise


@DB.connection_context()
def update_news_task(task_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """更新抓取任务"""
    try:
        task = NewsTask.get(NewsTask.f_id == task_id)
        
        # 更新字段
        if "task_name" in data:
            task.f_task_name = data["task_name"]
        if "kb_id" in data:
            task.f_kb_id = data["kb_id"]
        if "source_ids" in data:
            task.f_source_ids = data["source_ids"]
        if "status" in data:
            task.f_status = STATUS_MAPPING.get(data["status"], data["status"])
        if "auto_parse" in data:
            task.f_auto_parse = data["auto_parse"]
        if "max_articles_per_source" in data:
            task.f_max_articles_per_source = data["max_articles_per_source"]
        if "schedule_config" in data:
            task.f_schedule_config = data["schedule_config"]
        if "statistics" in data:
            task.f_statistics = data["statistics"]
        if "error_message" in data:
            task.f_error_message = data["error_message"]
        
        task.f_update_time = current_timestamp()
        task.f_update_date = timestamp_to_date(task.f_update_time)
        task.save()
        
        return {
            "id": task.f_id,
            "task_name": task.f_task_name,
            "kb_id": task.f_kb_id,
            "source_ids": task.f_source_ids,
            "status": task.f_status,
            "auto_parse": task.f_auto_parse,
            "max_articles_per_source": task.f_max_articles_per_source,
            "created_at": timestamp_to_date(task.f_create_time).isoformat(),
            "updated_at": timestamp_to_date(task.f_update_time).isoformat(),
            "last_run_at": timestamp_to_date(task.f_last_run_time).isoformat() if task.f_last_run_time else None,
            "next_run_at": timestamp_to_date(task.f_next_run_time).isoformat() if task.f_next_run_time else None,
            "statistics": task.f_statistics,
            "schedule_config": task.f_schedule_config
        }
    except NewsTask.DoesNotExist:
        return None
    except Exception as e:
        logger.error(f"Failed to update news task {task_id}: {e}")
        raise


@DB.connection_context()
def delete_news_task(task_id: str) -> bool:
    """删除抓取任务"""
    try:
        deleted = NewsTask.delete().where(NewsTask.f_id == task_id).execute()
        return deleted > 0
    except Exception as e:
        logger.error(f"Failed to delete news task {task_id}: {e}")
        return False


def execute_news_task(task_id: str) -> Dict[str, Any]:
    """执行抓取任务"""
    if not _news_manager:
        return {"success": False, "message": "新闻管理器未初始化"}
    
    try:
        with DB.connection_context():
            task = NewsTask.get(NewsTask.f_id == task_id)
            
            if task.f_status == DBTaskStatus.RUNNING.value:
                return {"success": False, "message": "任务正在运行中"}
            
            # 更新任务状态
            task.f_status = DBTaskStatus.RUNNING.value
            task.f_last_run_time = current_timestamp()
            task.f_update_time = current_timestamp()
            task.f_update_date = timestamp_to_date(task.f_update_time)
            task.save()
    except NewsTask.DoesNotExist:
        return {"success": False, "message": "任务不存在"}
    except Exception as e:
        logger.error(f"Failed to prepare task execution {task_id}: {e}")
        return {"success": False, "message": f"任务准备失败: {str(e)}"}
    
    try:
        # 在后台线程中执行任务
        def run_task():
            asyncio.run(_execute_task_async(task_id))
        
        threading.Thread(target=run_task, daemon=True).start()
        
        return {
            "success": True,
            "message": "任务已开始执行",
            "task_id": task_id,
            "status": "running"
        }
        
    except Exception as e:
        # 恢复任务状态
        try:
            with DB.connection_context():
                task = NewsTask.get(NewsTask.f_id == task_id)
                task.f_status = DBTaskStatus.FAILED.value
                task.f_error_message = str(e)
                task.f_update_time = current_timestamp()
                task.f_update_date = timestamp_to_date(task.f_update_time)
                task.save()
        except:
            pass
        
        logger.error(f"Failed to execute task {task_id}: {e}")
        return {"success": False, "message": f"任务执行失败: {str(e)}"}


async def _execute_task_async(task_id: str):
    """异步执行抓取任务"""
    try:
        logger.info(f"Starting task execution: {task_id}")
        
        # 获取任务信息
        with DB.connection_context():
            task = NewsTask.get(NewsTask.f_id == task_id)
            
            # 获取相关新闻源
            sources = []
            if task.f_source_ids:
                source_query = NewsSource.select().where(NewsSource.f_id.in_(task.f_source_ids))
                for source in source_query:
                    # 转换为NewsSourceModel格式
                    source_model = NewsSourceModel(
                        id=source.f_id,
                        name=source.f_name,
                        url=source.f_url,
                        selector_config=SelectorConfig(**source.f_selector_config) if source.f_selector_config else None,
                        status=source.f_status,
                        created_at=timestamp_to_date(source.f_create_time),
                        updated_at=timestamp_to_date(source.f_update_time)
                    )
                    sources.append(source_model)
        
        if not sources:
            logger.warning(f"No valid sources found for task {task_id}")
            with DB.connection_context():
                task = NewsTask.get(NewsTask.f_id == task_id)
                task.f_status = DBTaskStatus.FAILED.value
                task.f_error_message = "No valid sources found"
                task.f_update_time = current_timestamp()
                task.f_update_date = timestamp_to_date(task.f_update_time)
                task.save()
            return
        
        # 执行抓取
        total_articles = 0
        success_count = 0
        failed_count = 0
        
        for source in sources:
            try:
                logger.info(f"Scraping source: {source.name} ({source.url})")
                
                # 使用新闻管理器执行抓取
                result = await _news_manager.scrape_and_save(
                    source=source,
                    kb_id=task.f_kb_id,
                    max_articles=task.f_max_articles_per_source,
                    auto_parse=task.f_auto_parse
                )
                
                articles = result.get("articles", [])
                total_articles += len(articles)
                
                # 保存抓取到的新闻到数据库
                with DB.connection_context():
                    for article in articles:
                        try:
                            # 生成内容指纹用于去重
                            fingerprint = _generate_content_fingerprint(
                                article.get("title", ""),
                                article.get("url", ""),
                                article.get("content", "")
                            )
                            
                            # 检查是否已存在
                            existing = NewsContent.select().where(NewsContent.f_fingerprint == fingerprint).exists()
                            if existing:
                                logger.debug(f"Article already exists: {article.get('title', '')}")
                                continue
                            
                            # 创建新闻内容记录
                            publish_time = None
                            if article.get("publish_time"):
                                try:
                                    if isinstance(article["publish_time"], str):
                                        from datetime import datetime
                                        publish_dt = datetime.fromisoformat(article["publish_time"].replace('Z', '+00:00'))
                                        publish_time = int(publish_dt.timestamp())
                                    else:
                                        publish_time = int(article["publish_time"])
                                except:
                                    pass
                            
                            content = NewsContent.create(
                                f_id=get_uuid(),
                                f_source_id=source.id,
                                f_task_id=task_id,
                                f_title=article.get("title", ""),
                                f_content=article.get("content", ""),
                                f_content_text=article.get("content_text", article.get("content", "")),
                                f_url=article.get("url", ""),
                                f_author=article.get("author", ""),
                                f_publish_time=publish_time,
                                f_crawl_time=current_timestamp(),
                                f_parse_status=DBParseStatus.PARSED.value if article.get("status") == "success" else DBParseStatus.PENDING.value,
                                f_ragflow_doc_id=article.get("ragflow_doc_id"),
                                f_tags=article.get("tags", []),
                                f_metadata=article.get("metadata", {}),
                                f_fingerprint=fingerprint,
                                f_create_time=current_timestamp(),
                                f_create_date=timestamp_to_date(current_timestamp()),
                                f_update_time=current_timestamp(),
                                f_update_date=timestamp_to_date(current_timestamp())
                            )
                            
                            if article.get("status") == "success":
                                success_count += 1
                            else:
                                failed_count += 1
                                
                        except Exception as e:
                            logger.error(f"Failed to save article: {e}")
                            failed_count += 1
                            continue
                
                # 更新新闻源统计
                with DB.connection_context():
                    source_record = NewsSource.get(NewsSource.f_id == source.id)
                    source_record.f_last_crawl_time = current_timestamp()
                    source_record.f_total_articles += len(articles)
                    source_record.f_success_count += success_count
                    source_record.f_failure_count += failed_count
                    source_record.f_update_time = current_timestamp()
                    source_record.f_update_date = timestamp_to_date(source_record.f_update_time)
                    source_record.save()
                
                logger.info(f"Scraped {len(articles)} articles from {source.name}")
                
            except Exception as e:
                logger.error(f"Error scraping source {source.name}: {e}")
                failed_count += 1
                continue
        
        # 更新任务状态和统计
        with DB.connection_context():
            task = NewsTask.get(NewsTask.f_id == task_id)
            task.f_status = DBTaskStatus.COMPLETED.value
            task.f_statistics = {
                "total_articles": total_articles,
                "success_count": success_count,
                "failed_count": failed_count,
                "last_execution": timestamp_to_date(current_timestamp()).isoformat()
            }
            task.f_update_time = current_timestamp()
            task.f_update_date = timestamp_to_date(task.f_update_time)
            task.save()
        
        logger.info(f"Task {task_id} completed. Total articles: {total_articles}, Success: {success_count}, Failed: {failed_count}")
        
    except Exception as e:
        logger.error(f"Task {task_id} execution failed: {e}")
        try:
            with DB.connection_context():
                task = NewsTask.get(NewsTask.f_id == task_id)
                task.f_status = DBTaskStatus.FAILED.value
                task.f_error_message = str(e)
                task.f_update_time = current_timestamp()
                task.f_update_date = timestamp_to_date(task.f_update_time)
                task.save()
        except Exception as save_error:
            logger.error(f"Failed to update task status: {save_error}")


# === 新闻内容管理 ===

@DB.connection_context()
def get_news_contents(page: int = 1, page_size: int = 10, source_id: Optional[str] = None, task_id: Optional[str] = None) -> Dict[str, Any]:
    """获取新闻内容列表（分页）"""
    try:
        query = NewsContent.select().order_by(NewsContent.f_crawl_time.desc())
        
        # 过滤条件
        if source_id:
            query = query.where(NewsContent.f_source_id == source_id)
        if task_id:
            query = query.where(NewsContent.f_task_id == task_id)
        
        total = query.count()
        offset = (page - 1) * page_size
        contents = query.offset(offset).limit(page_size)
        
        return {
            "data": [
                {
                    "id": content.f_id,
                    "source_id": content.f_source_id,
                    "task_id": content.f_task_id,
                    "title": content.f_title,
                    "content": content.f_content[:200] + "..." if len(content.f_content) > 200 else content.f_content,
                    "url": content.f_url,
                    "author": content.f_author,
                    "publish_time": timestamp_to_date(content.f_publish_time).isoformat() if content.f_publish_time else None,
                    "created_at": timestamp_to_date(content.f_create_time).isoformat(),
                    "parse_status": content.f_parse_status,
                    "tags": content.f_tags,
                    "ragflow_doc_id": content.f_ragflow_doc_id
                }
                for content in contents
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }
    except Exception as e:
        logger.error(f"Failed to get news contents: {e}")
        return {"data": [], "total": 0, "page": page, "page_size": page_size, "total_pages": 0}


@DB.connection_context()
def get_news_content(content_id: str) -> Optional[Dict[str, Any]]:
    """获取单个新闻内容详情"""
    try:
        content = NewsContent.get(NewsContent.f_id == content_id)
        return {
            "id": content.f_id,
            "source_id": content.f_source_id,
            "task_id": content.f_task_id,
            "title": content.f_title,
            "content": content.f_content,
            "content_text": content.f_content_text,
            "url": content.f_url,
            "author": content.f_author,
            "publish_time": timestamp_to_date(content.f_publish_time).isoformat() if content.f_publish_time else None,
            "created_at": timestamp_to_date(content.f_create_time).isoformat(),
            "parse_status": content.f_parse_status,
            "tags": content.f_tags,
            "metadata": content.f_metadata,
            "ragflow_doc_id": content.f_ragflow_doc_id
        }
    except NewsContent.DoesNotExist:
        return None
    except Exception as e:
        logger.error(f"Failed to get news content {content_id}: {e}")
        return None


@DB.connection_context()
def delete_news_content(content_id: str) -> bool:
    """删除新闻内容"""
    try:
        deleted = NewsContent.delete().where(NewsContent.f_id == content_id).execute()
        return deleted > 0
    except Exception as e:
        logger.error(f"Failed to delete news content {content_id}: {e}")
        return False


# === 统计和报表 ===

@DB.connection_context()
def get_statistics_overview() -> Dict[str, Any]:
    """获取统计概览"""
    try:
        # 基础统计
        total_sources = NewsSource.select().count()
        active_sources = NewsSource.select().where(NewsSource.f_status == NewsSourceStatus.ACTIVE.value).count()
        total_tasks = NewsTask.select().count()
        running_tasks = NewsTask.select().where(NewsTask.f_status == DBTaskStatus.RUNNING.value).count()
        total_news = NewsContent.select().count()
        
        # 最近7天的新闻数量
        week_ago_timestamp = current_timestamp() - (7 * 24 * 60 * 60)
        recent_news = NewsContent.select().where(NewsContent.f_crawl_time >= week_ago_timestamp).count()
        
        # 按来源统计
        source_stats = []
        sources = NewsSource.select()
        for source in sources:
            news_count = NewsContent.select().where(NewsContent.f_source_id == source.f_id).count()
            if news_count > 0:
                source_stats.append({
                    "source_id": source.f_id,
                    "source_name": source.f_name,
                    "news_count": news_count
                })
        
        return {
            "total_sources": total_sources,
            "active_sources": active_sources,
            "total_tasks": total_tasks,
            "running_tasks": running_tasks,
            "total_news": total_news,
            "recent_news_week": recent_news,
            "source_statistics": source_stats
        }
    except Exception as e:
        logger.error(f"Failed to get statistics overview: {e}")
        return {
            "total_sources": 0,
            "active_sources": 0,
            "total_tasks": 0,
            "running_tasks": 0,
            "total_news": 0,
            "recent_news_week": 0,
            "source_statistics": []
        }


@DB.connection_context()
def get_source_statistics(source_id: str) -> Optional[Dict[str, Any]]:
    """获取特定新闻源的统计信息"""
    try:
        source = NewsSource.get(NewsSource.f_id == source_id)
        
        # 该源的新闻数量
        total_news = NewsContent.select().where(NewsContent.f_source_id == source_id).count()
        
        # 最近7天的新闻
        week_ago_timestamp = current_timestamp() - (7 * 24 * 60 * 60)
        recent_news = NewsContent.select().where(
            (NewsContent.f_source_id == source_id) & 
            (NewsContent.f_crawl_time >= week_ago_timestamp)
        ).count()
        
        # 解析状态统计
        parse_stats = {}
        for status in [DBParseStatus.PENDING.value, DBParseStatus.PARSING.value, DBParseStatus.PARSED.value, DBParseStatus.FAILED.value]:
            count = NewsContent.select().where(
                (NewsContent.f_source_id == source_id) & 
                (NewsContent.f_parse_status == status)
            ).count()
            if count > 0:
                parse_stats[status] = count
        
        # 相关任务
        related_tasks = 0
        tasks = NewsTask.select()
        for task in tasks:
            if source_id in task.f_source_ids:
                related_tasks += 1
        
        # 最后更新时间
        last_update = None
        latest_content = NewsContent.select().where(NewsContent.f_source_id == source_id).order_by(NewsContent.f_crawl_time.desc()).first()
        if latest_content:
            last_update = timestamp_to_date(latest_content.f_crawl_time).isoformat()
        
        return {
            "source_id": source_id,
            "source_name": source.f_name,
            "source_url": source.f_url,
            "total_news": total_news,
            "recent_news_week": recent_news,
            "parse_statistics": parse_stats,
            "related_tasks": related_tasks,
            "last_update": last_update
        }
    except NewsSource.DoesNotExist:
        return None
    except Exception as e:
        logger.error(f"Failed to get source statistics {source_id}: {e}")
        return None
