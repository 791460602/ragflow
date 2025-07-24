"""
新闻抓取系统服务层

提供业务逻辑处理，连接API和底层模块
"""

import asyncio
import threading
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging

# 导入本包内的模块
from .models import (
    NewsSource, NewsTask, NewsContent, KnowledgeBase, 
    TaskStatus, SelectorConfig, ParseStatus
)
from .manager import NewsManager
from .scraper import NewsScraper

logger = logging.getLogger(__name__)

# 内存存储（临时解决方案，后续可以替换为数据库）
_news_sources: Dict[int, NewsSource] = {}
_news_tasks: Dict[int, NewsTask] = {}
_news_contents: Dict[int, NewsContent] = {}
_knowledge_bases: Dict[str, KnowledgeBase] = {}

# 线程锁和ID生成器
_lock = threading.Lock()
_next_source_id = 1
_next_task_id = 1
_next_content_id = 1

# 全局新闻管理器（需要在初始化时设置RAGFlow客户端）
_news_manager: Optional[NewsManager] = None


def initialize_news_manager(ragflow_client):
    """初始化新闻管理器"""
    global _news_manager
    _news_manager = NewsManager(ragflow_client)
    logger.info("News manager initialized with RAGFlow client")


def get_news_manager() -> Optional[NewsManager]:
    """获取新闻管理器实例"""
    return _news_manager


# === 知识库管理 ===

def get_knowledge_bases() -> List[Dict[str, Any]]:
    """获取所有知识库列表"""
    with _lock:
        return [
            {
                "id": kb.id,
                "name": kb.name,
                "description": kb.description,
                "created_at": kb.created_at.isoformat(),
                "status": kb.status
            }
            for kb in _knowledge_bases.values()
        ]


def get_knowledge_base(kb_id: str) -> Optional[Dict[str, Any]]:
    """获取单个知识库详情"""
    with _lock:
        kb = _knowledge_bases.get(kb_id)
        if kb:
            return {
                "id": kb.id,
                "name": kb.name,
                "description": kb.description,
                "created_at": kb.created_at.isoformat(),
                "status": kb.status
            }
        return None


def create_knowledge_base(data: Dict[str, Any]) -> Dict[str, Any]:
    """创建知识库"""
    with _lock:
        kb = KnowledgeBase(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            created_at=datetime.now(),
            status="active"
        )
        _knowledge_bases[kb.id] = kb
        
        return {
            "id": kb.id,
            "name": kb.name,
            "description": kb.description,
            "created_at": kb.created_at.isoformat(),
            "status": kb.status
        }


# === 新闻源管理 ===

def get_news_sources(page: int = 1, page_size: int = 10) -> Dict[str, Any]:
    """获取新闻源列表（分页）"""
    with _lock:
        sources = list(_news_sources.values())
        total = len(sources)
        start = (page - 1) * page_size
        end = start + page_size
        page_sources = sources[start:end]
        
        return {
            "data": [
                {
                    "id": source.id,
                    "name": source.name,
                    "url": source.url,
                    "remark": source.remark,
                    "status": source.status,
                    "created_at": source.created_at.isoformat(),
                    "updated_at": source.updated_at.isoformat(),
                    "selector_config": source.selector_config.__dict__ if source.selector_config else None
                }
                for source in page_sources
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }


def get_news_source(source_id: int) -> Optional[Dict[str, Any]]:
    """获取单个新闻源详情"""
    with _lock:
        source = _news_sources.get(source_id)
        if source:
            return {
                "id": source.id,
                "name": source.name,
                "url": source.url,
                "remark": source.remark,
                "status": source.status,
                "created_at": source.created_at.isoformat(),
                "updated_at": source.updated_at.isoformat(),
                "selector_config": source.selector_config.__dict__ if source.selector_config else None
            }
        return None


def create_news_source(data: Dict[str, Any]) -> Dict[str, Any]:
    """创建新闻源"""
    global _next_source_id
    
    with _lock:
        source_id = _next_source_id
        _next_source_id += 1
        
        # 创建选择器配置
        selector_config = None
        if "selector_config" in data and data["selector_config"]:
            selector_config = SelectorConfig(**data["selector_config"])
        
        source = NewsSource(
            id=source_id,
            name=data["name"],
            url=data["url"],
            remark=data.get("remark", ""),
            status=data.get("status", "active"),
            selector_config=selector_config,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        _news_sources[source_id] = source
        
        return {
            "id": source.id,
            "name": source.name,
            "url": source.url,
            "remark": source.remark,
            "status": source.status,
            "created_at": source.created_at.isoformat(),
            "updated_at": source.updated_at.isoformat(),
            "selector_config": source.selector_config.__dict__ if source.selector_config else None
        }


def update_news_source(source_id: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """更新新闻源"""
    with _lock:
        source = _news_sources.get(source_id)
        if not source:
            return None
        
        # 更新字段
        if "name" in data:
            source.name = data["name"]
        if "url" in data:
            source.url = data["url"]
        if "remark" in data:
            source.remark = data["remark"]
        if "status" in data:
            source.status = data["status"]
        if "selector_config" in data:
            if data["selector_config"]:
                source.selector_config = SelectorConfig(**data["selector_config"])
            else:
                source.selector_config = None
        
        source.updated_at = datetime.now()
        
        return {
            "id": source.id,
            "name": source.name,
            "url": source.url,
            "remark": source.remark,
            "status": source.status,
            "created_at": source.created_at.isoformat(),
            "updated_at": source.updated_at.isoformat(),
            "selector_config": source.selector_config.__dict__ if source.selector_config else None
        }


def delete_news_source(source_id: int) -> bool:
    """删除新闻源"""
    with _lock:
        if source_id in _news_sources:
            del _news_sources[source_id]
            return True
        return False


# === 抓取任务管理 ===

def get_news_tasks(page: int = 1, page_size: int = 10) -> Dict[str, Any]:
    """获取抓取任务列表（分页）"""
    with _lock:
        tasks = list(_news_tasks.values())
        total = len(tasks)
        start = (page - 1) * page_size
        end = start + page_size
        page_tasks = tasks[start:end]
        
        return {
            "data": [
                {
                    "id": task.id,
                    "task_name": task.task_name,
                    "kb_id": task.kb_id,
                    "source_ids": task.source_ids,
                    "status": task.status,
                    "auto_parse": task.auto_parse,
                    "max_articles_per_source": task.max_articles_per_source,
                    "created_at": task.created_at.isoformat(),
                    "updated_at": task.updated_at.isoformat(),
                    "last_run_at": task.last_run_at.isoformat() if task.last_run_at else None,
                    "next_run_at": task.next_run_at.isoformat() if task.next_run_at else None,
                    "statistics": task.statistics
                }
                for task in page_tasks
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }


def get_news_task(task_id: int) -> Optional[Dict[str, Any]]:
    """获取单个抓取任务详情"""
    with _lock:
        task = _news_tasks.get(task_id)
        if task:
            return {
                "id": task.id,
                "task_name": task.task_name,
                "kb_id": task.kb_id,
                "source_ids": task.source_ids,
                "status": task.status,
                "auto_parse": task.auto_parse,
                "max_articles_per_source": task.max_articles_per_source,
                "created_at": task.created_at.isoformat(),
                "updated_at": task.updated_at.isoformat(),
                "last_run_at": task.last_run_at.isoformat() if task.last_run_at else None,
                "next_run_at": task.next_run_at.isoformat() if task.next_run_at else None,
                "statistics": task.statistics
            }
        return None


def create_news_task(data: Dict[str, Any]) -> Dict[str, Any]:
    """创建抓取任务"""
    global _next_task_id
    
    with _lock:
        task_id = _next_task_id
        _next_task_id += 1
        
        task = NewsTask(
            id=task_id,
            task_name=data["task_name"],
            kb_id=data["kb_id"],
            source_ids=data["source_ids"],
            status=TaskStatus.PENDING,
            auto_parse=data.get("auto_parse", True),
            max_articles_per_source=data.get("max_articles_per_source", 10),
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        _news_tasks[task_id] = task
        
        return {
            "id": task.id,
            "task_name": task.task_name,
            "kb_id": task.kb_id,
            "source_ids": task.source_ids,
            "status": task.status,
            "auto_parse": task.auto_parse,
            "max_articles_per_source": task.max_articles_per_source,
            "created_at": task.created_at.isoformat(),
            "updated_at": task.updated_at.isoformat(),
            "statistics": task.statistics
        }


def update_news_task(task_id: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """更新抓取任务"""
    with _lock:
        task = _news_tasks.get(task_id)
        if not task:
            return None
        
        # 更新字段
        if "task_name" in data:
            task.task_name = data["task_name"]
        if "kb_id" in data:
            task.kb_id = data["kb_id"]
        if "source_ids" in data:
            task.source_ids = data["source_ids"]
        if "status" in data:
            task.status = data["status"]
        if "auto_parse" in data:
            task.auto_parse = data["auto_parse"]
        if "max_articles_per_source" in data:
            task.max_articles_per_source = data["max_articles_per_source"]
        
        task.updated_at = datetime.now()
        
        return {
            "id": task.id,
            "task_name": task.task_name,
            "kb_id": task.kb_id,
            "source_ids": task.source_ids,
            "status": task.status,
            "auto_parse": task.auto_parse,
            "max_articles_per_source": task.max_articles_per_source,
            "created_at": task.created_at.isoformat(),
            "updated_at": task.updated_at.isoformat(),
            "last_run_at": task.last_run_at.isoformat() if task.last_run_at else None,
            "next_run_at": task.next_run_at.isoformat() if task.next_run_at else None,
            "statistics": task.statistics
        }


def delete_news_task(task_id: int) -> bool:
    """删除抓取任务"""
    with _lock:
        if task_id in _news_tasks:
            del _news_tasks[task_id]
            return True
        return False


def execute_news_task(task_id: int) -> Dict[str, Any]:
    """执行抓取任务"""
    if not _news_manager:
        return {"success": False, "message": "新闻管理器未初始化"}
    
    with _lock:
        task = _news_tasks.get(task_id)
        if not task:
            return {"success": False, "message": "任务不存在"}
        
        if task.status == TaskStatus.RUNNING:
            return {"success": False, "message": "任务正在运行中"}
        
        # 更新任务状态
        task.status = TaskStatus.RUNNING
        task.last_run_at = datetime.now()
        task.updated_at = datetime.now()
    
    try:
        # 在后台线程中执行任务
        def run_task():
            asyncio.run(_execute_task_async(task))
        
        threading.Thread(target=run_task, daemon=True).start()
        
        return {
            "success": True,
            "message": "任务已开始执行",
            "task_id": task_id,
            "status": "running"
        }
        
    except Exception as e:
        with _lock:
            task.status = TaskStatus.FAILED
            task.updated_at = datetime.now()
        
        logger.error(f"Failed to execute task {task_id}: {e}")
        return {"success": False, "message": f"任务执行失败: {str(e)}"}


async def _execute_task_async(task: NewsTask):
    """异步执行抓取任务"""
    try:
        logger.info(f"Starting task execution: {task.id}")
        
        # 获取任务相关的新闻源
        sources = []
        with _lock:
            for source_id in task.source_ids:
                if source_id in _news_sources:
                    sources.append(_news_sources[source_id])
        
        if not sources:
            logger.warning(f"No valid sources found for task {task.id}")
            with _lock:
                task.status = TaskStatus.FAILED
                task.updated_at = datetime.now()
            return
        
        # 执行抓取
        total_articles = 0
        success_count = 0
        
        for source in sources:
            try:
                logger.info(f"Scraping source: {source.name} ({source.url})")
                
                # 使用新闻管理器执行抓取
                result = await _news_manager.scrape_and_save(
                    source=source,
                    kb_id=task.kb_id,
                    max_articles=task.max_articles_per_source,
                    auto_parse=task.auto_parse
                )
                
                articles = result.get("articles", [])
                total_articles += len(articles)
                success_count += len([a for a in articles if a.get("status") == "success"])
                
                # 保存抓取到的新闻到内存存储
                global _next_content_id
                with _lock:
                    for article in articles:
                        content = NewsContent(
                            id=_next_content_id,
                            source_id=source.id,
                            task_id=task.id,
                            title=article.get("title", ""),
                            content=article.get("content", ""),
                            url=article.get("url", ""),
                            author=article.get("author", ""),
                            publish_time=datetime.fromisoformat(article["publish_time"]) if article.get("publish_time") else datetime.now(),
                            created_at=datetime.now(),
                            parse_status=ParseStatus.PARSED if article.get("status") == "success" else ParseStatus.PENDING
                        )
                        _news_contents[_next_content_id] = content
                        _next_content_id += 1
                
                logger.info(f"Scraped {len(articles)} articles from {source.name}")
                
            except Exception as e:
                logger.error(f"Error scraping source {source.name}: {e}")
                continue
        
        # 更新任务状态和统计
        with _lock:
            task.status = TaskStatus.COMPLETED
            task.updated_at = datetime.now()
            task.statistics.update({
                "total_articles": total_articles,
                "success_count": success_count,
                "last_execution": datetime.now().isoformat()
            })
        
        logger.info(f"Task {task.id} completed. Total articles: {total_articles}, Success: {success_count}")
        
    except Exception as e:
        logger.error(f"Task {task.id} execution failed: {e}")
        with _lock:
            task.status = TaskStatus.FAILED
            task.updated_at = datetime.now()


# === 新闻内容管理 ===

def get_news_contents(page: int = 1, page_size: int = 10, source_id: Optional[int] = None, task_id: Optional[int] = None) -> Dict[str, Any]:
    """获取新闻内容列表（分页）"""
    with _lock:
        contents = list(_news_contents.values())
        
        # 过滤条件
        if source_id is not None:
            contents = [c for c in contents if c.source_id == source_id]
        if task_id is not None:
            contents = [c for c in contents if c.task_id == task_id]
        
        # 按创建时间降序排序
        contents.sort(key=lambda x: x.created_at, reverse=True)
        
        total = len(contents)
        start = (page - 1) * page_size
        end = start + page_size
        page_contents = contents[start:end]
        
        return {
            "data": [
                {
                    "id": content.id,
                    "source_id": content.source_id,
                    "task_id": content.task_id,
                    "title": content.title,
                    "content": content.content[:200] + "..." if len(content.content) > 200 else content.content,  # 截断长内容
                    "url": content.url,
                    "author": content.author,
                    "publish_time": content.publish_time.isoformat(),
                    "created_at": content.created_at.isoformat(),
                    "parse_status": content.parse_status
                }
                for content in page_contents
            ],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }


def get_news_content(content_id: int) -> Optional[Dict[str, Any]]:
    """获取单个新闻内容详情"""
    with _lock:
        content = _news_contents.get(content_id)
        if content:
            return {
                "id": content.id,
                "source_id": content.source_id,
                "task_id": content.task_id,
                "title": content.title,
                "content": content.content,
                "url": content.url,
                "author": content.author,
                "publish_time": content.publish_time.isoformat(),
                "created_at": content.created_at.isoformat(),
                "parse_status": content.parse_status
            }
        return None


def delete_news_content(content_id: int) -> bool:
    """删除新闻内容"""
    with _lock:
        if content_id in _news_contents:
            del _news_contents[content_id]
            return True
        return False


# === 统计和报表 ===

def get_statistics_overview() -> Dict[str, Any]:
    """获取统计概览"""
    with _lock:
        # 基础统计
        total_sources = len(_news_sources)
        active_sources = len([s for s in _news_sources.values() if s.status == "active"])
        total_tasks = len(_news_tasks)
        running_tasks = len([t for t in _news_tasks.values() if t.status == TaskStatus.RUNNING])
        total_news = len(_news_contents)
        
        # 最近7天的新闻数量
        now = datetime.now()
        week_ago = now - timedelta(days=7)
        recent_news = len([c for c in _news_contents.values() if c.created_at >= week_ago])
        
        # 按来源统计
        source_stats = {}
        for content in _news_contents.values():
            source_id = content.source_id
            if source_id not in source_stats:
                source_stats[source_id] = {"count": 0, "name": "Unknown"}
                # 获取源名称
                source = _news_sources.get(source_id)
                if source:
                    source_stats[source_id]["name"] = source.name
            source_stats[source_id]["count"] += 1
        
        return {
            "total_sources": total_sources,
            "active_sources": active_sources,
            "total_tasks": total_tasks,
            "running_tasks": running_tasks,
            "total_news": total_news,
            "recent_news_week": recent_news,
            "source_statistics": [
                {"source_id": sid, "source_name": stats["name"], "news_count": stats["count"]}
                for sid, stats in source_stats.items()
            ]
        }


def get_source_statistics(source_id: int) -> Optional[Dict[str, Any]]:
    """获取特定新闻源的统计信息"""
    with _lock:
        source = _news_sources.get(source_id)
        if not source:
            return None
        
        # 该源的新闻数量
        source_contents = [c for c in _news_contents.values() if c.source_id == source_id]
        total_news = len(source_contents)
        
        # 最近7天的新闻
        now = datetime.now()
        week_ago = now - timedelta(days=7)
        recent_news = len([c for c in source_contents if c.created_at >= week_ago])
        
        # 解析状态统计
        parse_stats = {}
        for content in source_contents:
            status = content.parse_status
            parse_stats[status] = parse_stats.get(status, 0) + 1
        
        # 相关任务
        related_tasks = [t for t in _news_tasks.values() if source_id in t.source_ids]
        
        return {
            "source_id": source_id,
            "source_name": source.name,
            "source_url": source.url,
            "total_news": total_news,
            "recent_news_week": recent_news,
            "parse_statistics": parse_stats,
            "related_tasks": len(related_tasks),
            "last_update": max([c.created_at for c in source_contents]).isoformat() if source_contents else None
        }
