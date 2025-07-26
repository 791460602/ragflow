"""
新闻收集器API - 基于RAGFlow SDK架构

使用现有的@token_required认证，支持多种外部爬虫工具
"""

from flask import request
from api.utils.api_utils import get_json_result, server_error_response, token_required
from api.db.services.knowledgebase_service import KnowledgebaseService
from api.db.services.file_service import FileService
from api.db.services.document_service import DocumentService
from api.db.services.file2document_service import File2DocumentService
from api.utils import get_uuid
from api.db import FileType
from datetime import datetime
import tempfile
import os
import json
from pathlib import Path

# 导入爬虫接口和实现
from api.interfaces.news_crawler_interface import NewsSource, CrawlTask, CrawlerStatus
from api.crawlers.news_crawler_implementations import (
    ScrapyNewsCrawler, 
    Newspaper3kCrawler, 
    DemoCrawler
)


# 爬虫工厂类
class CrawlerFactory:
    """爬虫工厂，根据类型创建相应的爬虫实例"""
    
    _crawlers = {
        "scrapy": ScrapyNewsCrawler,
        "newspaper": Newspaper3kCrawler,
        "demo": DemoCrawler
    }
    
    @classmethod
    def create_crawler(cls, crawler_type: str, **kwargs):
        """创建爬虫实例"""
        if crawler_type not in cls._crawlers:
            raise ValueError(f"不支持的爬虫类型: {crawler_type}")
        
        return cls._crawlers[crawler_type](**kwargs)
    
    @classmethod
    def get_supported_types(cls) -> list:
        """获取支持的爬虫类型"""
        return list(cls._crawlers.keys())


# 新闻收集器核心类
class NewsCollector:
    """新闻收集器核心类 - 支持多种外部爬虫工具"""
    
    @staticmethod
    def execute_crawl_task(sources_config: list, output_dir: str, crawler_type: str = "demo", max_articles: int = 5) -> dict:
        """执行爬虫任务 - 使用指定的爬虫工具"""
        try:
            # 创建爬虫实例
            crawler = CrawlerFactory.create_crawler(crawler_type)
            
            # 转换为NewsSource对象
            news_sources = []
            for source_config in sources_config:
                news_source = NewsSource(
                    id=get_uuid(),
                    name=source_config.get("name", "未知来源"),
                    url=source_config.get("url", ""),
                    crawler_config=source_config.get("config", {})
                )
                news_sources.append(news_source)
            
            # 创建爬取任务
            crawl_task = CrawlTask(
                task_id=get_uuid(),
                sources=news_sources,
                output_directory=output_dir,
                max_articles_per_source=max_articles,
                crawler_config={}
            )
            
            # 执行爬取
            crawl_result = crawler.crawl_articles(crawl_task)
            
            return {
                "success": crawl_result.status == CrawlerStatus.COMPLETED,
                "task_id": crawl_result.task_id,
                "status": crawl_result.status.value,
                "total_articles": crawl_result.total_articles,
                "success_count": crawl_result.success_count,
                "failed_count": crawl_result.failed_count,
                "skipped_count": crawl_result.skipped_count,
                "output_directory": crawl_result.output_directory,
                "error_message": crawl_result.error_message,
                "crawler_type": crawler_type
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "crawler_type": crawler_type
            }
    
    @staticmethod
    def upload_to_ragflow(output_dir: str, kb_id: str, tenant_id: str) -> dict:
        """将爬取结果上传到RAGFlow知识库"""
        try:
            uploaded_files = []
            
            # 遍历输出目录中的所有.md文件
            for root, dirs, files in os.walk(output_dir):
                for file in files:
                    if file.endswith('.md'):
                        file_path = os.path.join(root, file)
                        
                        # 读取文件内容
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        # 获取文件大小
                        file_size = os.path.getsize(file_path)
                        
                        # 创建文件记录
                        file_record = FileService.insert({
                            "id": get_uuid(),
                            "parent_id": FileService.get_root_folder(tenant_id)["id"],
                            "tenant_id": tenant_id,
                            "created_by": tenant_id,
                            "type": FileType.OTHER.value,
                            "name": file,
                            "location": file_path,
                            "size": file_size,
                        })
                        
                        # 创建文档记录
                        doc = DocumentService.insert({
                            "id": get_uuid(),
                            "kb_id": kb_id,
                            "parser_id": "markdown",
                            "parser_config": {},
                            "created_by": tenant_id,
                            "type": FileType.OTHER.value,
                            "name": file,
                            "suffix": "md",
                            "location": file_path,
                            "size": file_size
                        })
                        
                        # 创建文件到文档的映射
                        File2DocumentService.insert({
                            "id": get_uuid(),
                            "file_id": file_record.id,
                            "document_id": doc.id,
                        })
                        
                        uploaded_files.append({
                            "file_id": file_record.id,
                            "document_id": doc.id,
                            "name": file,
                            "size": file_size
                        })
            
            return {
                "success": True,
                "uploaded_files": len(uploaded_files),
                "files": uploaded_files
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }


# 全局任务存储（简化版，生产环境应使用数据库）
news_tasks = {}


@manager.route('/ping', methods=['GET'])  # noqa: F821
@token_required
def ping(tenant_id):
    """
    测试新闻收集器服务状态
    ---
    tags:
      - News Collector
    security:
      - ApiKeyAuth: []
    responses:
      200:
        description: 服务状态信息
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 0
            data:
              type: object
              properties:
                status:
                  type: string
                  example: "running"
                version:
                  type: string
                  example: "1.0.0"
                tenant_id:
                  type: string
                supported_crawlers:
                  type: array
                  items:
                    type: string
    """
    try:
        return get_json_result(data={
            "status": "running",
            "version": "2.0.0",
            "architecture": "external_crawlers",
            "tenant_id": tenant_id,
            "supported_crawlers": CrawlerFactory.get_supported_types(),
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return server_error_response(e)


@manager.route('/crawlers', methods=['GET'])  # noqa: F821
@token_required
def get_crawler_types(tenant_id):
    """
    获取支持的爬虫类型
    ---
    tags:
      - News Collector
    security:
      - ApiKeyAuth: []
    responses:
      200:
        description: 爬虫类型列表
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 0
            data:
              type: object
              properties:
                crawlers:
                  type: array
                  items:
                    type: object
                    properties:
                      type:
                        type: string
                      description:
                        type: string
    """
    try:
        crawler_info = [
            {
                "type": "demo", 
                "description": "演示爬虫 - 生成示例新闻数据"
            },
            {
                "type": "scrapy", 
                "description": "Scrapy爬虫 - 适用于复杂网站爬取"
            },
            {
                "type": "newspaper", 
                "description": "Newspaper3k爬虫 - 适用于新闻网站文章提取"
            }
        ]
        
        return get_json_result(data={
            "crawlers": crawler_info,
            "total": len(crawler_info)
        })
    except Exception as e:
        return server_error_response(e)


@manager.route('/sources', methods=['POST'])  # noqa: F821
@token_required
def create_news_source(tenant_id):
    """
    创建新闻源
    ---
    tags:
      - News Collector
    security:
      - ApiKeyAuth: []
    parameters:
      - in: body
        name: body
        description: 新闻源配置
        required: true
        schema:
          type: object
          properties:
            name:
              type: string
              description: 新闻源名称
            url:
              type: string
              description: 新闻源URL
            description:
              type: string
              description: 新闻源描述
            crawler_type:
              type: string
              enum: ["demo", "scrapy", "newspaper"]
              default: "demo"
              description: 爬虫类型
    responses:
      200:
        description: 新闻源创建成功
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 0
            data:
              type: object
              properties:
                source_id:
                  type: string
                name:
                  type: string
                url:
                  type: string
    """
    try:
        req = request.json
        if not req or 'name' not in req or 'url' not in req:
            return get_json_result(data=False, message='缺少必需参数: name, url', code=400)
        
        # 简化版：直接返回生成的ID（实际项目中应存储到数据库）
        source_id = get_uuid()
        
        source_data = {
            "id": source_id,
            "name": req["name"],
            "url": req["url"],
            "description": req.get("description", ""),
            "crawler_type": req.get("crawler_type", "demo"),
            "tenant_id": tenant_id,
            "created_at": datetime.now().isoformat(),
            "status": "active"
        }
        
        return get_json_result(data=source_data)
        
    except Exception as e:
        return server_error_response(e)


@manager.route('/tasks', methods=['POST'])  # noqa: F821
@token_required
def create_news_task(tenant_id):
    """
    创建新闻抓取任务
    ---
    tags:
      - News Collector
    security:
      - ApiKeyAuth: []
    parameters:
      - in: body
        name: body
        description: 抓取任务配置
        required: true
        schema:
          type: object
          properties:
            task_name:
              type: string
              description: 任务名称
            kb_id:
              type: string
              description: 知识库ID
            sources:
              type: array
              items:
                type: object
                properties:
                  name:
                    type: string
                  url:
                    type: string
              description: 新闻源列表
            max_articles:
              type: integer
              default: 5
              description: 每个源最大文章数
            crawler_type:
              type: string
              enum: ["demo", "scrapy", "newspaper"]
              default: "demo"
              description: 爬虫类型
    responses:
      200:
        description: 任务创建成功
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 0
            data:
              type: object
              properties:
                task_id:
                  type: string
                status:
                  type: string
                  example: "created"
    """
    try:
        req = request.json
        if not req or 'task_name' not in req or 'kb_id' not in req or 'sources' not in req:
            return get_json_result(data=False, message='缺少必需参数: task_name, kb_id, sources', code=400)
        
        # 验证爬虫类型
        crawler_type = req.get("crawler_type", "demo")
        if crawler_type not in CrawlerFactory.get_supported_types():
            return get_json_result(data=False, message=f'不支持的爬虫类型: {crawler_type}', code=400)
        
        # 验证知识库是否存在且属于当前租户
        e, kb = KnowledgebaseService.get_by_id(req["kb_id"])
        if not e:
            return get_json_result(data=False, message="知识库不存在", code=404)
        
        if kb.tenant_id != tenant_id:
            return get_json_result(data=False, message="无权访问此知识库", code=403)
        
        # 创建任务
        task_id = get_uuid()
        task_data = {
            "id": task_id,
            "name": req["task_name"],
            "kb_id": req["kb_id"],
            "sources": req["sources"],
            "crawler_type": crawler_type,
            "max_articles": req.get("max_articles", 5),
            "tenant_id": tenant_id,
            "status": "created",
            "created_at": datetime.now().isoformat()
        }
        
        # 存储任务（简化版）
        news_tasks[task_id] = task_data
        
        return get_json_result(data={
            "task_id": task_id,
            "status": "created",
            "message": "任务创建成功"
        })
        
    except Exception as e:
        return server_error_response(e)


@manager.route('/tasks/<task_id>/execute', methods=['POST'])  # noqa: F821
@token_required
def execute_news_task(tenant_id, task_id):
    """
    执行新闻抓取任务
    ---
    tags:
      - News Collector
    security:
      - ApiKeyAuth: []
    parameters:
      - in: path
        name: task_id
        type: string
        required: true
        description: 任务ID
    responses:
      200:
        description: 任务执行结果
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 0
            data:
              type: object
              properties:
                task_id:
                  type: string
                status:
                  type: string
                crawl_result:
                  type: object
                upload_result:
                  type: object
    """
    try:
        # 获取任务信息
        if task_id not in news_tasks:
            return get_json_result(data=False, message="任务不存在", code=404)
        
        task = news_tasks[task_id]
        
        # 验证任务属于当前租户
        if task["tenant_id"] != tenant_id:
            return get_json_result(data=False, message="无权访问此任务", code=403)
        
        # 更新任务状态
        task["status"] = "running"
        task["started_at"] = datetime.now().isoformat()
        
        # 创建临时输出目录
        output_dir = tempfile.mkdtemp(prefix=f"news_crawler_{task_id}_")
        
        # 执行爬虫 - 使用用户指定的爬虫类型
        crawler_type = task.get("crawler_type", "demo")
        crawl_result = NewsCollector.execute_crawl_task(
            sources_config=task["sources"],
            output_dir=output_dir,
            crawler_type=crawler_type,
            max_articles=task["max_articles"]
        )
        
        upload_result = None
        if crawl_result["success"]:
            # 上传到RAGFlow
            upload_result = NewsCollector.upload_to_ragflow(
                output_dir=output_dir,
                kb_id=task["kb_id"],
                tenant_id=tenant_id
            )
            
            if upload_result["success"]:
                task["status"] = "completed"
            else:
                task["status"] = "upload_failed"
        else:
            task["status"] = "failed"
        
        task["completed_at"] = datetime.now().isoformat()
        task["crawl_result"] = crawl_result
        task["upload_result"] = upload_result
        
        return get_json_result(data={
            "task_id": task_id,
            "status": task["status"],
            "crawl_result": crawl_result,
            "upload_result": upload_result
        })
        
    except Exception as e:
        return server_error_response(e)


@manager.route('/tasks/<task_id>', methods=['GET'])  # noqa: F821
@token_required
def get_task_status(tenant_id, task_id):
    """
    查询任务状态
    ---
    tags:
      - News Collector
    security:
      - ApiKeyAuth: []
    parameters:
      - in: path
        name: task_id
        type: string
        required: true
        description: 任务ID
    responses:
      200:
        description: 任务状态信息
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 0
            data:
              type: object
              properties:
                task_id:
                  type: string
                status:
                  type: string
                progress:
                  type: object
    """
    try:
        if task_id not in news_tasks:
            return get_json_result(data=False, message="任务不存在", code=404)
        
        task = news_tasks[task_id]
        
        # 验证任务属于当前租户
        if task["tenant_id"] != tenant_id:
            return get_json_result(data=False, message="无权访问此任务", code=403)
        
        # 计算统计信息
        statistics = {}
        if "crawl_result" in task:
            statistics = {
                "total_articles": task["crawl_result"].get("total_articles", 0),
                "sources_processed": task["crawl_result"].get("sources_processed", 0)
            }
        
        if "upload_result" in task:
            statistics["uploaded_files"] = task["upload_result"].get("uploaded_files", 0)
        
        return get_json_result(data={
            "task_id": task_id,
            "name": task["name"],
            "status": task["status"],
            "created_at": task["created_at"],
            "statistics": statistics
        })
        
    except Exception as e:
        return server_error_response(e)


@manager.route('/tasks', methods=['GET'])  # noqa: F821
@token_required
def list_news_tasks(tenant_id):
    """
    获取任务列表
    ---
    tags:
      - News Collector
    security:
      - ApiKeyAuth: []
    parameters:
      - in: query
        name: page
        type: integer
        default: 1
        description: 页码
      - in: query
        name: page_size
        type: integer
        default: 10
        description: 每页数量
    responses:
      200:
        description: 任务列表
        schema:
          type: object
          properties:
            code:
              type: integer
              example: 0
            data:
              type: object
              properties:
                tasks:
                  type: array
                  items:
                    type: object
                total:
                  type: integer
    """
    try:
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 10))
        
        # 过滤当前租户的任务
        tenant_tasks = [task for task in news_tasks.values() if task["tenant_id"] == tenant_id]
        
        # 排序（按创建时间倒序）
        tenant_tasks.sort(key=lambda x: x["created_at"], reverse=True)
        
        # 分页
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_tasks = tenant_tasks[start_idx:end_idx]
        
        # 简化任务信息
        simplified_tasks = []
        for task in page_tasks:
            simplified_task = {
                "task_id": task["id"],
                "name": task["name"],
                "status": task["status"],
                "created_at": task["created_at"],
                "sources_count": len(task["sources"])
            }
            
            if "crawl_result" in task:
                simplified_task["total_articles"] = task["crawl_result"].get("total_articles", 0)
            
            simplified_tasks.append(simplified_task)
        
        return get_json_result(data={
            "tasks": simplified_tasks,
            "total": len(tenant_tasks),
            "page": page,
            "page_size": page_size
        })
        
    except Exception as e:
        return server_error_response(e)
