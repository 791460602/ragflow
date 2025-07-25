#
#  新闻到文档集成服务
#
#  将新闻内容直接集成到RAGFlow的文档系统中，避免重复存储
#

import hashlib
import time
import io
from datetime import datetime
from typing import List, Optional, Dict, Any

from api.db import FileType, ParserType
from api.db.db_models import DB, NewsSource, NewsTask, NewsContent, Document, File, File2Document
from api.db.services.common_service import CommonService
from api.db.services.document_service import DocumentService
from api.db.services.file_service import FileService
from api.db.services.file2document_service import File2DocumentService
from api.db.services.knowledgebase_service import KnowledgebaseService
from api.utils import current_timestamp, get_uuid
from api.utils.news_fetcher import NewsTaskExecutor
from rag.utils.storage_factory import STORAGE_IMPL
import logging

logger = logging.getLogger(__name__)


class NewsDocumentIntegrationService:
    """新闻文档集成服务 - 将新闻直接转为RAGFlow文档"""
    
    @classmethod
    @DB.connection_context()
    def create_news_folder_structure(cls, kb_id: str, tenant_id: str, user_id: str) -> str:
        """创建新闻收集专用的文件夹结构"""
        
        # 获取知识库信息
        kb = KnowledgebaseService.get_by_id(kb_id)
        if not kb:
            raise ValueError("知识库不存在")
        
        # 创建新闻根文件夹
        news_root_folder_id = get_uuid()
        news_folder_data = {
            "id": news_root_folder_id,
            "parent_id": "",  # 根目录
            "tenant_id": tenant_id,
            "created_by": user_id,
            "name": "📰 新闻收集",
            "type": FileType.FOLDER.value,
            "source_type": "news_collector",
            "size": 0,
            "location": "",
            "create_time": current_timestamp(),
            "create_date": datetime.now(),
            "update_time": current_timestamp(),
            "update_date": datetime.now()
        }
        
        news_folder = File.create(**news_folder_data)
        logger.info(f"创建新闻根文件夹: {news_root_folder_id}")
        
        return news_root_folder_id
    
    @classmethod
    @DB.connection_context()
    def create_source_folder(cls, source: NewsSource, parent_folder_id: str) -> str:
        """为每个新闻源创建专用文件夹"""
        
        source_folder_id = get_uuid()
        folder_name = f"📡 {source.name}"
        
        folder_data = {
            "id": source_folder_id,
            "parent_id": parent_folder_id,
            "tenant_id": source.tenant_id,
            "created_by": source.user_id,
            "name": folder_name,
            "type": FileType.FOLDER.value,
            "source_type": "news_source",
            "size": 0,
            "location": f"news_source_{source.id}",
            "create_time": current_timestamp(),
            "create_date": datetime.now(),
            "update_time": current_timestamp(),
            "update_date": datetime.now()
        }
        
        folder = File.create(**folder_data)
        logger.info(f"创建新闻源文件夹: {source.name} -> {source_folder_id}")
        
        return source_folder_id
    
    @classmethod
    @DB.connection_context()
    def convert_news_to_document(cls, news_data: Dict[str, Any], task: NewsTask, 
                                source: NewsSource, source_folder_id: str) -> tuple:
        """将新闻数据转换为Document和File"""
        
        # 生成唯一标识
        content_hash = hashlib.md5((news_data["title"] + news_data["url"]).encode('utf-8')).hexdigest()
        
        # 检查是否已存在相同内容
        existing_news = NewsContent.select().where(
            NewsContent.content_hash == content_hash,
            NewsContent.tenant_id == task.tenant_id
        ).first()
        
        if existing_news:
            logger.info(f"新闻已存在，跳过: {news_data['title']}")
            return None, None
        
        # 创建文件记录
        file_id = get_uuid()
        file_name = cls._sanitize_filename(news_data["title"]) + ".txt"
        
        file_data = {
            "id": file_id,
            "parent_id": source_folder_id,
            "tenant_id": task.tenant_id,
            "created_by": task.user_id,
            "name": file_name,
            "type": FileType.TEXT.value,
            "source_type": "news_article",
            "size": len(news_data.get("content", "")),
            "location": f"news/{task.id}/{file_id}.txt",
            "create_time": current_timestamp(),
            "create_date": datetime.now(),
            "update_time": current_timestamp(),
            "update_date": datetime.now()
        }
        
        file_obj = File.create(**file_data)
        
        # 创建文档记录
        doc_id = get_uuid()
        doc_data = {
            "id": doc_id,
            "kb_id": task.kb_id,
            "parser_id": ParserType.NAIVE.value,
            "parser_config": {"pages": [[1, 1000000]]},
            "source_type": "news_collector",
            "type": FileType.TEXT.value,
            "created_by": task.user_id,
            "name": news_data["title"],
            "location": file_data["location"],
            "size": file_data["size"],
            "token_num": 0,
            "chunk_num": 0,
            "progress": 0,
            "progress_msg": "等待处理",
            "run": "0",  # 准备运行
            "status": "1",  # 有效
            "suffix": "txt",
            "meta_fields": {
                "source_url": news_data["url"],
                "author": news_data.get("author"),
                "publish_time": news_data.get("publish_time"),
                "news_source": source.name,
                "category": news_data.get("category", "")
            },
            "create_time": current_timestamp(),
            "create_date": datetime.now(),
            "update_time": current_timestamp(),
            "update_date": datetime.now()
        }
        
        document = Document.create(**doc_data)
        
        # 创建文件和文档的关联关系
        file2doc_data = {
            "id": get_uuid(),
            "file_id": file_id,
            "document_id": doc_id
        }
        File2Document.create(**file2doc_data)
        
        # 保存新闻内容到存储系统
        content_text = cls._format_news_content(news_data, source)
        cls._save_news_content_to_storage(file_data["location"], content_text)
        
        # 创建新闻内容记录（元数据）
        news_content_data = {
            "id": get_uuid(),
            "task_id": task.id,
            "source_id": source.id,
            "document_id": doc_id,
            "user_id": task.user_id,
            "tenant_id": task.tenant_id,
            "original_url": news_data["url"],
            "author": news_data.get("author"),
            "publish_time": news_data.get("publish_time"),
            "fetch_time": current_timestamp(),
            "category": news_data.get("category", ""),
            "tags": news_data.get("tags", []),
            "summary": news_data.get("summary", ""),
            "content_hash": content_hash,
            "word_count": len(news_data.get("content", "")),
            "create_time": current_timestamp(),
            "create_date": datetime.now(),
            "update_time": current_timestamp(),
            "update_date": datetime.now()
        }
        
        news_content = NewsContent.create(**news_content_data)
        
        logger.info(f"新闻转换为文档成功: {news_data['title']} -> {doc_id}")
        return document, news_content
    
    @classmethod
    def _sanitize_filename(cls, title: str) -> str:
        """清理文件名，移除非法字符"""
        import re
        # 移除或替换非法字符
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', title)
        # 限制长度
        if len(sanitized) > 100:
            sanitized = sanitized[:100]
        return sanitized
    
    @classmethod
    def _format_news_content(cls, news_data: Dict[str, Any], source: NewsSource) -> str:
        """格式化新闻内容为文本格式"""
        content_parts = [
            f"标题: {news_data['title']}",
            f"来源: {source.name}",
            f"原文链接: {news_data['url']}",
            f"作者: {news_data.get('author', '未知')}",
            f"发布时间: {datetime.fromtimestamp(news_data.get('publish_time', time.time())).strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "正文内容:",
            "=" * 50,
            news_data.get('content', ''),
            "",
            "=" * 50,
            f"抓取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        ]
        
        return "\n".join(content_parts)
    
    @classmethod
    def _save_news_content_to_storage(cls, location: str, content: str):
        """保存新闻内容到存储系统"""
        try:
            content_bytes = content.encode('utf-8')
            content_io = io.BytesIO(content_bytes)
            STORAGE_IMPL.put(location, content_io)
            logger.info(f"新闻内容已保存到存储: {location}")
        except Exception as e:
            logger.error(f"保存新闻内容失败: {e}")
            raise
    
    @classmethod
    @DB.connection_context()
    def execute_news_task_with_integration(cls, task_id: str) -> Dict[str, Any]:
        """执行新闻抓取任务并集成到文档系统"""
        
        # 获取任务信息
        task = NewsTask.get_by_id(task_id)
        if not task:
            raise ValueError("任务不存在")
        
        if task.status == "running":
            raise ValueError("任务正在运行中")
        
        # 更新任务状态
        NewsTask.update(
            status="running",
            last_run_time=current_timestamp(),
            update_time=current_timestamp(),
            update_date=datetime.now()
        ).where(NewsTask.id == task_id).execute()
        
        try:
            # 获取新闻源信息
            sources = NewsSource.select().where(
                NewsSource.id.in_(task.source_ids),
                NewsSource.tenant_id == task.tenant_id,
                NewsSource.status == "active"
            )
            
            if not sources:
                raise ValueError("没有找到有效的新闻源")
            
            # 创建新闻文件夹结构
            news_root_folder = cls.create_news_folder_structure(
                task.kb_id, task.tenant_id, task.user_id
            )
            
            # 执行抓取任务
            executor = NewsTaskExecutor()
            results = {
                "total_articles": 0,
                "success_count": 0,
                "failed_count": 0,
                "skipped_count": 0
            }
            
            for source in sources:
                try:
                    # 为每个新闻源创建文件夹
                    source_folder_id = cls.create_source_folder(source, news_root_folder)
                    
                    # 抓取新闻
                    source_config = {
                        "url": source.url,
                        "fetch_config": source.fetch_config
                    }
                    
                    fetch_results = executor.execute_task(
                        {"max_articles_per_source": task.max_articles_per_source},
                        [source_config]
                    )
                    
                    # 转换新闻为文档
                    for article_data in fetch_results.get("articles", []):
                        try:
                            document, news_content = cls.convert_news_to_document(
                                article_data, task, source, source_folder_id
                            )
                            
                            if document and news_content:
                                results["success_count"] += 1
                                
                                # 如果启用自动解析，触发文档解析
                                if task.auto_parse:
                                    cls._trigger_document_parsing(document.id)
                            else:
                                results["skipped_count"] += 1
                                
                        except Exception as e:
                            logger.error(f"转换新闻失败: {e}")
                            results["failed_count"] += 1
                    
                    results["total_articles"] += len(fetch_results.get("articles", []))
                    
                    # 更新新闻源统计
                    NewsSource.update(
                        total_articles=NewsSource.total_articles + len(fetch_results.get("articles", [])),
                        last_fetch_time=current_timestamp(),
                        update_time=current_timestamp(),
                        update_date=datetime.now()
                    ).where(NewsSource.id == source.id).execute()
                    
                except Exception as e:
                    logger.error(f"处理新闻源失败 {source.name}: {e}")
                    results["failed_count"] += 1
            
            # 更新任务状态为完成
            NewsTask.update(
                status="completed",
                statistics=results,
                update_time=current_timestamp(),
                update_date=datetime.now()
            ).where(NewsTask.id == task_id).execute()
            
            logger.info(f"新闻任务执行完成: {task_id}, 结果: {results}")
            return results
            
        except Exception as e:
            # 更新任务状态为失败
            NewsTask.update(
                status="failed",
                error_message=str(e),
                update_time=current_timestamp(),
                update_date=datetime.now()
            ).where(NewsTask.id == task_id).execute()
            
            logger.error(f"新闻任务执行失败: {e}")
            raise
    
    @classmethod
    def _trigger_document_parsing(cls, doc_id: str):
        """触发文档解析"""
        try:
            # 更新文档状态为准备解析
            Document.update(
                run="1",  # 开始运行解析
                progress_msg="准备解析...",
                update_time=current_timestamp(),
                update_date=datetime.now()
            ).where(Document.id == doc_id).execute()
            
            logger.info(f"已触发文档解析: {doc_id}")
            
        except Exception as e:
            logger.error(f"触发文档解析失败: {e}")
    
    @classmethod
    @DB.connection_context()
    def get_news_documents_by_task(cls, task_id: str) -> List[Dict[str, Any]]:
        """获取任务产生的所有文档"""
        
        news_contents = NewsContent.select().where(
            NewsContent.task_id == task_id
        )
        
        documents = []
        for news in news_contents:
            if news.document_id:
                doc = Document.get_by_id(news.document_id)
                if doc:
                    doc_dict = doc.to_dict()
                    doc_dict.update({
                        "news_url": news.original_url,
                        "news_author": news.author,
                        "news_category": news.category,
                        "publish_time": news.publish_time
                    })
                    documents.append(doc_dict)
        
        return documents
