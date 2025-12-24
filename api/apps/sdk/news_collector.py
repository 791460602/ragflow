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
新闻收集器完整API (精简版)

功能：
1. 新闻源 CRUD 管理
2. 即时抓取（精确模式/自动模式）
3. 主题搜索抓取（关键词相关性爬取）- 基于source_ids
4. 内容哈希管理（持久化去重）
"""

from quart import request, Blueprint
from api.utils.api_utils import get_json_result, server_error_response, token_required
from api.db.services.news_service import NewsSourceService, NewsContentService
from api.db.services.knowledgebase_service import KnowledgebaseService
from api.db.services.document_service import DocumentService
from api.db.services.file_service import FileService
from common.misc_utils import get_uuid
from common import settings
from datetime import datetime
import os
import traceback
import threading
import asyncio
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, BrowserConfig
from crawl4ai.content_scraping_strategy import LXMLWebScrapingStrategy
import json
import hashlib
import re
import aiofiles
from typing import List

# 从 crawl4ai.deep_crawling 导入 BFS 策略（替换 BestFirst）
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy
from crawl4ai.deep_crawling.filters import FilterChain, ContentTypeFilter



# =================================================================================
# LibraryCrawler 类 - 基础爬虫（精确模式/自动模式）
# =================================================================================
class LibraryCrawler:
    """封装 crawl4ai 库调用逻辑的内部爬虫类"""

    async def recursive_crawl(self, start_url: str, depth: int, max_pages: int, persistent_hashes: set, selectors: dict = None):
        """
        递归爬取网页内容
        - 无论当前页面内容是否重复，总是解析页面上的链接以发现新内容
        - 只有当页面内容本身是全新的，才将其添加到最终结果列表
        """
        newly_crawled_data = []
        async with AsyncWebCrawler() as crawler:
            visited_urls = set()
            urls_to_visit = [(start_url, 0)]

            IGNORED_EXTENSIONS = (
                ".doc",
                ".docx",
                ".wps",
                ".xls",
                ".xlsx",
                ".ppt",
                ".pptx",
                ".zip",
                ".rar",
                ".7z",
                ".gz",
                ".tar",
                ".jpg",
                ".jpeg",
                ".png",
                ".gif",
                ".bmp",
                ".svg",
                ".mp3",
                ".mp4",
                ".avi",
                ".mov",
                ".wmv",
                ".pdf",
            )

            while urls_to_visit and len(newly_crawled_data) < max_pages:
                current_url, current_depth = urls_to_visit.pop(0)
                if current_url in visited_urls:
                    continue

                print(f"\n[LibraryCrawler] 正在抓取: {current_url} (深度: {current_depth})")
                visited_urls.add(current_url)

                try:
                    result = await crawler.arun(url=current_url, bypass_cache=True, cache_mode="disabled")
                    if not result.success or not result.html:
                        continue

                    soup = BeautifulSoup(result.html, "html.parser")

                    # 兼容性处理 markdown 字段
                    md_raw = getattr(result, "markdown", None)
                    if md_raw is None:
                        md_text = ""
                    elif isinstance(md_raw, str):
                        md_text = md_raw
                    elif isinstance(md_raw, dict):
                        md_text = md_raw.get("str") or md_raw.get("raw_markdown") or md_raw.get("markdown_with_citations") or md_raw.get("markdown") or json.dumps(md_raw, ensure_ascii=False)
                    else:
                        md_text = str(md_raw)

                    # 解析内容
                    content_text = ""
                    title_text = ""

                    if selectors and selectors.get("link_selector"):
                        print("[LibraryCrawler] 模式: 精确抓取 (使用选择器)")
                        content_tag = soup.select_one(selectors.get("content_selector"))
                        content_text = content_tag.get_text(strip=True) if content_tag else md_text
                    else:
                        print("[LibraryCrawler] 模式: 自动抓取 (无选择器)")
                        content_text = md_text

                    if not content_text or not content_text.strip():
                        print("[LibraryCrawler] 警告: 页面内容为空，跳过内容处理，但仍会查找链接。")
                    else:
                        content_hash = hashlib.sha256(content_text.encode("utf-8")).hexdigest()

                        if content_hash in persistent_hashes:
                            title_tag = soup.title.string if soup.title else current_url
                            print(f"[持久化去重] 跳过已存在内容: {title_tag}")
                        else:
                            # 解析元数据
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
                                if md_text:
                                    for line in md_text.split("\n"):
                                        cleaned_line = line.strip("#*-> ").strip()
                                        if cleaned_line:
                                            title_text = cleaned_line
                                            break
                                if not title_text:
                                    title_text = soup.title.string if soup.title else f"Untitled_{get_uuid()}"

                            print(f"[LibraryCrawler] 发现新内容: {title_text}")
                            page_data = {
                                "url": current_url,
                                "title": title_text,
                                "content": content_text,
                                "author": author_text,
                                "publication_time": time_text,
                                "crawl_timestamp": datetime.now().isoformat(),
                                "content_hash": content_hash,
                            }
                            newly_crawled_data.append(page_data)
                            persistent_hashes.add(content_hash)

                    # 发现并添加新链接
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

                except Exception as e:
                    print(f"[LibraryCrawler] 错误: 处理 {current_url} 时发生错误: {e}")

        return newly_crawled_data


class ChineseContentScorer:
    """基于内容的中文关键词相关性评分器"""

    def __init__(self, keywords: List[str], k1: float = 1.5, b: float = 0.75):
        self.keywords = keywords
        self.k1 = k1
        self.b = b
        self.keyword_patterns = self._build_keyword_patterns(keywords)

    def _build_keyword_patterns(self, keywords: List[str]) -> List[str]:
        """构建关键词匹配模式"""
        patterns = []
        for kw in keywords:
            patterns.append(kw)
            if len(kw) > 2:
                for i in range(len(kw) - 1):
                    patterns.append(kw[i : i + 2])
                    if i + 3 <= len(kw):
                        patterns.append(kw[i : i + 3])
        return list(set(patterns))

    def score(self, content: str, title: str = "") -> float:
        """计算内容与关键词的相关性分数"""
        if not content:
            return 0.0

        full_text = (title + " ") * 3 + content
        full_text_lower = full_text.lower()
        doc_length = len(full_text)
        avg_doc_length = 500

        total_score = 0.0
        matched_keywords = 0

        for keyword in self.keywords:
            keyword_lower = keyword.lower()

            if keyword_lower in full_text_lower:
                freq = full_text_lower.count(keyword_lower)
                numerator = freq * (self.k1 + 1)
                denominator = freq + self.k1 * (1 - self.b + self.b * doc_length / avg_doc_length)
                score = numerator / denominator
                total_score += score * 2
                matched_keywords += 1

        if matched_keywords == 0:
            return 0.0

        coverage = matched_keywords / len(self.keywords)
        normalized_score = min(1.0, total_score / (len(self.keywords) * 3))
        final_score = coverage * 0.4 + normalized_score * 0.6

        return round(final_score, 4)

    def get_matched_keywords(self, content: str) -> List[str]:
        """返回匹配到的关键词列表"""
        matched = []
        content_lower = content.lower()
        for keyword in self.keywords:
            if keyword.lower() in content_lower:
                matched.append(keyword)
        return matched


# =================================================================================
# TopicCrawler 类 - 修复版
# =================================================================================
class TopicCrawler:
    """基于内容评分的主题搜索爬虫 - 修复版

    修复内容：
    1. 每个源使用独立的浏览器配置，避免跨源的上下文冲突
    2. 改进的资源管理，确保爬虫正确关闭
    3. 更强的异常处理，忽略已知的crawl4ai库问题
    4. 源之间添加延迟，确保资源完全释放
    """

    def __init__(self):
        self.content_scorer = None

    async def search_by_topic_from_sources(
        self, sources: list, keywords: list, max_depth: int = 2, max_pages_per_source: int = 30, max_crawl_pages_per_source: int = 100, score_threshold: float = 0.3, persistent_hashes: set = None
    ):
        """从多个新闻源根据主题关键词进行智能搜索爬取"""
        if persistent_hashes is None:
            persistent_hashes = set()

        # 初始化内容评分器
        self.content_scorer = ChineseContentScorer(keywords=keywords)

        all_crawled_data = []

        print("\n[TopicCrawler] 开始多源主题搜索爬取（内容评分模式）")
        print(f"[TopicCrawler] 新闻源数量: {len(sources)}")
        print(f"[TopicCrawler] 关键词: {keywords}")
        print(f"[TopicCrawler] 每源最大收集: {max_pages_per_source}, 每源最大爬取: {max_crawl_pages_per_source}")
        print(f"[TopicCrawler] 内容评分阈值: {score_threshold}")

        # 【修复】不再在这里创建共享的 browser_config

        for i, source in enumerate(sources):
            source_id = source.get("id")
            source_name = source.get("name")
            start_url = source.get("url")

            if not start_url:
                continue

            print(f"\n[TopicCrawler] === 处理源 {i + 1}/{len(sources)}: {source_name} ===")

            try:
                # 【关键修复】每个源创建独立的浏览器配置实例
                browser_config = BrowserConfig(
                    headless=True,
                    verbose=False,
                    extra_args=[
                        "--disable-gpu",
                        "--disable-dev-shm-usage",
                        "--no-sandbox",
                        "--disable-extensions",
                    ],
                )

                source_articles = await self._crawl_single_source(
                    start_url=start_url,
                    source_id=source_id,
                    keywords=keywords,
                    max_depth=max_depth,
                    max_pages=max_pages_per_source,
                    max_crawl_pages=max_crawl_pages_per_source,
                    score_threshold=score_threshold,
                    persistent_hashes=persistent_hashes,
                    browser_config=browser_config,
                )
                all_crawled_data.extend(source_articles)
                print(f"[TopicCrawler] 源 '{source_name}' 发现 {len(source_articles)} 篇相关内容")

            except Exception as e:
                print(f"[TopicCrawler] 处理源 '{source_name}' 时发生错误: {e}")
                traceback.print_exc()

            # 【关键修复】源之间添加延迟，确保浏览器资源完全释放
            if i < len(sources) - 1:
                print("[TopicCrawler] 等待资源释放...")
                await asyncio.sleep(2)

        print(f"\n[TopicCrawler] 完成，共发现 {len(all_crawled_data)} 篇相关内容")
        return all_crawled_data

    async def _crawl_single_source(
        self, start_url: str, source_id: str, keywords: list, max_depth: int, max_pages: int, max_crawl_pages: int, score_threshold: float, persistent_hashes: set, browser_config: BrowserConfig
    ):
        """爬取单个新闻源 - 使用内容评分（修复版）

        改进点：
        1. 使用try-finally确保爬虫正确关闭
        2. 在收集到足够内容后主动退出迭代
        3. 捕获并处理已知的crawl4ai库错误
        """
        newly_crawled_data = []
        visited_urls = set()
        pages_processed = 0
        should_stop = False

        print(f"[TopicCrawler] 目标: {max_pages} 篇相关内容, 最大爬取: {max_crawl_pages} 页")

        # 使用 BFS 策略
        config = CrawlerRunConfig(
            deep_crawl_strategy=BFSDeepCrawlStrategy(
                max_depth=max_depth, include_external=False, max_pages=max_crawl_pages, filter_chain=FilterChain([ContentTypeFilter(allowed_types=["text/html"])])
            ),
            scraping_strategy=LXMLWebScrapingStrategy(),
            stream=True,
            verbose=True,
        )

        crawler = None
        try:
            # 【修复】手动管理爬虫生命周期
            crawler = AsyncWebCrawler(config=browser_config)
            await crawler.__aenter__()

            try:
                async for result in await crawler.arun(start_url, config=config):
                    # 检查是否应该停止
                    if should_stop or len(newly_crawled_data) >= max_pages:
                        if not should_stop:
                            print(f"[TopicCrawler] ✓ 已收集到 {max_pages} 篇相关内容，停止爬取")
                            should_stop = True
                        break  # 【关键】直接退出循环

                    pages_processed += 1

                    if not result.success:
                        continue

                    url = result.url
                    if url in visited_urls:
                        continue
                    visited_urls.add(url)

                    # 提取内容
                    content_text = self._extract_content(result)
                    title = getattr(result, "title", "") or ""
                    if not str(title).strip():
                        try:
                            if result.metadata and isinstance(result.metadata, dict):
                                title = result.metadata.get("title") or title
                        except Exception:
                            pass
                    if not str(title).strip():
                        try:
                            html = getattr(result, "html", None)
                            if html:
                                soup = BeautifulSoup(html, "html.parser")
                                title = soup.title.string if soup.title and soup.title.string else title
                        except Exception:
                            pass
                    title = (title or "").strip()

                    if not content_text or len(content_text.strip()) < 100:
                        continue

                    # 使用内容评分
                    content_score = self.content_scorer.score(content_text, title)
                    matched_keywords = self.content_scorer.get_matched_keywords(content_text + " " + title)
                    depth = result.metadata.get("depth", 0) if result.metadata else 0

                    print(f"[TopicCrawler] 深度: {depth} | 评分: {content_score:.2f} | 匹配: {matched_keywords[:3]} | {url[:60]}...")

                    if content_score < score_threshold:
                        continue

                    # 去重
                    content_hash = hashlib.sha256(content_text.encode("utf-8")).hexdigest()
                    if content_hash in persistent_hashes:
                        print(f"[TopicCrawler] 跳过重复内容: {title[:30]}...")
                        continue
                    persistent_hashes.add(content_hash)

                    # 收集内容
                    article_data = {
                        "url": url,
                        "source_id": source_id,
                        "score": content_score,
                        "depth": depth,
                        "content": content_text,
                        "content_hash": content_hash,
                        "title": title,
                        "matched_keywords": matched_keywords,
                        "crawl_timestamp": datetime.now().isoformat(),
                    }
                    newly_crawled_data.append(article_data)
                    print(f"[TopicCrawler] ✓ 收集: {title[:40]}... (评分: {content_score:.2f})")

            except GeneratorExit:
                # 【修复】正常处理生成器退出
                print("[TopicCrawler] 爬取迭代器已关闭")
            except StopAsyncIteration:
                # 正常结束
                pass
            except Exception as iter_error:
                # 【修复】忽略已知的crawl4ai库错误
                error_str = str(iter_error)
                if "was created in a different Context" in error_str:
                    print("[TopicCrawler] 忽略ContextVar错误（crawl4ai已知问题）")
                elif "Target page, context or browser has been closed" in error_str:
                    print("[TopicCrawler] 浏览器已关闭，停止当前源爬取")
                elif "net::ERR_ABORTED" in error_str:
                    print("[TopicCrawler] 页面请求被中断")
                else:
                    print(f"[TopicCrawler] 迭代错误: {iter_error}")

        except Exception as e:
            print(f"[TopicCrawler] 源爬取错误: {e}")
            traceback.print_exc()

        finally:
            # 【关键修复】确保爬虫资源被正确释放
            if crawler:
                try:
                    await crawler.__aexit__(None, None, None)
                except Exception:
                    # 忽略关闭时的错误（这些通常是无害的）
                    pass

            # 额外等待，确保浏览器进程完全退出
            await asyncio.sleep(0.5)

        print(f"[TopicCrawler] 单源完成: 处理 {pages_processed} 页, 收集 {len(newly_crawled_data)} 篇")
        return newly_crawled_data

    def _extract_content(self, result) -> str:
        """从爬取结果中提取文本内容"""
        md_raw = getattr(result, "markdown", None)
        if md_raw is None:
            return ""
        elif isinstance(md_raw, str):
            return md_raw
        elif isinstance(md_raw, dict):
            return md_raw.get("str") or md_raw.get("raw_markdown") or md_raw.get("markdown_with_citations") or md_raw.get("markdown") or ""
        return str(md_raw)


# =================================================================================
# 工具函数
# =================================================================================
def _sanitize_filename(name: str) -> str:
    """清理字符串，使其成为一个合法的文件名的一部分"""
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    name = re.sub(r"\s+", "_", name)
    return name[:50]


async def _upload_to_knowledgebase(kb_id: str, tenant_id: str, file_path: str, article_data: dict, parse: bool = False, document_id: str = None) -> bool:
    """上传内容到知识库 (修复版)"""
    try:
        _, kb = KnowledgebaseService.get_by_id(kb_id)
        if not kb:
            print(f"[知识库上传] 知识库 {kb_id} 不存在")
            return False

        doc_name = os.path.basename(file_path)
        doc_id = document_id if document_id else get_uuid()

        # 读取文件内容(文本模式)
        async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
            file_content = await f.read()

        # 准备文档数据
        article_title = (article_data.get("title") or "").strip()
        if not article_title:
            try:
                u = (article_data.get("url") or "").strip()
                if u:
                    parsed = urlparse(u)
                    last_seg = (parsed.path or "").rstrip("/").split("/")[-1]
                    article_title = last_seg or parsed.netloc
            except Exception:
                article_title = ""
        if not article_title:
            article_title = "Untitled"

        sanitized_title = _sanitize_filename(article_title)
        if not sanitized_title:
            sanitized_title = _sanitize_filename(f"Untitled_{datetime.now().strftime('%Y%m%d%H%M%S')}")
        doc_name = f"{sanitized_title}.json"

        # location 应该是相对于 bucket 的路径
        doc_id = document_id if document_id else get_uuid()
        storage_location = f"{doc_id}/{doc_name}"

        # 使用 settings.STORAGE_IMPL 进行存储
        settings.STORAGE_IMPL.put(kb_id, storage_location, file_content.encode("utf-8"))

        # 如果调用方提供了 document_id,则尝试更新该 Document;
        # 否则新建 Document(保持向后兼容)
        if document_id:
            try:
                # 更新已有 Document
                DocumentService.update_by_id(
                    document_id,
                    {
                        "location": storage_location,
                        "size": len(file_content),
                        "name": doc_name,
                        "suffix": "json",
                        "type": "json",
                        "source_type": "local",
                    },
                )
                e, doc = DocumentService.get_by_id(document_id)
                if not e:
                    doc = None
                else:
                    print(f"[知识库上传] 更新已存在的文档: {document_id}")
            except Exception as update_err:
                print(f"[知识库上传] 更新文档失败,尝试创建新文档: {update_err}")
                doc = None
        else:
            doc = None

        # 如果没有成功更新现有文档,则创建新文档
        if doc is None:
            doc_data = {
                "id": doc_id,
                "kb_id": kb_id,
                "name": doc_name,
                "location": storage_location,
                "size": len(file_content),
                "type": "json",
                "suffix": "json",
                "parser_id": kb.parser_id,
                "parser_config": kb.parser_config,
                "source_type": "local",
                "created_by": tenant_id,
                "tenant_id": tenant_id,
            }
            doc = DocumentService.insert(doc_data)

        # 获取知识库文件夹（只需要 tenant_id 一个参数）
        kb_root_folder = FileService.get_kb_folder(tenant_id)
        if kb_root_folder:
            # 为知识库创建子文件夹
            kb_folder = FileService.new_a_file_from_kb(
                tenant_id,
                kb.name,
                kb_root_folder["id"],
            )
            if kb_folder:
                FileService.add_file_from_kb(doc.to_dict(), kb_folder["id"], tenant_id)

        print(f"[知识库上传] 成功上传文档到知识库 {kb_id}: {doc_name}")

        if parse:
            from api.db.services.task_service import queue_tasks
            from api.db.services.file2document_service import File2DocumentService

            bucket, name = File2DocumentService.get_storage_address(doc_id=doc_id)
            doc_info = {
                "id": doc_id,
                "kb_id": kb_id,
                "name": doc_name,
                "location": storage_location,
                "type": "json",
                "parser_id": kb.parser_id,
                "parser_config": kb.parser_config,
                "tenant_id": tenant_id,
                "size": len(file_content),
            }
            queue_tasks(doc_info, bucket, name, 0)
            print(f"[知识库上传] 已将文档 {doc_name} 加入解析队列")

        return True

    except Exception as e:
        print(f"[知识库上传] 上传失败: {e}")
        traceback.print_exc()
        return False


# =================================================================================
# 后台异步任务
# =================================================================================
async def _async_crawl_from_post_worker(tenant_id: str, source_ids: list, depth: int, max_pages: int, kb_id: str = None, parse: bool = False):
    """基于新闻源的异步抓取任务"""
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
            new_articles = await crawler.recursive_crawl(start_url=start_url, depth=depth, max_pages=max_pages, persistent_hashes=content_hashes, selectors=selectors)

            if not new_articles:
                print(f"[后台任务] 源 '{source_name}' 未发现任何新内容。")
                continue

            print(f"[后台任务] 源 '{source_name}' 发现 {len(new_articles)} 篇新内容，开始处理...")

            for page_data in new_articles:
                content_hash = page_data.get("content_hash")
                page_title = _sanitize_filename((page_data.get("title") or "untitled"))
                timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                filename = f"{page_title}_{timestamp}_{content_hash[:16]}.json"

                base_dir = "crawl4ai_data"
                site_domain = _sanitize_filename(urlparse(start_url).netloc)
                output_dir = os.path.join(base_dir, site_domain)
                output_file = os.path.join(output_dir, filename)

                os.makedirs(output_dir, exist_ok=True)

                async with aiofiles.open(output_file, "w", encoding="utf-8") as f:
                    await f.write(json.dumps(page_data, ensure_ascii=False, indent=2))
                print(f"[文件存储] 成功保存新页面: {output_file}")

                try:
                    news_content = NewsContentService.create_content(tenant_id=tenant_id, task_id=instant_task_id, source_id=source_id, article_data=page_data, kb_id=kb_id)
                    print(f"[数据库同步] 成功将新内容 '{page_title}' 同步到数据库。")
                    total_new_articles_saved += 1

                    if kb_id:
                        document_id = None
                        try:
                            if isinstance(news_content, dict):
                                document_id = news_content.get("document_id")
                        except Exception:
                            document_id = None

                        upload_success = await _upload_to_knowledgebase(
                            kb_id=kb_id,
                            tenant_id=tenant_id,
                            file_path=output_file,
                            article_data=page_data,
                            parse=parse,
                            document_id=document_id,
                        )
                        if upload_success:
                            print(f"[知识库集成] 成功将内容上传到知识库 {kb_id}")
                        else:
                            print("[知识库集成] 上传到知识库失败，但本地文件和数据库已保存")

                except Exception as e:
                    print(f"[数据库同步] 警告: 写入数据库失败: {e}")

        except Exception as e:
            print(f"[后台任务] 处理源 {source_name} 时发生严重错误: {e}")
            traceback.print_exc()

    print(f"\n[后台任务] 所有新闻源处理完毕。本次任务共发现并存储了 {total_new_articles_saved} 篇全新内容。")


async def _async_topic_search_worker(
    tenant_id: str, source_ids: list, keywords: list, max_depth: int, max_pages_per_source: int, max_crawl_pages_per_source: int, score_threshold: float, kb_id: str = None, parse: bool = False
):
    """主题搜索的异步任务 - 改进版，支持多源"""
    kb_info = f", 目标知识库: {kb_id}" if kb_id else ""
    print(f"[主题搜索任务] 开始搜索... (关键词: {keywords}, 新闻源数: {len(source_ids)}, 深度: {max_depth}, 每源最大收集: {max_pages_per_source}, 每源最大爬取: {max_crawl_pages_per_source}{kb_info})")

    try:
        content_hashes = NewsContentService.get_all_content_hashes(tenant_id)
        print(f"[主题搜索任务] 成功从数据库加载 {len(content_hashes)} 个已存在的历史内容哈希。")
    except Exception as e:
        print(f"[主题搜索任务] 警告: 从数据库加载历史哈希失败: {e}")
        content_hashes = set()

    # 从数据库加载新闻源
    sources_from_db = []
    for sid in source_ids:
        try:
            _, source_model = NewsSourceService.get_by_id(sid)
            if source_model:
                sources_from_db.append(NewsSourceService.to_dict(source_model))
            else:
                print(f"[主题搜索任务] 警告: 未在数据库中找到 ID 为 {sid} 的新闻源。")
        except Exception as e:
            print(f"[主题搜索任务] 错误: 查询新闻源 {sid} 时出错: {e}")

    if not sources_from_db:
        print("[主题搜索任务] 错误: 没有有效的新闻源，任务终止。")
        return

    topic_crawler = TopicCrawler()
    instant_task_id = get_uuid()

    try:
        new_articles = await topic_crawler.search_by_topic_from_sources(
            sources=sources_from_db,
            keywords=keywords,
            max_depth=max_depth,
            max_pages_per_source=max_pages_per_source,
            max_crawl_pages_per_source=max_crawl_pages_per_source,
            score_threshold=score_threshold,
            persistent_hashes=content_hashes,
        )

        if not new_articles:
            print("[主题搜索任务] 未发现任何相关新内容。")
            return

        print(f"[主题搜索任务] 发现 {len(new_articles)} 篇相关内容，开始处理...")

        total_saved = 0
        for page_data in new_articles:
            content_hash = page_data.get("content_hash")
            source_id = page_data.get("source_id")
            page_title = _sanitize_filename((page_data.get("title") or "untitled"))
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            filename = f"topic_{page_title}_{timestamp}_{content_hash[:16]}.json"

            base_dir = "crawl4ai_data"
            topic_dir = _sanitize_filename("_".join(keywords[:3]))
            output_dir = os.path.join(base_dir, "topic_search", topic_dir)
            output_file = os.path.join(output_dir, filename)

            os.makedirs(output_dir, exist_ok=True)

            async with aiofiles.open(output_file, "w", encoding="utf-8") as f:
                await f.write(json.dumps(page_data, ensure_ascii=False, indent=2))
            print(f"[文件存储] 成功保存: {output_file}")

            try:
                news_content = NewsContentService.create_content(tenant_id=tenant_id, task_id=instant_task_id, source_id=source_id, article_data=page_data, kb_id=kb_id)
                print(f"[数据库同步] 成功将内容 '{page_title}' 同步到数据库。")
                total_saved += 1

                if kb_id:
                    document_id = None
                    try:
                        if isinstance(news_content, dict):
                            document_id = news_content.get("document_id")
                    except Exception:
                        document_id = None

                    await _upload_to_knowledgebase(
                        kb_id=kb_id,
                        tenant_id=tenant_id,
                        file_path=output_file,
                        article_data=page_data,
                        parse=parse,
                        document_id=document_id,
                    )

            except Exception as e:
                print(f"[数据库同步] 警告: 写入数据库失败: {e}")

        print(f"\n[主题搜索任务] 完成。共存储了 {total_saved} 篇相关内容。")

    except Exception as e:
        print(f"[主题搜索任务] 发生严重错误: {e}")
        traceback.print_exc()


def _background_crawl_from_post_wrapper(tenant_id: str, source_ids: list, depth: int, max_pages: int, kb_id: str = None, parse: bool = False):
    """同步的包装函数，在线程中启动asyncio事件循环"""
    asyncio.run(_async_crawl_from_post_worker(tenant_id, source_ids, depth, max_pages, kb_id, parse))


def _background_topic_search_wrapper(
    tenant_id: str, source_ids: list, keywords: list, max_depth: int, max_pages_per_source: int, max_crawl_pages_per_source: int, score_threshold: float, kb_id: str = None, parse: bool = False
):
    """主题搜索的同步包装函数"""
    asyncio.run(_async_topic_search_worker(tenant_id, source_ids, keywords, max_depth, max_pages_per_source, max_crawl_pages_per_source, score_threshold, kb_id, parse))


# =================================================================================
# Flask Blueprint 和 API 端点
# =================================================================================
manager = Blueprint("news_collector_bp", __name__)


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

        source = NewsSourceService.create_source(tenant_id=tenant_id, user_id=tenant_id, **req)
        return get_json_result(data={"source": source})

    except Exception as e:
        return server_error_response(e)


@manager.route("/news_collector/sources/<source_id>", methods=["GET"])
@token_required
def get_news_source(tenant_id, source_id):
    """获取单个新闻源详情"""
    try:
        _, source_model = NewsSourceService.get_by_id(source_id)

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
        NewsSourceService.update_source(source_id=source_id, tenant_id=tenant_id, status="deleted")
        return get_json_result(message="删除成功")

    except ValueError as e:
        return get_json_result(code=404, message=str(e))
    except Exception as e:
        return server_error_response(e)


# ========== 即时抓取 ==========


@manager.route("/news_collector/crawl_from_post", methods=["POST"])
@token_required
async def crawl_from_post_api(tenant_id):
    """
    即时抓取：接收新闻源ID列表和控制参数，启动后台抓取任务。
    根据新闻源的 remark 字段自动选择抓取模式（精确/自动）。
    """
    req_data = await request.get_json()

    source_ids = req_data.get("source_ids")
    depth = int(req_data.get("depth", 2))
    max_pages_per_source = int(req_data.get("max_pages_per_source", 50))

    if not isinstance(source_ids, list) or not source_ids:
        return get_json_result(code=400, message="请求体必须包含一个名为 'source_ids' 的非空数组。")

    try:
        thread = threading.Thread(target=_background_crawl_from_post_wrapper, args=(tenant_id, source_ids, depth, max_pages_per_source))
        thread.start()

        return get_json_result(data={"message": f"已成功启动后台即时抓取任务，将从数据库加载并处理 {len(source_ids)} 个新闻源。"})

    except Exception as e:
        traceback.print_exc()
        return server_error_response(e)


# ========== 主题搜索抓取 (改进版) ==========


@manager.route("/news_collector/topic_search", methods=["POST"])
@token_required
async def topic_search_api(tenant_id):
    """
    主题搜索抓取（改进版）：根据关键词从多个新闻源进行智能爬取，优先抓取与主题相关的内容。
    改进点：
    1. 使用 source_ids 替代 start_url
    2. 跳过低分/重复内容时继续搜索，确保收集到足够数量的新内容

    请求体:
    {
        "source_ids": ["id1", "id2"],           // 新闻源ID列表
        "keywords": ["电力市场", "现货交易"],     // 关键词列表
        "max_depth": 2,                          // 爬取深度 (可选, 默认2)
        "max_pages_per_source": 5,               // 每个源最大收集篇数 (可选, 默认5)
        "max_crawl_pages_per_source": 100,       // 每个源最大爬取页数 (可选, 默认100)
        "score_threshold": 0.3,                  // 相关性分数阈值 (可选, 默认0.3)
        "kb_id": "knowledge_base_id",            // 目标知识库ID (可选)
        "parse": false                           // 是否自动解析 (可选, 默认false)
    }
    """
    req_data = await request.get_json()

    source_ids = req_data.get("source_ids")
    keywords = req_data.get("keywords")
    max_depth = int(req_data.get("max_depth", 2))
    max_pages_per_source = int(req_data.get("max_pages_per_source", 5))
    max_crawl_pages_per_source = int(req_data.get("max_crawl_pages_per_source", 100))
    score_threshold = float(req_data.get("score_threshold", 0.3))
    kb_id = req_data.get("kb_id")
    parse = req_data.get("parse", False)

    # 参数验证
    if not source_ids or not isinstance(source_ids, list) or len(source_ids) == 0:
        return get_json_result(code=400, message="新闻源ID列表 (source_ids) 不能为空，应为非空数组")

    if not keywords or not isinstance(keywords, list) or len(keywords) == 0:
        return get_json_result(code=400, message="关键词列表 (keywords) 不能为空，应为非空数组")

    # 验证知识库（如果指定）
    if kb_id:
        if not KnowledgebaseService.accessible(kb_id, tenant_id):
            return get_json_result(code=403, message=f"无权访问知识库 {kb_id} 或知识库不存在。")

    try:
        thread = threading.Thread(
            target=_background_topic_search_wrapper, args=(tenant_id, source_ids, keywords, max_depth, max_pages_per_source, max_crawl_pages_per_source, score_threshold, kb_id, parse)
        )
        thread.start()

        return get_json_result(
            data={
                "message": f"已成功启动主题搜索任务，关键词: {keywords}，新闻源数: {len(source_ids)}",
                "params": {
                    "source_ids": source_ids,
                    "keywords": keywords,
                    "max_depth": max_depth,
                    "max_pages_per_source": max_pages_per_source,
                    "max_crawl_pages_per_source": max_crawl_pages_per_source,
                    "score_threshold": score_threshold,
                    "kb_id": kb_id,
                },
            }
        )

    except Exception as e:
        traceback.print_exc()
        return server_error_response(e)


# ========== 内容哈希管理 ==========


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

        records, total = NewsContentService.get_hashes_paginated(tenant_id=tenant_id, page=page, page_size=page_size)

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
        return get_json_result(message=f"成功删除 {deleted_count} 条内容记录。抓取历史已重置。")

    except Exception as e:
        return server_error_response(e)
