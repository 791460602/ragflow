"""
新闻管理器模块

提供新闻抓取任务管理、调度和与RAGFlow集成的功能
"""

import asyncio
import json
import os
import tempfile
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from pathlib import Path
import logging

from .models import NewsSource, NewsTask, NewsContent, KnowledgeBase, TaskStatus, ParseStatus
from .scraper import NewsScraper

logger = logging.getLogger(__name__)


class NewsManager:
    """新闻管理器"""
    
    def __init__(self, ragflow_client=None):
        """
        初始化新闻管理器
        
        Args:
            ragflow_client: RAGFlow客户端实例
        """
        self.ragflow_client = ragflow_client
        self.scraper = None
        self.running_tasks = {}  # 存储正在运行的任务
        
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.scraper = NewsScraper()
        await self.scraper.__aenter__()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.scraper:
            await self.scraper.__aexit__(exc_type, exc_val, exc_tb)
    
    async def validate_news_source(self, url: str, selector_config: dict) -> Dict[str, Any]:
        """
        验证新闻源可用性
        
        Args:
            url: 新闻源URL
            selector_config: 选择器配置
            
        Returns:
            验证结果
        """
        if not self.scraper:
            raise RuntimeError("NewsManager not initialized. Use async context manager.")
        
        from .models import SelectorConfig
        config = SelectorConfig.from_dict(selector_config)
        return await self.scraper.validate_news_source(url, config)
    
    async def execute_scraping_task(self, task: NewsTask, sources: List[NewsSource]) -> Dict[str, Any]:
        """
        执行抓取任务
        
        Args:
            task: 抓取任务
            sources: 新闻源列表
            
        Returns:
            执行结果
        """
        if not self.scraper:
            raise RuntimeError("NewsManager not initialized. Use async context manager.")
        
        logger.info(f"Starting scraping task: {task.task_name}")
        
        # 标记任务为运行中
        task.status = TaskStatus.RUNNING
        self.running_tasks[task.id] = task
        
        # 执行结果
        result = {
            "task_id": task.id,
            "status": "running",
            "upload_result": {"data": []},
            "convert_result": {"data": []},
            "parse_result": None,
            "run_log": []
        }
        
        try:
            all_articles = []
            
            # 并发抓取所有新闻源
            scraping_tasks = []
            for source in sources:
                if source.id in task.source_ids:
                    scraping_task = asyncio.create_task(
                        self._scrape_source_with_logging(source, task.max_articles_per_source, result["run_log"])
                    )
                    scraping_tasks.append(scraping_task)
            
            # 等待所有抓取任务完成
            scraping_results = await asyncio.gather(*scraping_tasks, return_exceptions=True)
            
            # 收集所有文章
            for i, scraping_result in enumerate(scraping_results):
                if isinstance(scraping_result, list):
                    all_articles.extend(scraping_result)
                elif isinstance(scraping_result, Exception):
                    logger.error(f"Scraping task {i} failed: {str(scraping_result)}")
            
            logger.info(f"Total articles scraped: {len(all_articles)}")
            
            # 如果有文章，上传到RAGFlow
            if all_articles and self.ragflow_client:
                upload_result = await self._upload_to_ragflow(task, all_articles)
                result.update(upload_result)
            
            # 更新任务状态
            task.status = TaskStatus.SUCCESS
            task.success_count = len(all_articles)
            task.failed_count = 0
            task.finished_at = datetime.now()
            
            result["status"] = "success"
            result["message"] = f"成功抓取 {len(all_articles)} 篇文章"
            
        except Exception as e:
            logger.error(f"Scraping task failed: {str(e)}")
            task.status = TaskStatus.FAILED
            task.finished_at = datetime.now()
            result["status"] = "failed"
            result["message"] = str(e)
        
        finally:
            # 移除运行中的任务
            if task.id in self.running_tasks:
                del self.running_tasks[task.id]
        
        return result
    
    async def _scrape_source_with_logging(self, source: NewsSource, max_articles: int, run_log: List[Dict]) -> List[NewsContent]:
        """
        抓取单个新闻源并记录日志
        
        Args:
            source: 新闻源
            max_articles: 最大文章数
            run_log: 运行日志列表
            
        Returns:
            新闻内容列表
        """
        log_entry = {
            "source_id": source.id,
            "source_name": source.name,
            "status": "running",
            "fetched_count": 0,
            "message": "开始抓取..."
        }
        run_log.append(log_entry)
        
        try:
            articles = await self.scraper.scrape_news_source(source, max_articles)
            
            # 更新日志
            log_entry["status"] = "success"
            log_entry["fetched_count"] = len(articles)
            log_entry["message"] = f"成功抓取 {len(articles)} 篇文章"
            
            return articles
            
        except Exception as e:
            # 更新日志
            log_entry["status"] = "failed"
            log_entry["message"] = f"抓取失败: {str(e)}"
            logger.error(f"Failed to scrape {source.name}: {str(e)}")
            return []
    
    async def _upload_to_ragflow(self, task: NewsTask, articles: List[NewsContent]) -> Dict[str, Any]:
        """
        将文章上传到RAGFlow知识库
        
        Args:
            task: 抓取任务
            articles: 文章列表
            
        Returns:
            上传结果
        """
        result = {
            "upload_result": {"data": []},
            "convert_result": {"data": []},
            "parse_result": None
        }
        
        try:
            if not self.ragflow_client:
                raise RuntimeError("RAGFlow client not configured")
            
            # 获取目标知识库
            dataset = self.ragflow_client.get_dataset(task.kb_id)
            if not dataset:
                raise RuntimeError(f"Knowledge base {task.kb_id} not found")
            
            # 创建临时文件夹
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                uploaded_files = []
                
                # 为每篇文章创建文件
                for i, article in enumerate(articles):
                    file_name = f"news_{i+1:04d}_{self._sanitize_filename(article.title)}.txt"
                    file_path = temp_path / file_name
                    
                    # 创建文章内容
                    content = self._format_article_content(article)
                    
                    # 写入文件
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    
                    uploaded_files.append({
                        "name": file_name,
                        "path": str(file_path),
                        "article": article
                    })
                
                logger.info(f"Created {len(uploaded_files)} temporary files")
                
                # 上传文件夹到RAGFlow
                upload_result = dataset.upload_folder(
                    str(temp_path), 
                    "", 
                    auto_parse=task.auto_parse
                )
                
                # 更新文章的文档ID和解析状态
                if upload_result.get("upload_result", {}).get("data"):
                    upload_data = upload_result["upload_result"]["data"]
                    for i, file_info in enumerate(upload_data):
                        if i < len(articles):
                            articles[i].document_id = file_info.get("id")
                            articles[i].parse_status = ParseStatus.PENDING if task.auto_parse else ParseStatus.SUCCESS
                
                result.update(upload_result)
                logger.info(f"Successfully uploaded {len(uploaded_files)} files to RAGFlow")
        
        except Exception as e:
            logger.error(f"Failed to upload to RAGFlow: {str(e)}")
            result["upload_result"] = {"error": str(e)}
        
        return result
    
    def _sanitize_filename(self, filename: str) -> str:
        """
        清理文件名，移除不合法字符
        
        Args:
            filename: 原始文件名
            
        Returns:
            清理后的文件名
        """
        # 移除或替换不合法字符
        import re
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        filename = filename.strip()
        
        # 限制长度
        if len(filename) > 50:
            filename = filename[:50]
        
        return filename or "untitled"
    
    def _format_article_content(self, article: NewsContent) -> str:
        """
        格式化文章内容为RAGFlow可读格式
        
        Args:
            article: 新闻文章
            
        Returns:
            格式化的内容
        """
        content_parts = []
        
        # 添加标题
        content_parts.append(f"标题: {article.title}")
        content_parts.append("")
        
        # 添加元数据
        if article.publish_time:
            content_parts.append(f"发布时间: {article.publish_time.strftime('%Y-%m-%d %H:%M:%S')}")
        
        if article.url:
            content_parts.append(f"原文链接: {article.url}")
        
        if article.metadata.get("author"):
            content_parts.append(f"作者: {article.metadata['author']}")
        
        content_parts.append("")
        
        # 添加摘要（如果有）
        if article.summary:
            content_parts.append("摘要:")
            content_parts.append(article.summary)
            content_parts.append("")
        
        # 添加正文
        content_parts.append("正文:")
        content_parts.append(article.content_text)
        
        # 添加标签（如果有）
        if article.tags:
            content_parts.append("")
            content_parts.append(f"标签: {', '.join(article.tags)}")
        
        return "\n".join(content_parts)
    
    async def stop_task(self, task_id: int) -> bool:
        """
        停止正在运行的任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否成功停止
        """
        if task_id in self.running_tasks:
            task = self.running_tasks[task_id]
            task.status = TaskStatus.FAILED
            task.finished_at = datetime.now()
            del self.running_tasks[task_id]
            logger.info(f"Task {task_id} stopped")
            return True
        
        return False
    
    def get_task_status(self, task_id: int) -> Optional[Dict[str, Any]]:
        """
        获取任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务状态信息
        """
        if task_id in self.running_tasks:
            task = self.running_tasks[task_id]
            return {
                "id": task.id,
                "status": task.status.value,
                "progress": "running",
                "message": "任务正在执行中..."
            }
        
        return None
    
    async def reparse_news_to_kb(self, news_content: NewsContent, kb_id: str) -> Dict[str, Any]:
        """
        重新解析新闻内容到知识库
        
        Args:
            news_content: 新闻内容
            kb_id: 知识库ID
            
        Returns:
            解析结果
        """
        try:
            if not self.ragflow_client:
                raise RuntimeError("RAGFlow client not configured")
            
            # 获取目标知识库
            dataset = self.ragflow_client.get_dataset(kb_id)
            if not dataset:
                raise RuntimeError(f"Knowledge base {kb_id} not found")
            
            # 创建临时文件
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as temp_file:
                content = self._format_article_content(news_content)
                temp_file.write(content)
                temp_file_path = temp_file.name
            
            try:
                # 上传单个文件
                file_name = f"news_{self._sanitize_filename(news_content.title)}.txt"
                upload_result = dataset.upload_file(temp_file_path, file_name, auto_parse=True)
                
                # 更新新闻内容的解析状态
                if upload_result.get("data"):
                    news_content.document_id = upload_result["data"].get("id")
                    news_content.parse_status = ParseStatus.PENDING
                    news_content.kb_id = kb_id
                
                return {
                    "status": "success",
                    "message": "重新解析已开始",
                    "document_id": news_content.document_id
                }
                
            finally:
                # 清理临时文件
                try:
                    os.unlink(temp_file_path)
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"Failed to reparse news content: {str(e)}")
            return {
                "status": "failed",
                "message": str(e)
            }
    
    def get_knowledge_bases(self) -> List[KnowledgeBase]:
        """
        获取可用的知识库列表
        
        Returns:
            知识库列表
        """
        try:
            if not self.ragflow_client:
                return []
            
            # 获取RAGFlow中的数据集
            datasets = self.ragflow_client.list_datasets()
            
            knowledge_bases = []
            for dataset in datasets:
                kb = KnowledgeBase(
                    id=dataset.id,
                    name=dataset.name,
                    description=dataset.description or "",
                    chunk_method=getattr(dataset, 'chunk_method', 'naive'),
                    document_count=getattr(dataset, 'document_count', 0),
                    created_at=getattr(dataset, 'created_at', None),
                    updated_at=getattr(dataset, 'updated_at', None)
                )
                knowledge_bases.append(kb)
            
            return knowledge_bases
            
        except Exception as e:
            logger.error(f"Failed to get knowledge bases: {str(e)}")
            return []
    
    def create_knowledge_base(self, name: str, description: str = "", chunk_method: str = "naive") -> Optional[KnowledgeBase]:
        """
        创建新的知识库
        
        Args:
            name: 知识库名称
            description: 描述
            chunk_method: 分块方法
            
        Returns:
            创建的知识库对象
        """
        try:
            if not self.ragflow_client:
                raise RuntimeError("RAGFlow client not configured")
            
            # 在RAGFlow中创建数据集
            dataset = self.ragflow_client.create_dataset(
                name=name,
                description=description,
                chunk_method=chunk_method
            )
            
            # 创建知识库对象
            kb = KnowledgeBase(
                id=dataset.id,
                name=dataset.name,
                description=description,
                chunk_method=chunk_method,
                created_at=datetime.now()
            )
            
            logger.info(f"Created knowledge base: {name} ({kb.id})")
            return kb
            
        except Exception as e:
            logger.error(f"Failed to create knowledge base: {str(e)}")
            return None
