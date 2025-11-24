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
from api.db.services.document_service import DocumentService
from api.db.services.file_service import FileService
from common import settings
from common.misc_utils import get_uuid
from common.file_utils import get_project_base_directory
from datetime import datetime, timedelta
import os
import tempfile
from playhouse.shortcuts import model_to_dict
import traceback

# --- 新增的导入，用于实现高级抓取功能 ---
import threading
import asyncio
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler  # 直接从库导入
import json  # 新增: 用于写入JSON文件
import hashlib  # 新增: 用于哈希去重
import re  # 新增: 用于清理文件名
import aiofiles  # 确保在文件顶部导入
from flask import Blueprint


# =================================================================================
# LibraryCrawler 类 (最终修正版)
# =================================================================================
class LibraryCrawler:
    """
    一个封装了 crawl4ai 库调用逻辑的内部爬虫类。
    """
    async def recursive_crawl(self, start_url: str, depth: int, max_pages: int, 
                              persistent_hashes: set, selectors: dict = None):
        """
        最终修正：
        1. 无论当前页面内容是否重复，总是解析页面上的链接，以发现新内容。
        2. 只有当页面内容本身是全新的，才将其添加到最终的结果列表。
        """
        newly_crawled_data = [] # 只存储本次抓取到的新数据
        async with AsyncWebCrawler() as crawler:
            visited_urls = set()
            urls_to_visit = [(start_url, 0)]

            IGNORED_EXTENSIONS = (
                ".doc", ".docx", ".wps", ".xls", ".xlsx", ".ppt", ".pptx",
                ".zip", ".rar", ".7z", ".gz", ".tar", ".jpg", ".jpeg",
                ".png", ".gif", ".bmp", ".svg", ".mp3", ".mp4", ".avi",
                ".mov", ".wmv", ".pdf"
            )

            while urls_to_visit and len(newly_crawled_data) < max_pages:
                current_url, current_depth = urls_to_visit.pop(0)
                if current_url in visited_urls:
                    continue

                print(f"\n[LibraryCrawler] 正在抓取: {current_url} (深度: {current_depth})")
                visited_urls.add(current_url)

                try:
                    result = await crawler.arun(url=current_url)
                    if not result.success or not result.html:
                        continue

                    soup = BeautifulSoup(result.html, "html.parser")
                    
                    # ==================== 核心逻辑修正 START ====================
                    
                    # 步骤 1: 解析内容并计算哈希 (无论新旧)
                    content_text = ""
                    title_text = ""
                    
                    if selectors and selectors.get("link_selector"):
                        # (精确模式解析逻辑不变)
                        print("[LibraryCrawler] 模式: 精确抓取 (使用选择器)")
                        content_tag = soup.select_one(selectors.get("content_selector"))
                        content_text = content_tag.get_text(strip=True) if content_tag else result.markdown
                    else:
                        # (自动模式解析逻辑不变)
                        print("[LibraryCrawler] 模式: 自动抓取 (无选择器)")
                        content_text = result.markdown

                    if not content_text or not content_text.strip():
                        print(f"[LibraryCrawler] 警告: 页面内容为空，跳过内容处理，但仍会查找链接。")
                    else:
                        content_hash = hashlib.sha256(content_text.encode("utf-8")).hexdigest()
                        
                        # 步骤 2: 判断内容是否为全新
                        if content_hash in persistent_hashes:
                            # 如果是重复内容，只打印信息，不执行 continue
                            title_tag = soup.title.string if soup.title else current_url
                            print(f"[持久化去重] 跳过已存在内容: {title_tag}")
                        else:
                            # 如果是全新内容，则准备存储
                            # (解析标题、作者等元数据的逻辑移到这里)
                            author_text = None
                            time_text = None
                            if selectors and selectors.get("link_selector"):
                                title_tag = soup.select_one(selectors.get("title_selector", "h1"))
                                title_text = title_tag.get_text(strip=True) if title_tag else soup.title.string
                                author_tag = soup.select_one(selectors.get("author_selector"))
                                author_text = author_tag.get_text(strip=True) if author_tag else None
                                time_tag = soup.select_one(selectors.get("publication_time_selector"))
                                time_text = time_tag.get_text(strip=True) if time_tag else None
                            else:
                                if result.markdown:
                                    for line in result.markdown.split("\n"):
                                        cleaned_line = line.strip("#*-> ").strip()
                                        if cleaned_line:
                                            title_text = cleaned_line
                                            break
                                if not title_text:
                                    title_text = soup.title.string if soup.title else f"Untitled_{get_uuid()}"
                            
                            print(f"[LibraryCrawler] 发现新内容: {title_text}")
                            page_data = {
                                "url": current_url, "title": title_text, "content": content_text,
                                "author": author_text, "publication_time": time_text,
                                "crawl_timestamp": datetime.now().isoformat(),
                                "content_hash": content_hash
                            }
                            newly_crawled_data.append(page_data)
                            persistent_hashes.add(content_hash)

                    # 步骤 3: 发现并添加新链接 (此步骤现在总会执行)
                    if current_depth < depth:
                        link_selector = selectors.get("link_selector", "a[href]") if selectors else "a[href]"
                        for link_tag in soup.select(link_selector):
                            href = link_tag.get("href")
                            if href and not href.startswith(("javascript:", "#", "mailto:")):
                                absolute_link = urljoin(current_url, href)
                                if absolute_link.lower().endswith(IGNORED_EXTENSIONS):
                                    continue
                                if urlparse(absolute_link).netloc == urlparse(start_url).netloc and absolute_link not in visited_urls:
                                    urls_to_visit.append((absolute_link, current_depth + 1))
                    # ===================== 核心逻辑修正 END ======================

                except Exception as e:
                    print(f"[LibraryCrawler] 错误: 处理 {current_url} 时发生错误: {e}")

        return newly_crawled_data


# =================================================================================
# 后台异步任务 (已重构)
# 核心改动：从数据库加载新闻源配置，并根据 remark 字段动态选择抓取模式。
# =================================================================================
def _sanitize_filename(name: str) -> str:
    """清理字符串，使其成为一个合法的文件名的一部分。"""
    # 移除所有不安全的字符，包括 [](){}|#@!$%^&*+=~`，保留字母、数字、中文、下划线、连字符和点
    name = re.sub(r'[\\/*?:"<>|\[\](){}#@!$%^&*+=~`]', "", name)
    # 将空白字符替换为下划线
    name = re.sub(r"\s+", "_", name)
    # 限制长度
    return name[:100]


async def _upload_to_knowledgebase(kb_id: str, tenant_id: str, file_path: str, article_data: dict, parse: bool = False):
    """
    将抓取的新闻内容上传到指定知识库
    
    参数:
        kb_id: 知识库ID
        tenant_id: 租户ID
        file_path: 本地文件路径
        article_data: 文章数据（包含标题、内容等）
    """
    try:
        # 验证知识库存在
        _, kb = KnowledgebaseService.get_by_id(kb_id)
        if not kb:
            print(f"[知识库上传] 错误: 知识库 {kb_id} 不存在")
            return False
        
        # 读取文件内容
        async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
            file_content = await f.read()
        
        # 准备文档数据
        article_title = article_data.get("title", "Untitled")
        article_url = article_data.get("url", "")
        
        # 创建文档记录
        doc_id = get_uuid()
        # 清理文件名，移除不支持的特殊字符
        sanitized_title = _sanitize_filename(article_title)
        doc_name = f"{sanitized_title}.json"
        
        # 上传文件到存储
        # location 应该是相对于 bucket 的路径，与 STORAGE_IMPL.put 的第二个参数一致
        storage_location = f"{doc_id}/{doc_name}"
        settings.STORAGE_IMPL.put(kb_id, storage_location, file_content.encode('utf-8'))
        
        # 创建文档记录到数据库
        doc_data = {
            "id": doc_id,
            "kb_id": kb_id,
            "name": doc_name,
            "location": storage_location,  # 使用相对路径
            "size": len(file_content),
            "type": "json",
            "suffix": "json",  # 添加文件后缀字段
            "parser_id": kb.parser_id,
            "parser_config": kb.parser_config,
            "source_type": "news_crawler",
            "created_by": tenant_id,
            "tenant_id": tenant_id
        }
        
        # DocumentService.insert 会自动增加知识库的文档数量
        doc = DocumentService.insert(doc_data)
        
        # 获取或创建知识库文件夹 
        kb_root_folder = FileService.get_kb_folder(tenant_id)
        if kb_root_folder:
            kb_folder = FileService.new_a_file_from_kb(
                tenant_id,
                kb.name,
                kb_root_folder["id"],
            )
            if kb_folder:
                # 将文档添加到文件系统，以便在前端显示
                FileService.add_file_from_kb(doc.to_dict(), kb_folder["id"], tenant_id)
        
        
        print(f"[知识库上传] 成功上传文档到知识库 {kb_id}: {doc_name}")
        if parse:
            # 解析文档
            from api.db.services.task_service import queue_tasks
            from api.db.services.file2document_service import File2DocumentService
            
            # 获取存储地址信息
            bucket, name = File2DocumentService.get_storage_address(doc_id=doc_id)
            
            # 准备文档信息用于解析
            doc_info = {
                "id": doc_id,
                "kb_id": kb_id,
                "name": doc_name,
                "location": storage_location,
                "type": "json",
                "parser_id": kb.parser_id,
                "parser_config": kb.parser_config,
                "tenant_id": tenant_id,
                "size": len(file_content)
            }
            
            # 将解析任务加入队列
            queue_tasks(doc_info, bucket, name, 0)
            print(f"[知识库上传] 已将文档 {doc_name} 加入解析队列")
        
        return True
        
    except Exception as e:
        print(f"[知识库上传] 上传失败: {e}")
        traceback.print_exc()
        return False


async def _async_crawl_from_post_worker(tenant_id: str, source_ids: list, depth: int, max_pages: int, kb_id: str = None, parse: bool = False):
    """
    (已重构) 异步任务核心：
    1. 从数据库加载所有已存在的哈希值。
    2. 将哈希集合传入爬虫，由爬虫进行"边抓取、边检查"。
    3. 只对爬虫返回的"全新内容"进行存储和数据库更新。
    4. 如果提供了 kb_id，将抓取的内容上传到指定知识库。
    """
    kb_info = f", 目标知识库: {kb_id}" if kb_id else ""
    print(f"[后台任务] 开始处理 {len(source_ids)} 个新闻源... (深度: {depth}, 每源最大页数: {max_pages}{kb_info})")
    
    try:
        content_hashes = NewsContentService.get_all_content_hashes(tenant_id)
        print(f"[后台任务] 成功从数据库加载 {len(content_hashes)} 个已存在的历史内容哈希。")
    except Exception as e:
        print(f"[后台任务] 严重错误: 从数据库加载历史哈希失败: {e}")
        content_hashes = set()

    crawler = LibraryCrawler()
    instant_task_id = get_uuid()

    sources_from_db = []
    for sid in source_ids:
        try:
            _, source_model = NewsSourceService.get_by_id(sid)
            if source_model:
                sources_from_db.append(NewsSourceService.to_dict(source_model))
            else:
                print(f"[后台任务] 警告: 未在数据库中找到 ID 为 {sid} 的新闻源。")
        except Exception as e:
            print(f"[后台任务] 错误: 查询新闻源 {sid} 时出错: {e}")

    total_new_articles_saved = 0
    for i, source in enumerate(sources_from_db):
        source_id = source.get("id")
        source_name = source.get("name")
        start_url = source.get("url")
        
        print(f"\n[后台任务] 正在处理第 {i + 1}/{len(sources_from_db)} 个源: {source_name} ({start_url})")

        if not start_url:
            continue
        
        selectors = source.get("fetch_config") if source.get("remark") == "1" else None

        try:
            new_articles = await crawler.recursive_crawl(
                start_url=start_url, 
                depth=depth, 
                max_pages=max_pages, 
                persistent_hashes=content_hashes,
                selectors=selectors
            )
            
            if not new_articles:
                print(f"[后台任务] 源 '{source_name}' 未发现任何新内容。")
                continue
            
            print(f"[后台任务] 源 '{source_name}' 发现 {len(new_articles)} 篇新内容，开始处理...")

            for page_data in new_articles:
                content_hash = page_data.get("content_hash")

                page_title = _sanitize_filename(page_data.get("title", "untitled"))
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                filename = f"{page_title}_{timestamp}_{content_hash[:16]}.json"

                base_dir = "crawl4ai_data"
                site_domain = _sanitize_filename(urlparse(start_url).netloc)
                output_dir = os.path.join(base_dir, site_domain)
                output_file = os.path.join(output_dir, filename)

                os.makedirs(output_dir, exist_ok=True)
                
                # ==================== 核心修正：afiles -> aiofiles ====================
                async with aiofiles.open(output_file, "w", encoding="utf-8") as f:
                    await f.write(json.dumps(page_data, ensure_ascii=False, indent=2))
                # ===================================================================
                print(f"[文件存储] 成功保存新页面: {output_file}")
                
                try:
                    NewsContentService.create_content(
                        tenant_id=tenant_id, task_id=instant_task_id, source_id=source_id, article_data=page_data
                    )
                    print(f"[数据库同步] 成功将新内容 '{page_title}' 同步到数据库。")
                    total_new_articles_saved += 1
                    
                    # 如果指定了知识库，上传到知识库
                    if kb_id:
                        upload_success = await _upload_to_knowledgebase(
                            kb_id=kb_id,
                            tenant_id=tenant_id,
                            file_path=output_file,
                            article_data=page_data,
                            parse=parse
                        )
                        if upload_success:
                            print(f"[知识库集成] 成功将内容上传到知识库 {kb_id}")
                        else:
                            print(f"[知识库集成] 上传到知识库失败，但本地文件和数据库已保存")
                    
                except Exception as e:
                    print(f"[数据库同步] 警告: 写入数据库失败: {e}")

        except Exception as e:
            print(f"[后台任务] 处理源 {source_name} 时发生严重错误: {e}")
            traceback.print_exc()

    print(f"\n[后台任务] 所有新闻源处理完毕。本次任务共发现并存储了 {total_new_articles_saved} 篇全新内容。")

def _background_crawl_from_post_wrapper(tenant_id: str, source_ids: list, depth: int, max_pages: int, kb_id: str = None, parse: bool = False):
    """同步的包装函数，在线程中启动asyncio事件循环。"""
    asyncio.run(_async_crawl_from_post_worker(tenant_id, source_ids, depth, max_pages, kb_id, parse))


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
                    "title": f"【{source.name}】示例新闻标题 {i + 1}",
                    "content": f"""这是来自 {source.name} 的示例新闻内容 {i + 1}。

本文将深入探讨当前热门的技术趋势和行业动态。随着科技的快速发展，我们正在见证一个前所未有的创新时代。

主要内容包括：
1. 技术发展趋势分析
2. 市场机遇与挑战
3. 未来发展前景

这些变化不仅影响着技术行业，也在改变着我们的日常生活和工作方式。通过深入分析这些趋势，我们可以更好地理解当前的技术环境，并为未来的发展做好准备。

总的来说，技术创新将继续推动社会进步，为各行各业带来新的机遇和挑战。我们需要保持开放的心态，积极拥抱变化，才能在这个快速发展的时代中立于不败之地。""",
                    "url": f"{source.url}/article-{i + 1}",
                    "source": source.name,
                    "author": f"记者{chr(65 + i)}",
                    "publish_time": (datetime.now() - timedelta(hours=i * 2)).strftime("%Y-%m-%d %H:%M:%S"),
                    "crawl_time": datetime.now().isoformat(),
                    "category": source.config.get("category", "综合"),
                    "tags": ["示例", "新闻", source.config.get("category", "综合")],
                    "summary": f"这是第{i + 1}篇示例新闻的摘要内容",
                    "word_count": 150 + i * 20,
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

    # 修改: 移除了旧的 "crawl4ai"
    _crawlers = {"demo": DemoCrawler}

    @classmethod
    def create_crawler(cls, crawler_type: str, config: dict = None):
        if crawler_type not in cls._crawlers:
            raise ValueError(f"不支持的爬虫类型: {crawler_type}")
        return cls._crawlers[crawler_type](config)

    @classmethod
    def get_available_crawlers(cls):
        # 修改: 移除了旧的 "crawl4ai" 的描述
        return [{"type": "demo", "name": "Demo", "description": "演示爬虫 - 生成示例新闻数据"}]


def crawl_news(sources: list, crawler_type: str = "demo", max_articles: int = 10, crawler_config: dict = None) -> CrawlerResult:
    """
    便捷的爬虫调用函数
    修改: 增加 crawler_config 参数，以传递给爬虫实例
    """
    # 注意: 这个函数现在变得有些冗余，因为 crawl_multiple_sources 也能完成任务
    # 但为了保持向后兼容和便捷性，我们保留它
    crawler = CrawlerFactory.create_crawler(crawler_type, crawler_config)
    return crawler.crawl_multiple_sources(sources, max_articles)


class NewsUploader:
    """新闻上传器"""

    def __init__(self, api_key: str):
        self.api_key = api_key

    def upload_crawler_result(self, crawler_result: CrawlerResult, kb_id: str, auto_parse: bool = True):
        """上传爬虫结果到知识库"""
        if not crawler_result.success or not crawler_result.articles:
            return {"success": False, "message": "没有可上传的文章", "uploaded_files": 0}

        try:
            # 这里应集成真实的RAGFlow文件上传API逻辑
            # 当前为模拟逻辑
            uploaded_files = []

            for article in crawler_result.articles:
                content = self._article_to_markdown(article)

                # 模拟文件名清理
                safe_title = "".join(c for c in article.get("title", "untitled") if c.isalnum() or c in (" ", "-", "_")).strip()

                file_info = {"name": f"{safe_title}.md", "id": get_uuid(), "size": len(content.encode("utf-8"))}
                uploaded_files.append(file_info)

            return {"success": True, "uploaded_files": len(uploaded_files), "files": uploaded_files, "parse_started": auto_parse}

        except Exception as e:
            return {"success": False, "message": f"上传失败: {str(e)}", "uploaded_files": 0}

    def _article_to_markdown(self, article: dict) -> str:
        """将文章转换为Markdown格式"""
        content = f"# {article.get('title', '无标题')}\n\n"
        content += f"**来源**: {article.get('source', '未知')}\n"
        content += f"**作者**: {article.get('author', '未知')}\n"
        content += f"**发布时间**: {article.get('publish_time', '未知')}\n"
        content += f"**链接**: {article.get('url', '未知')}\n\n"

        if article.get("summary"):
            content += f"## 摘要\n\n{article['summary']}\n\n"

        content += f"## 正文\n\n{article.get('content', '')}\n\n"

        if article.get("tags"):
            content += f"**标签**: {', '.join(article['tags'])}\n"

        content += "\n---\n\n"
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

    if article.get("summary"):
        content += f"## 摘要\n\n{article['summary']}\n\n"

    content += f"## 正文\n\n{article.get('content', '')}\n\n"

    if article.get("tags"):
        content += f"**标签**: {', '.join(article['tags'])}\n"

    content += "\n---\n\n"
    content += f"*抓取时间: {article.get('crawl_time', '未知')}*\n"
    content += f"*分类: {article.get('category', '未知')}*\n"

    return content


# =================================================================================
# Flask Blueprint 和 API 端点
# =================================================================================

# 定义一个 Blueprint 对象
manager = Blueprint("news_collector_bp", __name__)
# ========== 爬虫相关API ==========


@manager.route("/news_collector/crawl", methods=["POST"])  # noqa: F821
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
                "config": {
                    "crawler_type": "crawl4ai",
                    "category": "科技",
                    "crawler_config": {
                        "base_url": "http://localhost:11235",
                        "api_token": "your-token-if-any",
                        "delay": 1.5
                    }
                }
            }
        ],
        "crawler_type": "demo", // 全局默认爬虫
        "max_articles": 10,
        "save_to_disk": true,
        "output_dir": "/tmp/news_output"
    }
    """
    try:
        req = request.get_json()
        sources_config = req.get("sources", [])
        # 全局爬虫类型和配置
        global_crawler_type = req.get("crawler_type", "demo")
        global_crawler_config = req.get("crawler_config", {})
        max_articles = req.get("max_articles", 10)
        save_to_disk = req.get("save_to_disk", False)
        output_dir = req.get("output_dir")

        sources = []
        for source_config in sources_config:
            # 源可以覆盖全局爬虫类型
            source_crawler_type = source_config.get("config", {}).get("crawler_type", global_crawler_type)
            source_config.setdefault("config", {}).setdefault("crawler_type", source_crawler_type)

            source = NewsSource(name=source_config.get("name", ""), url=source_config.get("url", ""), config=source_config.get("config", {}))
            sources.append(source)

        # 使用工厂创建一个基础爬虫实例，它内部会处理不同类型的源
        # 这里的 global_crawler_type 仅作为没有指定类型的源的默认值
        crawler = CrawlerFactory.create_crawler(global_crawler_type, global_crawler_config)
        crawler_result = crawler.crawl_multiple_sources(sources, max_articles)

        crawl_id = get_uuid()

        saved_files = []
        if save_to_disk and crawler_result.articles:
            if not output_dir:
                output_dir = os.path.join(tempfile.gettempdir(), f"news_crawl_{crawl_id[:8]}")
            os.makedirs(output_dir, exist_ok=True)

            for i, article in enumerate(crawler_result.articles):
                filename = f"{article.get('title', f'article_{i}')}.md"
                safe_filename = "".join(c for c in filename if c.isalnum() or c in (" ", "-", "_", ".", "【", "】")).strip()
                filepath = os.path.join(output_dir, safe_filename)
                content = _article_to_markdown(article)
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)
                saved_files.append({"filename": safe_filename, "filepath": filepath})

        return get_json_result(
            data={
                "crawl_id": crawl_id,
                "success": crawler_result.success,
                "total_articles": len(crawler_result.articles),
                "articles": crawler_result.articles,
                "errors": crawler_result.errors,
                "metadata": crawler_result.metadata,
                "output_directory": output_dir if save_to_disk else None,
                "saved_files": saved_files,
            }
        )

    except Exception as e:
        return server_error_response(e)


@manager.route("/news_collector/upload", methods=["POST"])  # noqa: F821
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
        kb_id = req.get("kb_id")
        articles = req.get("articles", [])
        auto_parse = req.get("auto_parse", True)

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
            file_info = {"name": f"{article.get('title', '未知标题')}.md", "id": get_uuid(), "size": len(str(article).encode("utf-8"))}
            uploaded_files.append(file_info)

        return get_json_result(data={"success": True, "uploaded_files": len(uploaded_files), "files": uploaded_files, "parse_started": auto_parse})

    except Exception as e:
        return server_error_response(e)


@manager.route("/news_collector/crawl_and_upload", methods=["POST"])  # noqa: F821
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
        kb_id = req.get("kb_id")
        sources_config = req.get("sources", [])
        crawler_type = req.get("crawler_type", "demo")
        max_articles = req.get("max_articles", 10)
        auto_parse = req.get("auto_parse", True)

        if not kb_id:
            return get_json_result(code=400, message="知识库ID不能为空")

        # 验证知识库权限
        if not KnowledgebaseService.get_by_id(kb_id):
            return get_json_result(code=404, message="知识库不存在")

        # 转换源配置
        sources = []
        for source_config in sources_config:
            source = NewsSource(name=source_config.get("name", ""), url=source_config.get("url", ""), config=source_config.get("config", {}))
            sources.append(source)

        # 执行爬取
        crawler_result = crawl_news(sources, crawler_type, max_articles)

        # 上传结果
        upload_result = {"success": False}
        if crawler_result.success and crawler_result.articles:
            uploader = NewsUploader("api-key")
            upload_result = uploader.upload_crawler_result(crawler_result, kb_id, auto_parse)

        return get_json_result(
            data={
                "crawl_result": {"success": crawler_result.success, "total_articles": len(crawler_result.articles), "articles": crawler_result.articles, "errors": crawler_result.errors},
                "upload_result": upload_result,
                "status": "completed" if crawler_result.success and upload_result.get("success") else "failed",
            }
        )

    except Exception as e:
        return server_error_response(e)


@manager.route("/news_collector/crawlers", methods=["GET"])  # noqa: F821
@token_required
def get_available_crawlers_api(tenant_id):
    """获取可用爬虫列表"""
    try:
        crawlers = CrawlerFactory.get_available_crawlers()

        return get_json_result(data={"crawlers": crawlers, "total": len(crawlers)})

    except Exception as e:
        return server_error_response(e)


# ========== 新闻源管理 CRUD ==========


@manager.route("/news_collector/sources", methods=["GET"])
@token_required
def list_news_sources(tenant_id):
    """获取新闻源列表"""
    try:
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 20))
        name = request.args.get("name")
        status = request.args.get("status")

        sources, total = NewsSourceService.get_by_tenant_id(tenant_id=tenant_id, page=page, page_size=page_size, name=name, status=status)
        return get_json_result(data={"sources": sources, "total": total, "page": page, "page_size": page_size})

    except Exception as e:
        return server_error_response(e)


@manager.route("/news_collector/sources", methods=["POST"])
@token_required
def create_news_source(tenant_id):
    """创建新闻源"""
    try:
        req = request.get_json()

        if not req.get("name"):
            return get_json_result(code=400, message="名称(name)不能为空")
        if not req.get("url"):
            return get_json_result(code=400, message="URL(url)不能为空")

        source = NewsSourceService.create_source(
            tenant_id=tenant_id,
            user_id=tenant_id,
            **req,
        )
        return get_json_result(data={"source": source})

    except Exception as e:
        return server_error_response(e)


@manager.route("/news_collector/sources/<source_id>", methods=["GET"])
@token_required
def get_news_source(tenant_id, source_id):
    """(已修正) 获取单个新闻源详情"""
    try:
        _, source_model = NewsSourceService.get_by_id(source_id)
        
        # FIX: 先判断对象是否存在，再转换为字典进行后续操作
        if not source_model:
            return get_json_result(code=404, message="新闻源不存在")
        
        source_dict = NewsSourceService.to_dict(source_model)

        if source_dict.get("tenant_id") != tenant_id:
            return get_json_result(code=404, message="新闻源不存在或无权限访问")
        
        return get_json_result(data={"source": source_dict})
    
    except Exception as e:
        return server_error_response(e)


@manager.route("/news_collector/sources/<source_id>", methods=["PUT"])
@token_required
def update_news_source(tenant_id, source_id):
    """更新新闻源"""
    try:
        req = request.get_json()
        source = NewsSourceService.update_source(source_id=source_id, tenant_id=tenant_id, **req)
        return get_json_result(data={"source": source})

    except ValueError as e:
        return get_json_result(code=404, message=str(e))
    except Exception as e:
        return server_error_response(e)


@manager.route("/news_collector/sources/<source_id>", methods=["DELETE"])
@token_required
def delete_news_source(tenant_id, source_id):
    """删除新闻源"""
    try:
        # 逻辑删除，将状态更新为 'deleted'
        NewsSourceService.update_source(source_id=source_id, tenant_id=tenant_id, status="deleted")
        return get_json_result(message="删除成功")

    except ValueError as e:
        return get_json_result(code=404, message=str(e))
    except Exception as e:
        return server_error_response(e)

# ========== 任务管理 CRUD ==========


@manager.route("/news_collector/tasks", methods=["GET"])  # noqa: F821
@token_required
def list_news_tasks(tenant_id):
    """获取新闻任务列表"""
    try:
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 20))
        task_name = request.args.get("task_name")
        status = request.args.get("status")

        tasks, total = NewsTaskService.get_by_tenant_id(tenant_id=tenant_id, page=page, page_size=page_size, task_name=task_name, status=status)

        return get_json_result(data={"tasks": tasks, "total": total, "page": page, "page_size": page_size})

    except Exception as e:
        return server_error_response(e)


@manager.route("/news_collector/tasks", methods=["POST"])  # noqa: F821
@token_required
def create_news_task(tenant_id):
    """创建新闻任务"""
    try:
        req = request.get_json()

        if not req.get("task_name"):
            return get_json_result(code=400, message="任务名称不能为空")
        if not req.get("kb_id"):
            return get_json_result(code=400, message="知识库ID不能为空")

        task = NewsTaskService.create_task(
            tenant_id=tenant_id,
            user_id=tenant_id,  # 在RAGFlow架构中，使用tenant_id作为user_id
            **req,
        )

        return get_json_result(data={"task": task})

    except ValueError as e:
        return get_json_result(code=400, message=str(e))
    except Exception as e:
        return server_error_response(e)


@manager.route("/news_collector/tasks/<task_id>", methods=["GET"])  # noqa: F821
@token_required
def get_news_task(tenant_id, task_id):
    """获取单个新闻任务详情"""
    try:
        e, task = NewsTaskService.get_by_id(task_id)

        if not task or task.get(tenant_id).tenant_id != tenant_id:
            return get_json_result(code=404, message="任务不存在")

        return get_json_result(data={"task": task})

    except Exception as e:
        return server_error_response(e)


@manager.route("/news_collector/tasks/<task_id>", methods=["PUT"])  # noqa: F821
@token_required
def update_news_task(tenant_id, task_id):
    """更新新闻任务"""
    try:
        req = request.get_json()

        task = NewsTaskService.update_task(task_id=task_id, tenant_id=tenant_id, **req)

        return get_json_result(data={"task": task})

    except ValueError as e:
        return get_json_result(code=404, message=str(e))
    except Exception as e:
        return server_error_response(e)


@manager.route("/news_collector/tasks/<task_id>", methods=["DELETE"])  # noqa: F821
@token_required
def delete_news_task(tenant_id, task_id):
    """删除新闻任务"""
    try:
        e, task = NewsTaskService.get_by_id(task_id)
        if not task or task.get(tenant_id).tenant_id != tenant_id:
            return get_json_result(code=404, message="任务不存在")

        NewsTaskService.update_task_status(task_id=task_id, status="deleted")

        return get_json_result(message="删除成功")

    except Exception as e:
        return server_error_response(e)


@manager.route("/news_collector/tasks/<task_id>/execute", methods=["POST"])  # noqa: F821
@token_required
def execute_news_task(tenant_id, task_id):
    """执行新闻任务"""
    try:
        e, task = NewsTaskService.get_by_id(task_id)
        if not task or task.get(tenant_id).tenant_id != tenant_id:
            return get_json_result(code=404, message="任务不存在")

        execution_id = get_uuid()

        NewsTaskService.update_task_status(task_id=task_id, status="running", last_run_time=int(datetime.now().timestamp() * 1000))

        return get_json_result(data={"execution_id": execution_id, "status": "running", "message": "任务已开始执行"})

    except Exception as e:
        return server_error_response(e)


# ========== 内容管理 ==========


@manager.route("/news_collector/contents", methods=["GET"])  # noqa: F821
@token_required
def list_news_contents(tenant_id):
    """获取新闻内容列表"""
    try:
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 20))
        task_id = request.args.get("task_id")
        source_id = request.args.get("source_id")

        if task_id:
            contents, total = NewsContentService.get_by_task_id(task_id=task_id, page=page, page_size=page_size)
        elif source_id:
            contents, total = NewsContentService.get_by_source_id(source_id=source_id, page=page, page_size=page_size)
        else:
            contents, total = [], 0

        return get_json_result(data={"contents": contents, "total": total, "page": page, "page_size": page_size})

    except Exception as e:
        return server_error_response(e)


@manager.route("/news_collector/contents/<content_id>", methods=["GET"])  # noqa: F821
@token_required
def get_news_content(tenant_id, content_id):
    """获取单个新闻内容详情"""
    try:
        e, content = NewsContentService.get_by_id(content_id)

        if not content or content.get(tenant_id).tenant_id != tenant_id:
            return get_json_result(code=404, message="新闻内容不存在")

        return get_json_result(data={"content": content})

    except Exception as e:
        return server_error_response(e)


@manager.route("/news_collector/contents/<content_id>", methods=["DELETE"])  # noqa: F821
@token_required
def delete_news_content(tenant_id, content_id):
    """删除新闻内容"""
    try:
        e, content = NewsContentService.get_by_id(content_id)
        if not content or content.get(tenant_id).tenant_id != tenant_id:
            return get_json_result(code=404, message="新闻内容不存在")

        NewsContentService.delete_by_id(content_id)

        return get_json_result(message="删除成功")

    except Exception as e:
        return server_error_response(e)


# ========== 统计分析 ==========


@manager.route("/news_collector/statistics", methods=["GET"])  # noqa: F821
@token_required
def get_news_statistics(tenant_id):
    """获取新闻收集统计信息"""
    try:
        days = int(request.args.get("days", 7))

        # 计算时间范围
        end_time = int(datetime.now().timestamp() * 1000)
        start_time = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)

        # 获取基础统计
        sources, _ = NewsSourceService.get_by_tenant_id(tenant_id, page_size=1000)
        tasks, _ = NewsTaskService.get_by_tenant_id(tenant_id, page_size=1000)

        # 统计活跃状态
        active_sources = len([s for s in sources if s.get("status") == "active"])
        running_tasks = len([t for t in tasks if t.get("status") == "running"])

        # 获取时间范围内的内容统计
        content_stats = NewsContentService.get_statistics_by_time_range(tenant_id, start_time, end_time)

        return get_json_result(
            data={
                "summary": {
                    "total_sources": len(sources),
                    "active_sources": active_sources,
                    "total_tasks": len(tasks),
                    "running_tasks": running_tasks,
                    "total_articles": content_stats.get("total_articles", 0),
                },
                "time_range_stats": content_stats,
                "analysis_period_days": days,
            }
        )

    except Exception as e:
        return server_error_response(e)


@manager.route("/news_collector/crawl_from_post", methods=["POST"])
@token_required
def crawl_from_post_api(tenant_id):
    """
    (已重构) 接收一个包含新闻源ID列表和控制参数的对象，
    并为它们启动一个即时的、数据库驱动的后台抓取任务。
    """
    req_data = request.get_json()

    source_ids = req_data.get("source_ids")
    depth = int(req_data.get("depth", 2))
    max_pages_per_source = int(req_data.get("max_pages_per_source", 50))

    if not isinstance(source_ids, list) or not source_ids:
        return get_json_result(code=400, message="请求体必须包含一个名为 'source_ids' 的非空数组。")

    try:
        # 将 tenant_id 传递给后台线程
        thread = threading.Thread(target=_background_crawl_from_post_wrapper, args=(tenant_id, source_ids, depth, max_pages_per_source))
        thread.start()

        return get_json_result(data={"message": f"已成功启动后台即时抓取任务，将从数据库加载并处理 {len(source_ids)} 个新闻源。"})

    except Exception as e:
        traceback.print_exc()
        return server_error_response(e)
    
# =================================================================================
# 新增的哈希管理 API
# =================================================================================

@manager.route("/news_collector/contents/hashes", methods=["GET"])
@token_required
def list_content_hashes(tenant_id):
    """
    获取已存储内容的哈希列表（带分页）。
    用于查看和调试持久化去重数据库。
    """
    try:
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 20))

        records, total = NewsContentService.get_hashes_paginated(
            tenant_id=tenant_id, page=page, page_size=page_size
        )

        return get_json_result(data={"records": records, "total": total, "page": page, "page_size": page_size})

    except Exception as e:
        return server_error_response(e)


@manager.route("/news_collector/contents", methods=["DELETE"])
@token_required
def delete_all_contents(tenant_id):
    """
    清除所有已存储的内容记录和哈希值。
    这是一个危险操作，用于完全重置抓取历史。
    """
    try:
        deleted_count = NewsContentService.delete_by_tenant_id(tenant_id)
        # 清空本地文件是一个更复杂的操作，此处我们只清除数据库记录
        # 如果需要，可以后续添加清理本地文件的逻辑
        return get_json_result(message=f"成功删除 {deleted_count} 条内容记录。抓取历史已重置。")

    except Exception as e:
        return server_error_response(e)