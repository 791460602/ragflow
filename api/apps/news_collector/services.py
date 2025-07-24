"""
新闻抓取系统服务层

提供业务逻辑处理，连接API和底层模块
"""

import asyncio
import threading
import sys
import os
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import logging

# 添加项目根路径，以便导入news_collector模块
current_dir = os.path.dirname(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 导入我们的新闻抓取模块
from news_collector.models import (
    NewsSource, NewsTask, NewsContent, KnowledgeBase, 
    TaskStatus, SelectorConfig, ParseStatus
)
from news_collector.manager import NewsManager
from news_collector.scraper import NewsScraper

# 兼容现有的 schemas
from .schemas import NewsSource as NewsSourceSchema, NewsSourceCreate, NewsHistoryItem

logger = logging.getLogger(__name__)

# 内存存储（临时解决方案，后续可以替换为数据库）
_news_sources: Dict[int, NewsSource] = {}
_news_tasks: Dict[int, NewsTask] = {}
_news_contents: Dict[int, NewsContent] = {}
_knowledge_bases: Dict[str, KnowledgeBase] = {}
_news_history: List[NewsHistoryItem] = []

# 线程锁和ID生成器
_lock = threading.Lock()
_next_source_id = 1
_next_task_id = 1
_next_content_id = 1
_next_history_id = 1

# 全局新闻管理器（需要在初始化时设置RAGFlow客户端）
_news_manager: Optional[NewsManager] = None


def initialize_news_manager(ragflow_client):
    """
    初始化新闻管理器
    
    Args:
        ragflow_client: RAGFlow客户端实例
    """
    global _news_manager
    _news_manager = NewsManager(ragflow_client)
    logger.info("News manager initialized")


# ===== 知识库管理 =====

def get_knowledge_bases() -> List[Dict[str, Any]]:
    """获取知识库列表"""
    try:
        if _news_manager:
            kbs = _news_manager.get_knowledge_bases()
            return [kb.to_dict() for kb in kbs]
        return list(_knowledge_bases.values())
    except Exception as e:
        logger.error(f"Error getting knowledge bases: {str(e)}")
        return []


def create_knowledge_base(name: str, description: str = "", chunk_method: str = "naive") -> Optional[Dict[str, Any]]:
    """创建知识库"""
    try:
        if _news_manager:
            kb = _news_manager.create_knowledge_base(name, description, chunk_method)
            if kb:
                _knowledge_bases[kb.id] = kb
                return kb.to_dict()
        return None
    except Exception as e:
        logger.error(f"Error creating knowledge base: {str(e)}")
        return None


# ===== 新闻源管理 =====

def get_news_sources(page: int = 1, size: int = 20, keyword: str = "", 
                    status: str = "", sort_by: str = "created_at", order: str = "desc") -> Dict[str, Any]:
    """获取新闻源列表（分页）"""
    try:
        sources = list(_news_sources.values())
        
        # 过滤
        if keyword:
            sources = [s for s in sources if keyword.lower() in s.name.lower() or keyword.lower() in s.remark.lower()]
        if status:
            sources = [s for s in sources if s.status.value == status]
        
        # 排序
        reverse = order == "desc"
        if sort_by == "name":
            sources.sort(key=lambda x: x.name, reverse=reverse)
        elif sort_by == "news_count":
            sources.sort(key=lambda x: x.news_count, reverse=reverse)
        else:  # created_at
            sources.sort(key=lambda x: x.created_at or datetime.min, reverse=reverse)
        
        # 分页
        total = len(sources)
        start = (page - 1) * size
        end = start + size
        page_sources = sources[start:end]
        
        return {
            "total": total,
            "page": page,
            "size": size,
            "list": [source.to_dict() for source in page_sources]
        }
    except Exception as e:
        logger.error(f"Error getting news sources: {str(e)}")
        return {"total": 0, "page": page, "size": size, "list": []}


def get_news_source(source_id: int) -> Optional[Dict[str, Any]]:
    """获取单个新闻源"""
    source = _news_sources.get(source_id)
    return source.to_dict() if source else None


def create_news_source(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """创建新闻源"""
    global _next_source_id
    
    try:
        with _lock:
            source_id = _next_source_id
            _next_source_id += 1
        
        # 创建选择器配置
        selector_config = SelectorConfig.from_dict(data.get("selector_config", {}))
        
        # 创建新闻源对象
        source = NewsSource(
            id=source_id,
            name=data["name"],
            url=data["url"],
            remark=data.get("remark", ""),
            selector_config=selector_config,
            created_at=datetime.now()
        )
        
        _news_sources[source_id] = source
        logger.info(f"Created news source: {source.name} (ID: {source_id})")
        
        return {"id": source_id}
    except Exception as e:
        logger.error(f"Error creating news source: {str(e)}")
        return None


def update_news_source(source_id: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """更新新闻源"""
    try:
        source = _news_sources.get(source_id)
        if not source:
            return None
        
        # 更新字段
        source.name = data.get("name", source.name)
        source.url = data.get("url", source.url)
        source.remark = data.get("remark", source.remark)
        source.status = NewsSource.NewsStatus(data.get("status", source.status.value))
        
        if "selector_config" in data:
            source.selector_config = SelectorConfig.from_dict(data["selector_config"])
        
        source.updated_at = datetime.now()
        
        logger.info(f"Updated news source: {source.name} (ID: {source_id})")
        return {"id": source_id}
    except Exception as e:
        logger.error(f"Error updating news source: {str(e)}")
        return None


def delete_news_source(source_id: int) -> bool:
    """删除新闻源"""
    try:
        source = _news_sources.pop(source_id, None)
        if source:
            logger.info(f"Deleted news source: {source.name} (ID: {source_id})")
            return True
        return False
    except Exception as e:
        logger.error(f"Error deleting news source: {str(e)}")
        return False


async def validate_news_source(url: str, selector_config: Dict[str, str]) -> Dict[str, Any]:
    """验证新闻源可用性"""
    try:
        if not _news_manager:
            raise RuntimeError("News manager not initialized")
        
        async with _news_manager as manager:
            result = await manager.validate_news_source(url, selector_config)
            return result
    except Exception as e:
        logger.error(f"Error validating news source: {str(e)}")
        return {
            "valid": False,
            "error": str(e)
        }


# ===== 抓取任务管理 =====

def get_news_tasks(page: int = 1, size: int = 20, status: str = "", 
                  start_date: str = "", end_date: str = "") -> Dict[str, Any]:
    """获取抓取任务列表"""
    try:
        tasks = list(_news_tasks.values())
        
        # 过滤
        if status:
            tasks = [t for t in tasks if t.status.value == status]
        
        if start_date:
            start_dt = datetime.fromisoformat(start_date)
            tasks = [t for t in tasks if t.created_at and t.created_at >= start_dt]
        
        if end_date:
            end_dt = datetime.fromisoformat(end_date)
            tasks = [t for t in tasks if t.created_at and t.created_at <= end_dt]
        
        # 排序（按创建时间倒序）
        tasks.sort(key=lambda x: x.created_at or datetime.min, reverse=True)
        
        # 分页
        total = len(tasks)
        start_idx = (page - 1) * size
        end_idx = start_idx + size
        page_tasks = tasks[start_idx:end_idx]
        
        # 转换为字典并添加额外信息
        task_list = []
        for task in page_tasks:
            task_dict = task.to_dict()
            
            # 添加知识库名称
            kb = _knowledge_bases.get(task.kb_id)
            task_dict["kb_name"] = kb.name if kb else task.kb_id
            
            # 添加新闻源名称
            source_names = []
            for source_id in task.source_ids:
                source = _news_sources.get(source_id)
                if source:
                    source_names.append(source.name)
            task_dict["source_names"] = source_names
            
            task_list.append(task_dict)
        
        return {
            "total": total,
            "page": page,
            "size": size,
            "list": task_list
        }
    except Exception as e:
        logger.error(f"Error getting news tasks: {str(e)}")
        return {"total": 0, "page": page, "size": size, "list": []}


def get_news_task(task_id: int) -> Optional[Dict[str, Any]]:
    """获取单个任务详情"""
    task = _news_tasks.get(task_id)
    if task:
        task_dict = task.to_dict()
        
        # 添加知识库信息
        kb = _knowledge_bases.get(task.kb_id)
        if kb:
            task_dict["kb_name"] = kb.name
        
        return task_dict
    return None


def create_news_task(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """创建抓取任务"""
    global _next_task_id
    
    try:
        with _lock:
            task_id = _next_task_id
            _next_task_id += 1
        
        # 创建任务对象
        task = NewsTask(
            id=task_id,
            task_name=data["task_name"],
            kb_id=data["kb_id"],
            source_ids=data["source_ids"],
            auto_parse=data.get("auto_parse", True),
            max_articles_per_source=data.get("max_articles_per_source", 100),
            created_at=datetime.now()
        )
        
        # 设置调度信息
        if "schedule_type" in data:
            task.schedule_type = NewsTask.ScheduleType(data["schedule_type"])
            task.schedule_time = data.get("schedule_time")
            task.schedule_days = data.get("schedule_days", [])
        
        _news_tasks[task_id] = task
        logger.info(f"Created news task: {task.task_name} (ID: {task_id})")
        
        return {"id": task_id}
    except Exception as e:
        logger.error(f"Error creating news task: {str(e)}")
        return None


async def execute_news_task(task_id: int) -> Dict[str, Any]:
    """执行抓取任务"""
    try:
        task = _news_tasks.get(task_id)
        if not task:
            return {"error": "Task not found"}
        
        if not _news_manager:
            return {"error": "News manager not initialized"}
        
        # 获取相关的新闻源
        sources = [_news_sources[sid] for sid in task.source_ids if sid in _news_sources]
        
        # 执行任务
        async with _news_manager as manager:
            result = await manager.execute_scraping_task(task, sources)
            
            # 保存抓取到的新闻内容
            if "articles" in result:
                for article in result["articles"]:
                    save_news_content(article)
        
        return result
    except Exception as e:
        logger.error(f"Error executing news task: {str(e)}")
        return {"error": str(e)}


def stop_news_task(task_id: int) -> Dict[str, Any]:
    """停止执行任务"""
    try:
        if _news_manager:
            success = asyncio.run(_news_manager.stop_task(task_id))
            if success:
                return {"message": "任务已停止"}
        return {"error": "无法停止任务"}
    except Exception as e:
        logger.error(f"Error stopping news task: {str(e)}")
        return {"error": str(e)}


def delete_news_task(task_id: int) -> bool:
    """删除抓取任务"""
    try:
        task = _news_tasks.pop(task_id, None)
        if task:
            logger.info(f"Deleted news task: {task.task_name} (ID: {task_id})")
            return True
        return False
    except Exception as e:
        logger.error(f"Error deleting news task: {str(e)}")
        return False


# ===== 新闻内容管理 =====

def get_news_contents(page: int = 1, size: int = 20, source_id: int = None, 
                     kb_id: str = "", parse_status: str = "") -> Dict[str, Any]:
    """获取新闻内容列表"""
    try:
        contents = list(_news_contents.values())
        
        # 过滤
        if source_id:
            contents = [c for c in contents if c.source_id == source_id]
        if kb_id:
            contents = [c for c in contents if c.kb_id == kb_id]
        if parse_status:
            contents = [c for c in contents if c.parse_status.value == parse_status]
        
        # 排序（按创建时间倒序）
        contents.sort(key=lambda x: x.created_at or datetime.min, reverse=True)
        
        # 分页
        total = len(contents)
        start = (page - 1) * size
        end = start + size
        page_contents = contents[start:end]
        
        # 转换为字典并添加额外信息
        content_list = []
        for content in page_contents:
            content_dict = content.to_dict()
            
            # 添加新闻源名称
            source = _news_sources.get(content.source_id)
            content_dict["source_name"] = source.name if source else "未知"
            
            # 添加知识库名称
            kb = _knowledge_bases.get(content.kb_id)
            content_dict["kb_name"] = kb.name if kb else content.kb_id
            
            content_list.append(content_dict)
        
        return {
            "total": total,
            "page": page,
            "size": size,
            "list": content_list
        }
    except Exception as e:
        logger.error(f"Error getting news contents: {str(e)}")
        return {"total": 0, "page": page, "size": size, "list": []}


def get_news_content(content_id: int) -> Optional[Dict[str, Any]]:
    """获取单个新闻详情"""
    content = _news_contents.get(content_id)
    if content:
        content_dict = content.to_dict()
        
        # 添加关联信息
        source = _news_sources.get(content.source_id)
        if source:
            content_dict["source"] = {"id": source.id, "name": source.name}
        
        kb = _knowledge_bases.get(content.kb_id)
        if kb:
            content_dict["knowledge_base"] = {"id": kb.id, "name": kb.name}
        
        task = _news_tasks.get(content.task_id)
        if task:
            content_dict["task"] = {"id": task.id, "name": task.task_name}
        
        return content_dict
    return None


def save_news_content(content: NewsContent) -> int:
    """保存新闻内容"""
    global _next_content_id
    
    try:
        with _lock:
            content_id = _next_content_id
            _next_content_id += 1
        
        content.id = content_id
        content.created_at = datetime.now()
        _news_contents[content_id] = content
        
        logger.info(f"Saved news content: {content.title[:50]}... (ID: {content_id})")
        return content_id
    except Exception as e:
        logger.error(f"Error saving news content: {str(e)}")
        return 0


def update_news_content(content_id: int, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """更新新闻内容"""
    try:
        content = _news_contents.get(content_id)
        if not content:
            return None
        
        # 更新字段
        if "title" in data:
            content.title = data["title"]
        if "tags" in data:
            content.tags = data["tags"]
        if "status" in data:
            content.status = NewsContent.NewsStatus(data["status"])
        
        content.updated_at = datetime.now()
        
        logger.info(f"Updated news content: {content.title[:50]}... (ID: {content_id})")
        return {"id": content_id}
    except Exception as e:
        logger.error(f"Error updating news content: {str(e)}")
        return None


def delete_news_content(content_id: int) -> bool:
    """删除新闻内容"""
    try:
        content = _news_contents.pop(content_id, None)
        if content:
            logger.info(f"Deleted news content: {content.title[:50]}... (ID: {content_id})")
            return True
        return False
    except Exception as e:
        logger.error(f"Error deleting news content: {str(e)}")
        return False


async def reparse_news_content(content_id: int) -> Dict[str, Any]:
    """重新解析新闻内容到知识库"""
    try:
        content = _news_contents.get(content_id)
        if not content:
            return {"error": "News content not found"}
        
        if not _news_manager:
            return {"error": "News manager not initialized"}
        
        async with _news_manager as manager:
            result = await manager.reparse_news_to_kb(content, content.kb_id)
            
            # 更新解析状态
            if result.get("status") == "success":
                content.parse_status = ParseStatus.PENDING
                content.updated_at = datetime.now()
            
            return result
            
    except Exception as e:
        logger.error(f"Error reparsing news content: {str(e)}")
        return {"error": str(e)}


# ===== 统计功能 =====

def get_statistics_overview() -> Dict[str, Any]:
    """获取统计概览"""
    try:
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        # 基础统计
        total_sources = len(_news_sources)
        total_tasks = len(_news_tasks)
        total_news = len(_news_contents)
        total_knowledge_bases = len(_knowledge_bases)
        
        # 今日新闻数量
        today_news = [c for c in _news_contents.values() 
                     if c.created_at and c.created_at >= today_start]
        today_news_count = len(today_news)
        
        # 已解析新闻数量
        parsed_news = [c for c in _news_contents.values() 
                      if c.parse_status == ParseStatus.SUCCESS]
        parsed_news_count = len(parsed_news)
        
        # 24小时内任务成功率
        yesterday = now - timedelta(hours=24)
        recent_tasks = [t for t in _news_tasks.values() 
                       if t.finished_at and t.finished_at >= yesterday]
        
        success_rate_24h = 0.0
        if recent_tasks:
            success_tasks = [t for t in recent_tasks if t.status == TaskStatus.SUCCESS]
            success_rate_24h = len(success_tasks) / len(recent_tasks) * 100
        
        # 解析成功率
        parse_success_rate = 0.0
        if total_news > 0:
            parse_success_rate = parsed_news_count / total_news * 100
        
        return {
            "total_sources": total_sources,
            "total_tasks": total_tasks,
            "total_news": total_news,
            "total_knowledge_bases": total_knowledge_bases,
            "today_news_count": today_news_count,
            "parsed_news_count": parsed_news_count,
            "success_rate_24h": round(success_rate_24h, 1),
            "parse_success_rate": round(parse_success_rate, 1)
        }
    except Exception as e:
        logger.error(f"Error getting statistics overview: {str(e)}")
        return {}


def get_timeseries_statistics(start_date: str, end_date: str, interval: str = "daily") -> Dict[str, Any]:
    """获取时序统计数据"""
    try:
        start_dt = datetime.fromisoformat(start_date)
        end_dt = datetime.fromisoformat(end_date)
        
        # 生成时间标签
        labels = []
        current = start_dt
        
        if interval == "daily":
            while current <= end_dt:
                labels.append(current.strftime("%m-%d"))
                current += timedelta(days=1)
        else:  # hourly
            while current <= end_dt:
                labels.append(current.strftime("%H:00"))
                current += timedelta(hours=1)
        
        # 初始化数据
        scrape_success = [0] * len(labels)
        scrape_failed = [0] * len(labels)
        parse_success = [0] * len(labels)
        parse_failed = [0] * len(labels)
        
        # 统计任务数据
        for task in _news_tasks.values():
            if not task.finished_at or task.finished_at < start_dt or task.finished_at > end_dt:
                continue
            
            if interval == "daily":
                index = (task.finished_at.date() - start_dt.date()).days
            else:  # hourly
                total_hours = int((task.finished_at - start_dt).total_seconds() / 3600)
                index = total_hours
            
            if 0 <= index < len(labels):
                if task.status == TaskStatus.SUCCESS:
                    scrape_success[index] += task.success_count
                    scrape_failed[index] += task.failed_count
                else:
                    scrape_failed[index] += task.success_count + task.failed_count
        
        # 统计解析数据
        for content in _news_contents.values():
            if not content.created_at or content.created_at < start_dt or content.created_at > end_dt:
                continue
            
            if interval == "daily":
                index = (content.created_at.date() - start_dt.date()).days
            else:  # hourly
                total_hours = int((content.created_at - start_dt).total_seconds() / 3600)
                index = total_hours
            
            if 0 <= index < len(labels):
                if content.parse_status == ParseStatus.SUCCESS:
                    parse_success[index] += 1
                elif content.parse_status == ParseStatus.FAILED:
                    parse_failed[index] += 1
        
        return {
            "labels": labels,
            "datasets": [
                {"label": "抓取成功数", "data": scrape_success},
                {"label": "抓取失败数", "data": scrape_failed},
                {"label": "解析成功数", "data": parse_success},
                {"label": "解析失败数", "data": parse_failed}
            ]
        }
    except Exception as e:
        logger.error(f"Error getting timeseries statistics: {str(e)}")
        return {"labels": [], "datasets": []}


# ===== 历史记录兼容性 =====

def add_news_history(source_name: str, title: str, status: str) -> NewsHistoryItem:
    """添加新闻历史记录（兼容现有API）"""
    global _next_history_id
    
    with _lock:
        history_id = _next_history_id
        _next_history_id += 1
    
    item = NewsHistoryItem(
        id=history_id,
        sourceName=source_name,
        title=title,
        status=status,
        createdAt=datetime.now().strftime('%Y-%m-%d %H:%M')
    )
    _news_history.append(item)
    return item


def get_news_history() -> List[NewsHistoryItem]:
    """获取新闻历史记录（兼容现有API）"""
    return list(_news_history)


# ===== 兼容现有的简单API =====

def get_news_sources_simple() -> List[NewsSourceSchema]:
    """获取新闻源列表（简单格式，兼容现有前端）"""
    sources = []
    for source in _news_sources.values():
        # 转换为现有的schema格式
        schema_source = NewsSourceSchema(
            id=source.id,
            name=source.name,
            url=source.url,
            remark=source.remark,
            status=source.status.value,
            createdAt=source.created_at.strftime('%Y-%m-%d %H:%M:%S') if source.created_at else ""
        )
        sources.append(schema_source)
    return sources


def add_news_source_simple(data: NewsSourceCreate) -> NewsSourceSchema:
    """添加新闻源（简单格式，兼容现有前端）"""
    result = create_news_source({
        "name": data.name,
        "url": data.url,
        "remark": data.remark,
        "status": data.status
    })
    
    if result:
        source = _news_sources[result["id"]]
        return NewsSourceSchema(
            id=source.id,
            name=source.name,
            url=source.url,
            remark=source.remark,
            status=source.status.value,
            createdAt=source.created_at.strftime('%Y-%m-%d %H:%M:%S') if source.created_at else ""
        )
    return None


def delete_news_source_simple(source_id: int) -> bool:
    """删除新闻源（兼容现有前端）"""
    return delete_news_source(source_id) 