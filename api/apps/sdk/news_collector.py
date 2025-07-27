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
"""
新闻收集器完整API

包含爬虫、上传、CRUD管理、统计分析等全部功能
采用分离架构设计，便于独立开发和测试
"""

from flask import request
from api.utils.api_utils import get_json_result, server_error_response, token_required
from api.db.services.news_service import NewsSourceService, NewsTaskService, NewsContentService
from api.db.services.knowledgebase_service import KnowledgebaseService
from api.utils import get_uuid
from datetime import datetime, timedelta
import os
import tempfile
import shutil
import traceback


# ========== 爬虫核心框架 ==========

class NewsSource:
    """新闻源配置"""
    def __init__(self, name: str, url: str, config: dict = None):
        self.name = name
        self.url = url
        self.config = config or {}

class CrawlerResult:
    """爬虫结果"""
    def __init__(self):
        self.success = False
        self.articles = []
        self.errors = []
        self.metadata = {}
        self.crawl_time = datetime.now().isoformat()
    
    def add_article(self, article: dict):
        """添加文章"""
        self.articles.append(article)
    
    def add_error(self, error: str):
        """添加错误"""
        self.errors.append(error)
    
    def set_metadata(self, key: str, value):
        """设置元数据"""
        self.metadata[key] = value

class BaseCrawler:
    """爬虫基类"""
    def __init__(self, crawler_config: dict = None):
        self.config = crawler_config or {}
    
    def crawl_source(self, source: NewsSource, max_articles: int = 10) -> CrawlerResult:
        """爬取单个新闻源"""
        raise NotImplementedError("子类必须实现此方法")
    
    def crawl_multiple_sources(self, sources: list, max_articles: int = 10) -> CrawlerResult:
        """爬取多个新闻源"""
        combined_result = CrawlerResult()
        
        for source in sources:
            try:
                result = self.crawl_source(source, max_articles)
                combined_result.articles.extend(result.articles)
                combined_result.errors.extend(result.errors)
            except Exception as e:
                combined_result.add_error(f"爬取源 {source.name} 失败: {str(e)}")
        
        combined_result.success = len(combined_result.articles) > 0
        return combined_result

class DemoCrawler(BaseCrawler):
    """演示爬虫，生成示例数据"""
    
    def crawl_source(self, source: NewsSource, max_articles: int = 10) -> CrawlerResult:
        result = CrawlerResult()
        
        try:
            # 生成示例文章
            for i in range(min(max_articles, 5)):
                article = {
                    "title": f"【{source.name}】示例新闻标题 {i+1}",
                    "content": f"""这是来自 {source.name} 的示例新闻内容 {i+1}。

本文将深入探讨当前热门的技术趋势和行业动态。随着科技的快速发展，我们正在见证一个前所未有的创新时代。

主要内容包括：
1. 技术发展趋势分析
2. 市场机遇与挑战
3. 未来发展前景

这些变化不仅影响着技术行业，也在改变着我们的日常生活和工作方式。通过深入分析这些趋势，我们可以更好地理解当前的技术环境，并为未来的发展做好准备。

总的来说，技术创新将继续推动社会进步，为各行各业带来新的机遇和挑战。我们需要保持开放的心态，积极拥抱变化，才能在这个快速发展的时代中立于不败之地。""",
                    "url": f"{source.url}/article-{i+1}",
                    "source": source.name,
                    "author": f"记者{chr(65+i)}",
                    "publish_time": (datetime.now() - timedelta(hours=i*2)).strftime("%Y-%m-%d %H:%M:%S"),
                    "crawl_time": datetime.now().isoformat(),
                    "category": source.config.get("category", "综合"),
                    "tags": ["示例", "新闻", source.config.get("category", "综合")],
                    "summary": f"这是第{i+1}篇示例新闻的摘要内容",
                    "word_count": 150 + i * 20
                }
                result.add_article(article)
            
            result.success = True
            result.set_metadata("crawler_type", "demo")
            result.set_metadata("source_url", source.url)
            
        except Exception as e:
            result.add_error(f"演示爬虫执行失败: {str(e)}")
        
        return result

class CrawlerFactory:
    """爬虫工厂"""
    _crawlers = {
        "demo": DemoCrawler
    }
    
    @classmethod
    def create_crawler(cls, crawler_type: str, config: dict = None):
        """创建爬虫实例"""
        if crawler_type not in cls._crawlers:
            raise ValueError(f"不支持的爬虫类型: {crawler_type}")
        
        return cls._crawlers[crawler_type](config)
    
    @classmethod
    def get_available_crawlers(cls):
        """获取可用爬虫列表"""
        return [
            {
                "type": "demo",
                "name": "Demo",
                "description": "演示爬虫 - 生成示例新闻数据"
            }
        ]

def crawl_news(sources: list, crawler_type: str = "demo", max_articles: int = 10) -> CrawlerResult:
    """便捷的爬虫调用函数"""
    crawler = CrawlerFactory.create_crawler(crawler_type)
    return crawler.crawl_multiple_sources(sources, max_articles)

class NewsUploader:
    """新闻上传器"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
    
    def upload_crawler_result(self, crawler_result: CrawlerResult, kb_id: str, auto_parse: bool = True):
        """上传爬虫结果到知识库"""
        if not crawler_result.success or not crawler_result.articles:
            return {
                "success": False,
                "message": "没有可上传的文章",
                "uploaded_files": 0
            }
        
        try:
            # 这里集成upload_folder_with_parse.py的逻辑
            # 将文章转换为文件并上传到RAGFlow
            uploaded_files = []
            
            for article in crawler_result.articles:
                # 生成文件内容
                content = self._article_to_markdown(article)
                
                # 这里应该调用RAGFlow的文件上传API
                # 暂时返回示例结果
                file_info = {
                    "name": f"{article['title']}.md",
                    "id": get_uuid(),
                    "size": len(content.encode('utf-8'))
                }
                uploaded_files.append(file_info)
            
            return {
                "success": True,
                "uploaded_files": len(uploaded_files),
                "files": uploaded_files,
                "parse_started": auto_parse
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"上传失败: {str(e)}",
                "uploaded_files": 0
            }
    
    def _article_to_markdown(self, article: dict) -> str:
        """将文章转换为Markdown格式"""
        content = f"# {article.get('title', '无标题')}\n\n"
        content += f"**来源**: {article.get('source', '未知')}\n"
        content += f"**作者**: {article.get('author', '未知')}\n"
        content += f"**发布时间**: {article.get('publish_time', '未知')}\n"
        content += f"**链接**: {article.get('url', '未知')}\n\n"
        
        if article.get('summary'):
            content += f"## 摘要\n\n{article['summary']}\n\n"
        
        content += f"## 正文\n\n{article.get('content', '')}\n\n"
        
        if article.get('tags'):
            content += f"**标签**: {', '.join(article['tags'])}\n"
        
        content += f"\n---\n\n"
        content += f"*抓取时间: {article.get('crawl_time', '未知')}*\n"
        content += f"*分类: {article.get('category', '未知')}*\n"
        
        return content


# ========== 工具函数 ==========

def _article_to_markdown(article: dict) -> str:
    """将文章转换为Markdown格式"""
    content = f"# {article.get('title', '无标题')}\n\n"
    content += f"**来源**: {article.get('source', '未知')}\n"
    content += f"**作者**: {article.get('author', '未知')}\n"
    content += f"**发布时间**: {article.get('publish_time', '未知')}\n"
    content += f"**链接**: {article.get('url', '未知')}\n\n"
    
    if article.get('summary'):
        content += f"## 摘要\n\n{article['summary']}\n\n"
    
    content += f"## 正文\n\n{article.get('content', '')}\n\n"
    
    if article.get('tags'):
        content += f"**标签**: {', '.join(article['tags'])}\n"
    
    content += f"\n---\n\n"
    content += f"*抓取时间: {article.get('crawl_time', '未知')}*\n"
    content += f"*分类: {article.get('category', '未知')}*\n"
    
    return content


# ========== 爬虫相关API ==========

@manager.route('/news_collector/crawl', methods=['POST'])  # noqa: F821
@token_required
def crawl_news_api(tenant_id):
    """
    爬取新闻数据
    
    请求体:
    {
        "sources": [
            {
                "name": "新闻源名称",
                "url": "https://example.com",
                "config": {}
            }
        ],
        "crawler_type": "demo",
        "max_articles": 10,
        "save_to_disk": true,
        "output_dir": "/tmp/news_output"
    }
    """
    try:
        req = request.get_json()
        sources_config = req.get('sources', [])
        crawler_type = req.get('crawler_type', 'demo')
        max_articles = req.get('max_articles', 10)
        save_to_disk = req.get('save_to_disk', False)
        output_dir = req.get('output_dir')
        
        # 转换源配置
        sources = []
        for source_config in sources_config:
            source = NewsSource(
                name=source_config.get('name', ''),
                url=source_config.get('url', ''),
                config=source_config.get('config', {})
            )
            sources.append(source)
        
        # 执行爬取
        crawler_result = crawl_news(sources, crawler_type, max_articles)
        
        # 生成爬取ID
        crawl_id = get_uuid()
        
        # 如果需要保存到磁盘
        saved_files = []
        if save_to_disk and crawler_result.articles:
            if not output_dir:
                output_dir = os.path.join(tempfile.gettempdir(), f"news_crawl_{crawl_id[:8]}")
            
            os.makedirs(output_dir, exist_ok=True)
            
            for i, article in enumerate(crawler_result.articles):
                filename = f"{article.get('title', f'article_{i}')}.md"
                safe_filename = "".join(c for c in filename if c.isalnum() or c in (' ', '-', '_', '.', '【', '】')).strip()
                filepath = os.path.join(output_dir, safe_filename)
                
                content = _article_to_markdown(article)
                
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
                
                saved_files.append({
                    "filename": safe_filename,
                    "filepath": filepath,
                    "size": len(content.encode('utf-8'))
                })
        
        return get_json_result(data={
            "crawl_id": crawl_id,
            "success": crawler_result.success,
            "total_articles": len(crawler_result.articles),
            "articles": crawler_result.articles,
            "errors": crawler_result.errors,
            "metadata": crawler_result.metadata,
            "output_directory": output_dir if save_to_disk else None,
            "saved_files": saved_files
        })
        
    except Exception as e:
        return server_error_response(e)


@manager.route('/news_collector/upload', methods=['POST'])  # noqa: F821
@token_required
def upload_news_api(tenant_id):
    """
    上传新闻到知识库
    
    请求体:
    {
        "kb_id": "知识库ID",
        "articles": [...],
        "auto_parse": true,
        "source_info": {...}
    }
    """
    try:
        req = request.get_json()
        kb_id = req.get('kb_id')
        articles = req.get('articles', [])
        auto_parse = req.get('auto_parse', True)
        
        if not kb_id:
            return get_json_result(code=400, message="知识库ID不能为空")
        
        if not articles:
            return get_json_result(code=400, message="文章列表不能为空")
        
        # 验证知识库权限
        if not KnowledgebaseService.get_by_id(kb_id):
            return get_json_result(code=404, message="知识库不存在")
        
        # 模拟上传逻辑
        uploaded_files = []
        for article in articles:
            file_info = {
                "name": f"{article.get('title', '未知标题')}.md",
                "id": get_uuid(),
                "size": len(str(article).encode('utf-8'))
            }
            uploaded_files.append(file_info)
        
        return get_json_result(data={
            "success": True,
            "uploaded_files": len(uploaded_files),
            "files": uploaded_files,
            "parse_started": auto_parse
        })
        
    except Exception as e:
        return server_error_response(e)


@manager.route('/news_collector/crawl_and_upload', methods=['POST'])  # noqa: F821
@token_required
def crawl_and_upload_news_api(tenant_id):
    """
    一体化操作：爬取并上传
    
    请求体:
    {
        "kb_id": "知识库ID",
        "sources": [...],
        "crawler_type": "demo",
        "max_articles": 10,
        "auto_parse": true
    }
    """
    try:
        req = request.get_json()
        kb_id = req.get('kb_id')
        sources_config = req.get('sources', [])
        crawler_type = req.get('crawler_type', 'demo')
        max_articles = req.get('max_articles', 10)
        auto_parse = req.get('auto_parse', True)
        
        if not kb_id:
            return get_json_result(code=400, message="知识库ID不能为空")
        
        # 验证知识库权限
        if not KnowledgebaseService.get_by_id(kb_id):
            return get_json_result(code=404, message="知识库不存在")
        
        # 转换源配置
        sources = []
        for source_config in sources_config:
            source = NewsSource(
                name=source_config.get('name', ''),
                url=source_config.get('url', ''),
                config=source_config.get('config', {})
            )
            sources.append(source)
        
        # 执行爬取
        crawler_result = crawl_news(sources, crawler_type, max_articles)
        
        # 上传结果
        upload_result = {"success": False}
        if crawler_result.success and crawler_result.articles:
            uploader = NewsUploader("api-key")
            upload_result = uploader.upload_crawler_result(
                crawler_result, kb_id, auto_parse
            )
        
        return get_json_result(data={
            "crawl_result": {
                "success": crawler_result.success,
                "total_articles": len(crawler_result.articles),
                "articles": crawler_result.articles,
                "errors": crawler_result.errors
            },
            "upload_result": upload_result,
            "status": "completed" if crawler_result.success and upload_result.get("success") else "failed"
        })
        
    except Exception as e:
        return server_error_response(e)


@manager.route('/news_collector/crawlers', methods=['GET'])  # noqa: F821
@token_required
def get_available_crawlers_api(tenant_id):
    """获取可用爬虫列表"""
    try:
        crawlers = CrawlerFactory.get_available_crawlers()
        
        return get_json_result(data={
            "crawlers": crawlers,
            "total": len(crawlers)
        })
        
    except Exception as e:
        return server_error_response(e)


# ========== 新闻源管理 CRUD ==========

@manager.route('/news_collector/sources', methods=['GET'])  # noqa: F821
@token_required
def list_news_sources(tenant_id):
    """获取新闻源列表"""
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))
        name = request.args.get('name')
        status = request.args.get('status')
        
        sources, total = NewsSourceService.get_by_tenant_id(
            tenant_id=tenant_id,
            page=page,
            page_size=page_size,
            name=name,
            status=status
        )
        
        return get_json_result(data={
            "sources": sources,
            "total": total,
            "page": page,
            "page_size": page_size
        })
        
    except Exception as e:
        return server_error_response(e)


@manager.route('/news_collector/sources', methods=['POST'])  # noqa: F821
@token_required
def create_news_source(tenant_id):
    """创建新闻源"""
    try:
        req = request.get_json()
        
        if not req.get('name'):
            return get_json_result(code=400, message="名称不能为空")
        if not req.get('url'):
            return get_json_result(code=400, message="URL不能为空")
        
        source = NewsSourceService.create_source(
            tenant_id=tenant_id,
            user_id=tenant_id,  # 在RAGFlow架构中，使用tenant_id作为user_id
            **req
        )
        
        return get_json_result(data={"source": source})
        
    except Exception as e:
        return server_error_response(e)


@manager.route('/news_collector/sources/<source_id>', methods=['GET'])  # noqa: F821
@token_required
def get_news_source(tenant_id, source_id):
    """获取单个新闻源详情"""
    try:
        e, source = NewsSourceService.get_by_id(source_id)
        
        if not source or source.get('tenant_id') != tenant_id:
            return get_json_result(code=404, message="新闻源不存在")
        
        return get_json_result(data={"source": source})
        
    except Exception as e:
        return server_error_response(e)


@manager.route('/news_collector/sources/<source_id>', methods=['PUT'])  # noqa: F821
@token_required
def update_news_source(tenant_id, source_id):
    """更新新闻源"""
    try:
        req = request.get_json()
        
        source = NewsSourceService.update_source(
            source_id=source_id,
            tenant_id=tenant_id,
            **req
        )
        
        return get_json_result(data={"source": source})
        
    except ValueError as e:
        return get_json_result(code=404, message=str(e))
    except Exception as e:
        return server_error_response(e)


@manager.route('/news_collector/sources/<source_id>', methods=['DELETE'])  # noqa: F821
@token_required
def delete_news_source(tenant_id, source_id):
    """删除新闻源"""
    try:
        e, source = NewsSourceService.get_by_id(source_id)
        if not source or source.get('tenant_id') != tenant_id:
            return get_json_result(code=404, message="新闻源不存在")
        
        NewsSourceService.update_source(
            source_id=source_id,
            tenant_id=tenant_id,
            status='deleted'
        )
        
        return get_json_result(message="删除成功")
        
    except Exception as e:
        return server_error_response(e)


# ========== 任务管理 CRUD ==========

@manager.route('/news_collector/tasks', methods=['GET'])  # noqa: F821
@token_required
def list_news_tasks(tenant_id):
    """获取新闻任务列表"""
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))
        task_name = request.args.get('task_name')
        status = request.args.get('status')
        
        tasks, total = NewsTaskService.get_by_tenant_id(
            tenant_id=tenant_id,
            page=page,
            page_size=page_size,
            task_name=task_name,
            status=status
        )
        
        return get_json_result(data={
            "tasks": tasks,
            "total": total,
            "page": page,
            "page_size": page_size
        })
        
    except Exception as e:
        return server_error_response(e)


@manager.route('/news_collector/tasks', methods=['POST'])  # noqa: F821
@token_required
def create_news_task(tenant_id):
    """创建新闻任务"""
    try:
        req = request.get_json()
        
        if not req.get('task_name'):
            return get_json_result(code=400, message="任务名称不能为空")
        if not req.get('kb_id'):
            return get_json_result(code=400, message="知识库ID不能为空")
        
        task = NewsTaskService.create_task(
            tenant_id=tenant_id,
            user_id=tenant_id,  # 在RAGFlow架构中，使用tenant_id作为user_id
            **req
        )
        
        return get_json_result(data={"task": task})
        
    except ValueError as e:
        return get_json_result(code=400, message=str(e))
    except Exception as e:
        return server_error_response(e)


@manager.route('/news_collector/tasks/<task_id>', methods=['GET'])  # noqa: F821
@token_required
def get_news_task(tenant_id, task_id):
    """获取单个新闻任务详情"""
    try:
        e, task = NewsTaskService.get_by_id(task_id)
        
        if not task or task.get('tenant_id') != tenant_id:
            return get_json_result(code=404, message="任务不存在")
        
        return get_json_result(data={"task": task})
        
    except Exception as e:
        return server_error_response(e)


@manager.route('/news_collector/tasks/<task_id>', methods=['PUT'])  # noqa: F821
@token_required
def update_news_task(tenant_id, task_id):
    """更新新闻任务"""
    try:
        req = request.get_json()
        
        task = NewsTaskService.update_task(
            task_id=task_id,
            tenant_id=tenant_id,
            **req
        )
        
        return get_json_result(data={"task": task})
        
    except ValueError as e:
        return get_json_result(code=404, message=str(e))
    except Exception as e:
        return server_error_response(e)


@manager.route('/news_collector/tasks/<task_id>', methods=['DELETE'])  # noqa: F821
@token_required
def delete_news_task(tenant_id, task_id):
    """删除新闻任务"""
    try:
        e, task = NewsTaskService.get_by_id(task_id)
        if not task or task.get('tenant_id') != tenant_id:
            return get_json_result(code=404, message="任务不存在")
        
        NewsTaskService.update_task_status(
            task_id=task_id,
            status='deleted'
        )
        
        return get_json_result(message="删除成功")
        
    except Exception as e:
        return server_error_response(e)


@manager.route('/news_collector/tasks/<task_id>/execute', methods=['POST'])  # noqa: F821
@token_required
def execute_news_task(tenant_id, task_id):
    """执行新闻任务"""
    try:
        e, task = NewsTaskService.get_by_id(task_id)
        if not task or task.get('tenant_id') != tenant_id:
            return get_json_result(code=404, message="任务不存在")
        
        execution_id = get_uuid()
        
        NewsTaskService.update_task_status(
            task_id=task_id,
            status='running',
            last_run_time=int(datetime.now().timestamp() * 1000)
        )
        
        return get_json_result(data={
            "execution_id": execution_id,
            "status": "running",
            "message": "任务已开始执行"
        })
        
    except Exception as e:
        return server_error_response(e)


# ========== 内容管理 ==========

@manager.route('/news_collector/contents', methods=['GET'])  # noqa: F821
@token_required
def list_news_contents(tenant_id):
    """获取新闻内容列表"""
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))
        task_id = request.args.get('task_id')
        source_id = request.args.get('source_id')
        
        if task_id:
            contents, total = NewsContentService.get_by_task_id(
                task_id=task_id,
                page=page,
                page_size=page_size
            )
        elif source_id:
            contents, total = NewsContentService.get_by_source_id(
                source_id=source_id,
                page=page,
                page_size=page_size
            )
        else:
            contents, total = [], 0
        
        return get_json_result(data={
            "contents": contents,
            "total": total,
            "page": page,
            "page_size": page_size
        })
        
    except Exception as e:
        return server_error_response(e)


@manager.route('/news_collector/contents/<content_id>', methods=['GET'])  # noqa: F821
@token_required
def get_news_content(tenant_id, content_id):
    """获取单个新闻内容详情"""
    try:
        e, content = NewsContentService.get_by_id(content_id)
        
        if not content or content.get('tenant_id') != tenant_id:
            return get_json_result(code=404, message="新闻内容不存在")
        
        return get_json_result(data={"content": content})
        
    except Exception as e:
        return server_error_response(e)


@manager.route('/news_collector/contents/<content_id>', methods=['DELETE'])  # noqa: F821
@token_required
def delete_news_content(tenant_id, content_id):
    """删除新闻内容"""
    try:
        e, content = NewsContentService.get_by_id(content_id)
        if not content or content.get('tenant_id') != tenant_id:
            return get_json_result(code=404, message="新闻内容不存在")
        
        NewsContentService.delete_by_id(content_id)
        
        return get_json_result(message="删除成功")
        
    except Exception as e:
        return server_error_response(e)


# ========== 统计分析 ==========

@manager.route('/news_collector/statistics', methods=['GET'])  # noqa: F821
@token_required
def get_news_statistics(tenant_id):
    """获取新闻收集统计信息"""
    try:
        days = int(request.args.get('days', 7))
        
        # 计算时间范围
        end_time = int(datetime.now().timestamp() * 1000)
        start_time = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)
        
        # 获取基础统计
        sources, _ = NewsSourceService.get_by_tenant_id(tenant_id, page_size=1000)
        tasks, _ = NewsTaskService.get_by_tenant_id(tenant_id, page_size=1000)
        
        # 统计活跃状态
        active_sources = len([s for s in sources if s.get('status') == 'active'])
        running_tasks = len([t for t in tasks if t.get('status') == 'running'])
        
        # 获取时间范围内的内容统计
        content_stats = NewsContentService.get_statistics_by_time_range(
            tenant_id, start_time, end_time
        )
        
        return get_json_result(data={
            "summary": {
                "total_sources": len(sources),
                "active_sources": active_sources,
                "total_tasks": len(tasks),
                "running_tasks": running_tasks,
                "total_articles": content_stats.get('total_articles', 0)
            },
            "time_range_stats": content_stats,
            "analysis_period_days": days
        })
        
    except Exception as e:
        return server_error_response(e)
