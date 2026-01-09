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
from api.db.services.news_service import NewsSourceService, NewsContentService, CrawlGroupService, CrawlTargetService, CrawlTaskLogService
from api.db.services.knowledgebase_service import KnowledgebaseService
from api.db.services.document_service import DocumentService
from api.db.services.file_service import FileService
from common.misc_utils import get_uuid
from common import settings
from common.constants import RetCode
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
import aiohttp

# 【智能爬取】导入 BestFirst 策略和评分器
from crawl4ai.deep_crawling import BestFirstCrawlingStrategy
from crawl4ai.deep_crawling.scorers import KeywordRelevanceScorer
from crawl4ai.deep_crawling.filters import FilterChain, ContentTypeFilter

# 【URL Seeding】导入 URL 发现和配置
from crawl4ai import AsyncUrlSeeder, SeedingConfig


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
# PolicyFeatureDetector 类 - 政策文档特征检测器
# =================================================================================
class PolicyFeatureDetector:
    """检测页面是否为电力能源政策文档

    识别特征：
    1. 标题包含政策关键词（通知、文件、政策、办法等）
    2. 内容包含能源电力关键词
    3. 包含文号格式（如：发改能源〔2024〕123号）
    4. 包含附件下载链接
    """

    # 政策文档类型关键词
    POLICY_TYPE_KEYWORDS = [
        "通知",
        "文件",
        "政策",
        "办法",
        "规定",
        "意见",
        "方案",
        "规划",
        "决定",
        "批复",
        "公告",
        "函",
        "指导",
        "措施",
        "制度",
        "条例",
        "纲要",
        "指南",
        "标准",
        "细则",
        "暂行",
        "试行",
    ]

    # 能源电力相关关键词
    ENERGY_KEYWORDS = [
        "电力",
        "能源",
        "电网",
        "电价",
        "供电",
        "用电",
        "发电",
        "输电",
        "配电",
        "售电",
        "电量",
        "电费",
        "电力市场",
        "现货",
        "辅助服务",
        "可再生能源",
        "新能源",
        "光伏",
        "风电",
        "储能",
        "电站",
        "变电",
        "输变电",
        "电力系统",
        "电力调度",
        "电力交易",
        "电力改革",
        "电力规划",
        "电力建设",
        "电力监管",
        "电力安全",
        "节能减排",
    ]

    # 发文单位关键词
    ISSUER_KEYWORDS = [
        "发改委",
        "发展改革委",
        "国家发展改革委",
        "国家能源局",
        "能源局",
        "电监会",
        "能监办",
        "国务院",
        "工信部",
        "住建部",
        "财政部",
        "国家电网",
        "南方电网",
        "电力公司",
        "省政府",
        "市政府",
    ]

    # 文号正则表达式（匹配如：发改能源〔2024〕123号）
    DOC_NUMBER_PATTERNS = [
        re.compile(r"[〔\[]?\d{4}[〕\]]\s?\d{1,4}\s?号"),  # 〔2024〕123号
        re.compile(r"第\s?\d{1,4}\s?号"),  # 第123号
        re.compile(r"\d{4}年第\d{1,4}号"),  # 2024年第123号
    ]

    # 附件相关关键词
    ATTACHMENT_KEYWORDS = ["附件", "下载", "文件下载", "政策原文", "解读", "全文"]

    def __init__(self):
        pass

    def detect(self, html: str, title: str, content: str, url: str = "") -> dict:
        """检测是否为政策文档

        返回:
        {
            'is_policy': bool,          # 是否为政策文档
            'score': float,             # 政策特征分数 (0-1)
            'features': {               # 识别到的特征
                'has_policy_type': bool,
                'has_energy_keywords': bool,
                'has_doc_number': bool,
                'has_issuer': bool,
                'has_attachment': bool,
                'doc_number': str or None,
                'matched_energy_keywords': list
            }
        }
        """
        features = {"has_policy_type": False, "has_energy_keywords": False, "has_doc_number": False, "has_issuer": False, "has_attachment": False, "doc_number": None, "matched_energy_keywords": []}

        # 1. 检测标题中的政策类型关键词
        for keyword in self.POLICY_TYPE_KEYWORDS:
            if keyword in title:
                features["has_policy_type"] = True
                break

        # 2. 检测能源电力关键词
        full_text = title + " " + content
        for keyword in self.ENERGY_KEYWORDS:
            if keyword in full_text:
                features["has_energy_keywords"] = True
                features["matched_energy_keywords"].append(keyword)

        # 3. 检测文号
        for pattern in self.DOC_NUMBER_PATTERNS:
            match = pattern.search(full_text[:500])  # 只搜索前500字符
            if match:
                features["has_doc_number"] = True
                features["doc_number"] = match.group(0)
                break

        # 4. 检测发文单位
        for keyword in self.ISSUER_KEYWORDS:
            if keyword in full_text[:300]:  # 只搜索前300字符
                features["has_issuer"] = True
                break

        # 5. 检测附件链接（从HTML中）
        for keyword in self.ATTACHMENT_KEYWORDS:
            if keyword in html:
                features["has_attachment"] = True
                break

        # 计算政策特征分数
        score = 0.0
        if features["has_policy_type"]:
            score += 0.3
        if features["has_energy_keywords"]:
            score += 0.3
        if features["has_doc_number"]:
            score += 0.2
        if features["has_issuer"]:
            score += 0.1
        if features["has_attachment"]:
            score += 0.1

        # 判定为政策文档的条件：
        # 1. 有政策类型关键词 + 有能源关键词，或
        # 2. 有文号 + 有能源关键词
        is_policy = (features["has_policy_type"] and features["has_energy_keywords"]) or (features["has_doc_number"] and features["has_energy_keywords"])

        return {"is_policy": is_policy, "score": score, "features": features}


# =================================================================================
# AttachmentDownloader 类 - 附件下载器
# =================================================================================
class AttachmentDownloader:
    """检测和下载政策附件"""

    # 支持的附件格式
    ATTACHMENT_EXTENSIONS = [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".zip", ".rar"]

    # 附件链接关键词
    ATTACHMENT_LINK_KEYWORDS = ["附件", "下载", "文件", "政策", "原文", "全文"]

    def __init__(self):
        pass

    async def find_attachments(self, html: str, base_url: str) -> List[dict]:
        """从HTML中查找附件链接

        返回: [
            {
                'url': str,
                'filename': str,
                'extension': str,
                'link_text': str
            }
        ]
        """
        if not html:
            return []

        try:
            soup = BeautifulSoup(html, "html.parser")
            attachments = []

            # 查找所有链接
            for link in soup.find_all("a", href=True):
                href = link.get("href", "")
                link_text = link.get_text(strip=True)

                if not href:
                    continue

                # 转换为绝对URL
                absolute_url = urljoin(base_url, href)

                # 检查是否为附件链接
                is_attachment = False
                extension = None

                # 方法1: 检查URL扩展名
                for ext in self.ATTACHMENT_EXTENSIONS:
                    if absolute_url.lower().endswith(ext):
                        is_attachment = True
                        extension = ext
                        break

                # 方法2: 检查链接文本
                if not is_attachment:
                    for keyword in self.ATTACHMENT_LINK_KEYWORDS:
                        if keyword in link_text:
                            # 进一步检查URL中是否包含文件扩展名
                            for ext in self.ATTACHMENT_EXTENSIONS:
                                if ext in absolute_url.lower():
                                    is_attachment = True
                                    extension = ext
                                    break
                            if is_attachment:
                                break

                if is_attachment:
                    # 生成文件名
                    filename = self._extract_filename(absolute_url, link_text, extension)

                    attachments.append({"url": absolute_url, "filename": filename, "extension": extension, "link_text": link_text})

            return attachments

        except Exception as e:
            print(f"[AttachmentDownloader] 查找附件时出错: {e}")
            return []

    def _extract_filename(self, url: str, link_text: str, extension: str) -> str:
        """从URL或链接文本中提取文件名"""
        # 尝试从URL中提取文件名
        try:
            parsed_url = urlparse(url)
            path = parsed_url.path
            if path:
                filename = os.path.basename(path)
                if filename and extension in filename:
                    return filename
        except Exception:
            pass

        # 使用链接文本作为文件名
        if link_text:
            safe_name = re.sub(r'[\\/*?:"<>|]', "", link_text)
            safe_name = re.sub(r"\s+", "_", safe_name)
            safe_name = safe_name[:50]  # 限制长度
            if extension:
                return f"{safe_name}{extension}"
            return safe_name

        # 生成默认文件名
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"attachment_{timestamp}{extension or ''}"

    async def download_attachment(self, url: str, save_dir: str, filename: str = None) -> dict:
        """下载附件到本地

        返回: {
            'success': bool,
            'filename': str,
            'filepath': str,
            'size': int,
            'url': str,
            'error': str or None
        }
        """
        try:
            # 确保保存目录存在
            os.makedirs(save_dir, exist_ok=True)

            # 如果未指定文件名，从URL中提取
            if not filename:
                filename = os.path.basename(urlparse(url).path) or f"attachment_{get_uuid()[:8]}"

            filepath = os.path.join(save_dir, filename)

            # 下载文件
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=25)) as response:  # 25秒超时（大规模爬取优化）
                    if response.status == 200:
                        content = await response.read()

                        # 保存文件
                        async with aiofiles.open(filepath, "wb") as f:
                            await f.write(content)

                        file_size = len(content)
                        print(f"[AttachmentDownloader] 成功下载附件: {filename} ({file_size} bytes)")

                        return {"success": True, "filename": filename, "filepath": filepath, "size": file_size, "url": url, "error": None}
                    else:
                        error_msg = f"HTTP {response.status}"
                        print(f"[AttachmentDownloader] 下载失败: {url} ({error_msg})")
                        return {"success": False, "filename": filename, "filepath": None, "size": 0, "url": url, "error": error_msg}

        except Exception as e:
            print(f"[AttachmentDownloader] 下载附件时出错: {url} - {e}")
            return {"success": False, "filename": filename, "filepath": None, "size": 0, "url": url, "error": str(e)}


# =================================================================================
# TopicCrawler 类 - 修复版
# =================================================================================
class TopicCrawler:
    """基于内容评分的主题搜索爬虫 - 改进版

    改进内容：
    1. 每个源使用独立的浏览器配置，避免跨源的上下文冲突
    2. 改进的资源管理，确保爬虫正确关闭
    3. 更强的异常处理，忽略已知的crawl4ai库问题
    4. 源之间添加延迟，确保资源完全释放
    5. 集成政策文档识别功能
    6. 自动检测和下载政策附件
    """

    def __init__(self):
        self.content_scorer = None
        self.policy_detector = PolicyFeatureDetector()
        self.attachment_downloader = AttachmentDownloader()

    async def search_by_topic_from_sources(
        self,
        sources: list,
        keywords: list,
        tenant_id: str,  # 【新增】租户ID，用于URL去重
        max_depth: int = 2,
        max_pages_per_source: int = 30,
        max_crawl_pages_per_source: int = 100,
        score_threshold: float = 0.3,
        persistent_hashes: set = None,
    ):
        """从多个新闻源根据主题关键词进行智能搜索爬取

        改进点（v4.1）：
        1. 集成URL访问记录，避免重复爬取
        2. 详细的计数统计（区分爬取、处理、收集等）
        3. 保存详细的爬取日志
        """
        import time

        start_time = time.time()

        if persistent_hashes is None:
            persistent_hashes = set()

        # 初始化内容评分器
        self.content_scorer = ChineseContentScorer(keywords=keywords)

        all_crawled_data = []
        all_source_stats = []  # 【新增】每个源的统计信息

        print("\n[TopicCrawler] 开始多源主题搜索爬取（内容评分模式）")
        print(f"[TopicCrawler] 新闻源数量: {len(sources)}")
        print(f"[TopicCrawler] 关键词: {keywords}")
        print(f"[TopicCrawler] 每源最大收集: {max_pages_per_source}, 每源最大爬取: {max_crawl_pages_per_source}")
        print(f"[TopicCrawler] 内容评分阈值: {score_threshold}")

        for i, source in enumerate(sources):
            source_id = source.get("id")
            source_name = source.get("name")
            start_url = source.get("url")

            if not start_url:
                continue

            print(f"\n[TopicCrawler] === 处理源 {i + 1}/{len(sources)}: {source_name} ===")

            source_start_time = time.time()

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
                        "--disable-images",
                        "--blink-settings=imagesEnabled=false",
                    ],
                )

                source_articles, source_stats = await self._crawl_single_source(
                    start_url=start_url,
                    source_id=source_id,
                    source_name=source_name,
                    tenant_id=tenant_id,  # 【新增】传递 tenant_id
                    keywords=keywords,
                    max_depth=max_depth,
                    max_pages=max_pages_per_source,
                    max_crawl_pages=max_crawl_pages_per_source,
                    score_threshold=score_threshold,
                    persistent_hashes=persistent_hashes,
                    browser_config=browser_config,
                )

                source_duration = time.time() - source_start_time
                source_stats["duration_seconds"] = round(source_duration, 2)
                all_source_stats.append(source_stats)

                all_crawled_data.extend(source_articles)
                print(f"[TopicCrawler] 源 '{source_name}' 完成: 收集 {len(source_articles)} 篇，耗时 {source_duration:.1f}秒")

            except Exception as e:
                print(f"[TopicCrawler] 处理源 '{source_name}' 时发生错误: {e}")
                traceback.print_exc()

                # 记录失败的源
                all_source_stats.append({"source_id": source_id, "source_name": source_name, "error": str(e), "duration_seconds": round(time.time() - source_start_time, 2)})

            # 【关键修复】源之间添加延迟，确保浏览器资源完全释放
            if i < len(sources) - 1:
                print("[TopicCrawler] 等待资源释放...")
                await asyncio.sleep(2)

        total_duration = time.time() - start_time

        # 【新增】保存详细日志
        self._save_crawl_log(keywords=keywords, total_collected=len(all_crawled_data), total_duration=total_duration, source_stats=all_source_stats)

        print("\n[TopicCrawler] ========== 爬取任务完成 ==========")
        print(f"[TopicCrawler] 总耗时: {total_duration:.1f}秒")
        print(f"[TopicCrawler] 共收集: {len(all_crawled_data)} 篇政策内容")
        print("[TopicCrawler] 日志已保存至: crawl4ai_data/logs/")

        return all_crawled_data

    async def _crawl_single_source(
        self,
        start_url: str,
        source_id: str,
        source_name: str,  # 【新增】源名称
        tenant_id: str,  # 【新增】租户ID
        keywords: list,
        max_depth: int,
        max_pages: int,
        max_crawl_pages: int,
        score_threshold: float,
        persistent_hashes: set,
        browser_config: BrowserConfig,
    ):
        """爬取单个新闻源 - 专注政策文档（v4.1 - URL去重版）

        参数说明：
        - max_pages: 最终收集的政策文档数量（目标）
        - max_crawl_pages: 最多爬取多少个页面（总页面数限制）

        返回：
        - (newly_crawled_data, source_stats) 元组

        改进点：
        1. 集成URL访问记录，跳过已访问URL
        2. 详细的计数统计
        3. 批量记录URL访问
        """
        from api.db.services.news_service import NewsVisitedUrlService

        # 统计数据
        stats = {
            "source_id": source_id,
            "source_name": source_name,
            "crawl4ai_returned": 0,  # crawl4ai返回的页面数
            "skipped_visited": 0,  # 跳过的已访问页面数
            "skipped_failed": 0,  # 跳过的失败页面数
            "processed": 0,  # 实际处理的页面数
            "policy_found": 0,  # 发现的政策页面数
            "policy_low_score": 0,  # 政策但分数低的页面数
            "policy_duplicate": 0,  # 重复的政策页面数
            "collected": 0,  # 最终收集的政策数
        }

        newly_crawled_data = []
        urls_to_record = []  # 【新增】需要记录到数据库的URL列表

        print(f"[TopicCrawler] 目标: 收集 {max_pages} 篇政策内容")
        print(f"[TopicCrawler] 限制: 最多爬取 {max_crawl_pages} 个页面")
        print("[TopicCrawler] 策略: 智能BestFirst（优先爬取政策相关链接）")
        print("[TopicCrawler] 超时设置: 8秒/页")

        # ===== 【关键】加载已访问URL =====
        print("[TopicCrawler] 正在加载已访问URL记录...")
        try:
            visited_stats = NewsVisitedUrlService.get_visited_count(tenant_id, source_id)
            print(f"[TopicCrawler] 已访问记录: 总计{visited_stats['total']}个URL (政策{visited_stats['policy']}, 已收集{visited_stats['collected']}, 失败{visited_stats['failed']})")
        except Exception as e:
            print(f"[TopicCrawler] 警告: 无法加载访问记录: {e}")

        # ===== 【智能爬取】使用 BestFirst 策略 + 关键词评分 =====

        # 1. 关键词评分器：自动识别政策相关链接
        keyword_scorer = KeywordRelevanceScorer(
            keywords=[
                # 中文政策类型关键词
                "政策",
                "通知",
                "文件",
                "办法",
                "规定",
                "意见",
                "公告",
                "决定",
                "方案",
                "规划",
                "标准",
                "指南",
                "细则",
                "条例",
                "法规",
                # 中文能源电力关键词
                "电力",
                "能源",
                "电网",
                "电价",
                "市场",
                "交易",
                "现货",
                "新能源",
                "光伏",
                "风电",
                "储能",
                "配电",
                "输电",
                # 英文关键词
                "policy",
                "notice",
                "document",
                "regulation",
                "announcement",
                "energy",
                "power",
                "electricity",
                "market",
                "trading",
                # URL路径关键词
                "zc",
                "wj",
                "tz",
                "gg",
                "fgw",
                "nyj",
                "drc",
                "news",
                "xw",
                "dt",
                "zwgk",
                # 地方政府网站常见URL模式
                "gzdt",
                "fzggdt",
                "zcjd",
                "zcwj",
                "gfxwj",
                "zfxxgk",
                "yjzj",
                "ztzl",
                "bmxx",
                # 组合关键词
                "电力市场",
                "能源政策",
                "电价政策",
                "市场交易",
            ]
            + keywords,  # 加上用户提供的搜索关键词
            weight=0.3,  # 关键词权重（0.0-1.0）
        )

        # 2. 组合过滤器
        filter_chain = FilterChain(
            [
                ContentTypeFilter(allowed_types=["text/html"]),
            ]
        )

        # 3. 配置 BestFirst 策略
        config = CrawlerRunConfig(
            deep_crawl_strategy=BestFirstCrawlingStrategy(
                max_depth=max_depth,
                include_external=False,
                max_pages=max_crawl_pages,
                url_scorer=keyword_scorer,
                filter_chain=filter_chain,
            ),
            scraping_strategy=LXMLWebScrapingStrategy(),
            stream=False,
            verbose=True,
            page_timeout=10000,  # 页面超时10秒（从8秒增加，确保页面完全加载）
            wait_until="domcontentloaded",  # 【修复】改为 domcontentloaded，确保 DOM 和链接加载完成
            delay_before_return_html=1.5,  # 【新增】额外等待1.5秒，确保动态内容加载完成
        )

        crawler = None
        try:
            # 【智能爬取】批量模式处理
            crawler = AsyncWebCrawler(config=browser_config)
            await crawler.__aenter__()

            try:
                # 批量模式：返回结果列表
                print("[TopicCrawler] 开始智能爬取（BestFirst策略）...")
                crawl_result = await crawler.arun(start_url, config=config)

                # 提取结果列表
                results_list = []
                if isinstance(crawl_result, list):
                    results_list = crawl_result
                elif hasattr(crawl_result, "results") and crawl_result.results:
                    results_list = crawl_result.results
                else:
                    results_list = []

                stats["crawl4ai_returned"] = len(results_list)
                print(f"[TopicCrawler] crawl4ai返回: {len(results_list)} 个页面")

                # 【关键】批量检查URL是否已访问
                all_urls = [r.url for r in results_list if hasattr(r, "url")]
                visited_url_map = {}
                if all_urls:
                    try:
                        visited_url_map = NewsVisitedUrlService.batch_check_visited(tenant_id, all_urls)
                    except Exception as e:
                        print(f"[TopicCrawler] 警告: 批量检查URL失败: {e}")

                # 遍历所有结果（已按BestFirst评分排序）
                for result in results_list:
                    # 停止条件1：已收集到足够的政策内容
                    if stats["collected"] >= max_pages:
                        print(f"[TopicCrawler] ✓ 已收集到 {max_pages} 篇政策内容，停止处理")
                        break

                    # 停止条件2：已处理足够多的页面
                    if stats["processed"] >= max_crawl_pages:
                        print(f"[TopicCrawler] ✓ 已处理 {max_crawl_pages} 个页面，停止处理")
                        break

                    url = result.url if hasattr(result, "url") else None
                    if not url:
                        continue

                    # 【关键】检查是否已访问
                    if visited_url_map.get(url, False):
                        stats["skipped_visited"] += 1
                        if stats["skipped_visited"] % 20 == 1:  # 每20个输出一次
                            print(f"[TopicCrawler] 跳过已访问URL (已跳过{stats['skipped_visited']}个)")
                        continue

                    # 检查是否成功
                    if not result.success:
                        stats["skipped_failed"] += 1
                        urls_to_record.append(
                            {
                                "url": url,
                                "source_id": source_id,
                                "failed": True,
                                "is_policy": False,
                                "collected": False,
                            }
                        )
                        continue

                    stats["processed"] += 1

                    # 提取内容
                    content_text = self._extract_content(result)
                    if not content_text or len(content_text.strip()) < 100:
                        urls_to_record.append(
                            {
                                "url": url,
                                "source_id": source_id,
                                "failed": False,
                                "is_policy": False,
                                "collected": False,
                            }
                        )
                        continue

                    # 提取标题
                    title = self._extract_title(result)

                    # ===== 【关键1】检测是否为政策文档 =====
                    html = getattr(result, "html", None) or ""
                    policy_info = self.policy_detector.detect(html, title, content_text, url)

                    # 如果不是政策文档，记录并跳过
                    if not policy_info["is_policy"]:
                        urls_to_record.append(
                            {
                                "url": url,
                                "source_id": source_id,
                                "failed": False,
                                "is_policy": False,
                                "collected": False,
                                "title": title,
                            }
                        )
                        if stats["processed"] % 10 == 0:
                            print(f"[TopicCrawler] 已处理 {stats['processed']} 页 | 发现 {stats['policy_found']} 个政策 | 收集 {stats['collected']} 篇")
                        continue

                    # ===== 【关键2】这是政策页面 =====
                    stats["policy_found"] += 1
                    depth = result.metadata.get("depth", 0) if result.metadata else 0

                    # 计算评分
                    content_score = self.content_scorer.score(content_text, title)
                    matched_keywords = self.content_scorer.get_matched_keywords(content_text + " " + title)
                    policy_score = policy_info["score"]
                    final_score = content_score * 0.5 + policy_score * 0.5

                    # 显示详细评分
                    link_score = result.metadata.get("score", 0.0) if result.metadata else 0.0
                    print(
                        f"[TopicCrawler] 🏛️ 政策#{stats['policy_found']} | 深度{depth} | "
                        f"链接分{link_score:.2f} | 综合分{final_score:.2f} "
                        f"(内容{content_score:.2f}/政策{policy_score:.2f}) | {title[:30]}..."
                    )

                    # 检查分数是否达标
                    if final_score < score_threshold:
                        stats["policy_low_score"] += 1
                        print("[TopicCrawler]    ⊗ 分数过低，跳过")
                        urls_to_record.append(
                            {
                                "url": url,
                                "source_id": source_id,
                                "failed": False,
                                "is_policy": True,
                                "collected": False,
                                "title": title,
                            }
                        )
                        continue

                    # ===== 【关键3】去重检查 =====
                    content_hash = hashlib.sha256(content_text.encode("utf-8")).hexdigest()

                    # 3.1 内存去重
                    if content_hash in persistent_hashes:
                        stats["policy_duplicate"] += 1
                        print("[TopicCrawler]    ⊗ 重复内容（哈希），跳过")
                        urls_to_record.append(
                            {
                                "url": url,
                                "source_id": source_id,
                                "failed": False,
                                "is_policy": True,
                                "collected": False,
                                "title": title,
                                "page_hash": content_hash,
                            }
                        )
                        continue

                    # 3.2 数据库去重
                    try:
                        from api.db.services.news_service import NewsContentService

                        if NewsContentService.model.select().where(NewsContentService.model.original_url == url).exists():
                            stats["policy_duplicate"] += 1
                            print("[TopicCrawler]    ⊗ URL已存在数据库，跳过")
                            urls_to_record.append(
                                {
                                    "url": url,
                                    "source_id": source_id,
                                    "failed": False,
                                    "is_policy": True,
                                    "collected": False,
                                    "title": title,
                                    "page_hash": content_hash,
                                }
                            )
                            continue
                    except Exception as db_error:
                        print(f"[TopicCrawler]    ⚠ 数据库去重检查失败: {db_error}")

                    persistent_hashes.add(content_hash)

                    # 查找并下载附件
                    attachments = await self._download_attachments(html, url, title)

                    # 收集内容
                    article_data = {
                        "url": url,
                        "source_id": source_id,
                        "score": content_score,
                        "final_score": final_score,
                        "depth": depth,
                        "content": content_text,
                        "content_hash": content_hash,
                        "title": title,
                        "matched_keywords": matched_keywords,
                        "crawl_timestamp": datetime.now().isoformat(),
                        "is_policy": True,
                        "policy_score": policy_score,
                        "policy_features": policy_info["features"],
                        "attachments": attachments,
                        "attachment_count": len(attachments),
                    }
                    newly_crawled_data.append(article_data)
                    stats["collected"] += 1

                    # 记录成功收集的URL
                    urls_to_record.append(
                        {
                            "url": url,
                            "source_id": source_id,
                            "failed": False,
                            "is_policy": True,
                            "collected": True,
                            "title": title,
                            "page_hash": content_hash,
                        }
                    )

                    attachment_tag = f"📎{len(attachments)}" if attachments else ""
                    print(f"[TopicCrawler]    ✓ 收集成功 {attachment_tag} [已收集 {stats['collected']}/{max_pages}]")

            except Exception as iter_error:
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
                    pass

            await asyncio.sleep(0.5)

        # 【新增】批量记录URL访问到数据库
        if urls_to_record:
            print(f"[TopicCrawler] 正在记录 {len(urls_to_record)} 个URL访问记录...")
            try:
                NewsVisitedUrlService.batch_record_visits(tenant_id, urls_to_record)
                print("[TopicCrawler] URL访问记录已保存")
            except Exception as record_error:
                print(f"[TopicCrawler] 警告: URL访问记录保存失败: {record_error}")

        # 打印统计摘要
        print("\n[TopicCrawler] ===== 单源统计摘要 =====")
        print(f"[TopicCrawler] crawl4ai返回: {stats['crawl4ai_returned']} 个页面")
        print(f"[TopicCrawler] 跳过已访问: {stats['skipped_visited']} 个")
        print(f"[TopicCrawler] 跳过失败: {stats['skipped_failed']} 个")
        print(f"[TopicCrawler] 实际处理: {stats['processed']} 个")
        print(f"[TopicCrawler] 发现政策: {stats['policy_found']} 个")
        print(f"[TopicCrawler]   - 分数过低: {stats['policy_low_score']} 个")
        print(f"[TopicCrawler]   - 重复内容: {stats['policy_duplicate']} 个")
        print(f"[TopicCrawler] 最终收集: {stats['collected']} 篇")

        return newly_crawled_data, stats

    def _extract_title(self, result) -> str:
        """从爬取结果中提取标题"""
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
                    from bs4 import BeautifulSoup

                    soup = BeautifulSoup(html, "html.parser")
                    title = soup.title.string if soup.title and soup.title.string else title
            except Exception:
                pass
        return (title or "").strip()

    async def _download_attachments(self, html: str, url: str, title: str) -> list:
        """下载页面的附件文件"""
        attachments = []
        if not html:
            return attachments

        try:
            found_attachments = await self.attachment_downloader.find_attachments(html, url)

            if found_attachments:
                print(f"[TopicCrawler]    📎 发现 {len(found_attachments)} 个附件")

                base_dir = "crawl4ai_data"
                safe_title = _sanitize_filename(title[:30] or "untitled")
                attachment_dir = os.path.join(base_dir, "attachments", safe_title)

                for att in found_attachments[:5]:  # 最多下载5个附件
                    download_result = await self.attachment_downloader.download_attachment(url=att["url"], save_dir=attachment_dir, filename=att["filename"])

                    if download_result["success"]:
                        attachments.append(
                            {
                                "filename": download_result["filename"],
                                "filepath": download_result["filepath"],
                                "size": download_result["size"],
                                "url": download_result["url"],
                                "extension": att["extension"],
                                "link_text": att["link_text"],
                            }
                        )
                        print(f"[TopicCrawler]       ✓ {download_result['filename']}")
                    else:
                        print(f"[TopicCrawler]       ✗ {att['filename']}")

                print(f"[TopicCrawler]    ✓ 下载 {len(attachments)}/{len(found_attachments)} 个附件")
        except Exception as e:
            print(f"[TopicCrawler]    ✗ 附件处理出错: {e}")

        return attachments

    def _save_crawl_log(self, keywords: list, total_collected: int, total_duration: float, source_stats: list):
        """保存详细的爬取日志到文件"""
        import json
        import time

        log_dir = "crawl4ai_data/logs"
        os.makedirs(log_dir, exist_ok=True)

        timestamp = int(time.time() * 1000)
        log_filename = f"crawl_log_{timestamp}.json"
        log_path = os.path.join(log_dir, log_filename)

        log_data = {
            "timestamp": timestamp,
            "datetime": datetime.now().isoformat(),
            "keywords": keywords,
            "total_duration_seconds": round(total_duration, 2),
            "total_collected": total_collected,
            "source_count": len(source_stats),
            "sources": source_stats,
        }

        try:
            with open(log_path, "w", encoding="utf-8") as f:
                json.dump(log_data, f, ensure_ascii=False, indent=2)
            print(f"[TopicCrawler] 日志已保存: {log_path}")
        except Exception as e:
            print(f"[TopicCrawler] 警告: 日志保存失败: {e}")

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
# UrlSeedingCrawler 类 - URL Seeding智能爬取（方案A）
# =================================================================================
class UrlSeedingCrawler:
    """基于URL Seeding的智能爬虫 - 先发现，再过滤，后爬取

    改进点（相比TopicCrawler）：
    1. 先发现全部URL（sitemap + Common Crawl），几秒完成
    2. 使用BM25对元数据（title, description）进行评分过滤，无需爬取
    3. 只爬取高分URL，避免浪费资源
    4. 简化版：移除PolicyFeatureDetector，只用BM25

    预期性能：
    - URL发现：10源 × 1000 URL = 10,000 URL in 2分钟
    - BM25过滤：即时完成
    - 精准爬取：200个高分URL in 20分钟
    - 总计：22分钟 vs 旧方法100分钟（78%提升）
    """

    def __init__(self):
        self.attachment_downloader = AttachmentDownloader()

    async def search_by_url_seeding(
        self,
        sources: list,
        keywords: list,
        tenant_id: str,
        max_pages_per_source: int = 30,
        max_urls_per_source: int = 1000,  # 新增：每源最大URL发现数量
        relevance_threshold: float = 0.3,  # 改名：相关性阈值（自定义评分），默认0.3
        persistent_hashes: set = None,
    ):
        """从多个新闻源使用URL Seeding进行智能搜索爬取

        参数:
            sources: 新闻源列表
            keywords: 关键词列表
            tenant_id: 租户ID
            max_pages_per_source: 每源最大收集篇数（默认30）
            max_urls_per_source: 每源最大URL发现数量（默认1000）
                - 从sitemap+CommonCrawl发现的URL总数上限
                - 推荐值：1000（平衡速度和覆盖度）
                - 更多：2000-5000（需要更长时间）
                - 更少：500（更快但可能遗漏）
            relevance_threshold: 相关性阈值，用于过滤URL（默认0.3）
                - 评分范围：0-1.0（URL路径0.15 + 预定义关键词0.25 + 用户关键词0.6）
                - 用户关键词权重最高（0.6），确保用户搜索意图优先
                - 推荐值：0.3（至少匹配URL或部分关键词）
                - 更严格：0.5（需要匹配用户关键词）
                - 更宽松：0.2（匹配部分即可）
            persistent_hashes: 已存在的内容哈希集合

        返回:
            收集到的文章数据列表
        """
        import time

        start_time = time.time()

        if persistent_hashes is None:
            persistent_hashes = set()

        all_crawled_data = []
        all_source_stats = []

        print("\n[UrlSeedingCrawler] 开始URL Seeding智能爬取")
        print(f"[UrlSeedingCrawler] 新闻源数量: {len(sources)}")
        print(f"[UrlSeedingCrawler] 关键词: {keywords}")
        print(f"[UrlSeedingCrawler] 每源最大收集: {max_pages_per_source}")
        print(f"[UrlSeedingCrawler] 相关性过滤阈值: {relevance_threshold} (自定义评分，范围0-1.0，用户词权重0.6)")

        for i, source in enumerate(sources):
            source_id = source.get("id")
            source_name = source.get("name")
            start_url = source.get("url")

            if not start_url:
                continue

            print(f"\n[UrlSeedingCrawler] === 处理源 {i + 1}/{len(sources)}: {source_name} ===")

            source_start_time = time.time()

            try:
                source_articles, source_stats = await self._crawl_single_source_with_seeding(
                    start_url=start_url,
                    source_id=source_id,
                    source_name=source_name,
                    tenant_id=tenant_id,
                    keywords=keywords,
                    max_pages=max_pages_per_source,
                    max_urls=max_urls_per_source,  # 传递最大URL数量
                    relevance_threshold=relevance_threshold,  # 使用相关性阈值
                    persistent_hashes=persistent_hashes,
                )

                source_duration = time.time() - source_start_time
                source_stats["duration_seconds"] = round(source_duration, 2)
                all_source_stats.append(source_stats)

                all_crawled_data.extend(source_articles)
                print(f"[UrlSeedingCrawler] 源 '{source_name}' 完成: 收集 {len(source_articles)} 篇，耗时 {source_duration:.1f}秒")

            except Exception as e:
                print(f"[UrlSeedingCrawler] 处理源 '{source_name}' 时发生错误: {e}")
                traceback.print_exc()

                all_source_stats.append({"source_id": source_id, "source_name": source_name, "error": str(e), "duration_seconds": round(time.time() - source_start_time, 2)})

            # 源之间添加延迟
            if i < len(sources) - 1:
                print("[UrlSeedingCrawler] 等待资源释放...")
                await asyncio.sleep(1)

        total_duration = time.time() - start_time

        # 保存详细日志
        self._save_crawl_log(keywords=keywords, total_collected=len(all_crawled_data), total_duration=total_duration, source_stats=all_source_stats)

        print("\n[UrlSeedingCrawler] ========== 爬取任务完成 ==========")
        print(f"[UrlSeedingCrawler] 总耗时: {total_duration:.1f}秒")
        print(f"[UrlSeedingCrawler] 共收集: {len(all_crawled_data)} 篇内容")
        print("[UrlSeedingCrawler] 日志已保存至: crawl4ai_data/logs/")

        return all_crawled_data

    async def _crawl_single_source_with_seeding(
        self,
        start_url: str,
        source_id: str,
        source_name: str,
        tenant_id: str,
        keywords: list,
        max_pages: int,
        max_urls: int,  # 新增：每源最大URL发现数量
        relevance_threshold: float,  # 改名：相关性阈值，默认0.3
        persistent_hashes: set,
    ):
        """使用URL Seeding爬取单个新闻源

        流程：
        1. URL发现：使用AsyncUrlSeeder从sitemap+CommonCrawl发现URL
        2. BM25过滤：基于head数据（title, description）进行BM25评分
        3. 选择高分URL：选取评分最高的URL
        4. 精准爬取：只爬取选中的URL
        5. 内容去重：使用content_hash去重
        """
        from api.db.services.news_service import NewsVisitedUrlService

        stats = {
            "source_id": source_id,
            "source_name": source_name,
            "discovered_urls": 0,
            "after_bm25_filter": 0,
            "after_visited_filter": 0,
            "crawled": 0,
            "collected": 0,
            "duplicate": 0,
        }

        newly_crawled_data = []
        urls_to_record = []

        print("[UrlSeedingCrawler] ===== 第1步：URL发现 =====")

        # 构建查询字符串
        query_str = " ".join(keywords + ["政策", "通知", "文件", "办法", "规定", "意见", "公告", "电力", "能源", "电网", "电价", "市场", "交易"])

        try:
            # 使用AsyncUrlSeeder发现URL
            async with AsyncUrlSeeder() as seeder:
                # 策略1：sitemap+cc（推荐，覆盖最全）
                config = SeedingConfig(
                    source="sitemap+cc",  # sitemap + Common Crawl
                    extract_head=True,  # 提取head元数据（title, description）
                    query=query_str,  # 提供关键词用于URL发现
                    max_urls=max_urls,  # 每源最多发现的URL数量（用户可配置）
                    concurrency=10,
                )

                print(f"[UrlSeedingCrawler] 正在从 {start_url} 发现URL（策略: sitemap+CommonCrawl）...")
                discovered = await seeder.urls(start_url, config)

                stats["discovered_urls"] = len(discovered)
                print(f"[UrlSeedingCrawler] ✓ 发现 {len(discovered)} 个URL")

                # 如果发现的URL太少，尝试备用策略
                if len(discovered) < 50:
                    print("[UrlSeedingCrawler] ⚠ 发现URL数量较少，尝试备用策略...")

                    # 策略2：只用Common Crawl（适合没有sitemap的网站）
                    print("[UrlSeedingCrawler] 备用策略1: 只用Common Crawl...")
                    config_cc = SeedingConfig(
                        source="cc",  # 只用Common Crawl
                        extract_head=True,
                        query=query_str,
                        max_urls=max_urls,
                    )
                    try:
                        discovered_cc = await seeder.urls(start_url, config_cc)
                        print(f"[UrlSeedingCrawler] ✓ Common Crawl发现 {len(discovered_cc)} 个URL")

                        if len(discovered_cc) > len(discovered):
                            print(f"[UrlSeedingCrawler] ✓ 使用Common Crawl结果（{len(discovered_cc)} > {len(discovered)}）")
                            discovered = discovered_cc
                            stats["discovered_urls"] = len(discovered)
                    except Exception as cc_error:
                        print(f"[UrlSeedingCrawler] ✗ Common Crawl策略失败: {cc_error}")

                    # 如果Common Crawl也失败，尝试只用sitemap
                    if len(discovered) < 50:
                        print("[UrlSeedingCrawler] 备用策略2: 只用Sitemap...")
                        config_sitemap = SeedingConfig(
                            source="sitemap",  # 只用sitemap
                            extract_head=True,
                            query=query_str,
                            max_urls=max_urls,
                        )
                        try:
                            discovered_sitemap = await seeder.urls(start_url, config_sitemap)
                            print(f"[UrlSeedingCrawler] ✓ Sitemap发现 {len(discovered_sitemap)} 个URL")

                            if len(discovered_sitemap) > len(discovered):
                                print(f"[UrlSeedingCrawler] ✓ 使用Sitemap结果（{len(discovered_sitemap)} > {len(discovered)}）")
                                discovered = discovered_sitemap
                                stats["discovered_urls"] = len(discovered)
                        except Exception as sitemap_error:
                            print(f"[UrlSeedingCrawler] ✗ Sitemap策略失败: {sitemap_error}")

        except Exception as e:
            print(f"[UrlSeedingCrawler] URL发现失败: {e}")
            traceback.print_exc()
            return newly_crawled_data, stats

        if not discovered:
            print("[UrlSeedingCrawler] 未发现任何URL，跳过此源")
            return newly_crawled_data, stats

        print("\n[UrlSeedingCrawler] ===== 第2步：智能过滤（自定义评分）=====")
        print("[UrlSeedingCrawler] 评分方式: URL路径(15%) + 预定义词(25%) + 用户词(60%)")

        # 政策相关的URL路径模式（政府网站常用）
        POLICY_URL_PATTERNS = [
            # 中文拼音缩写
            "zcfg",
            "zcwj",
            "zc",
            "wj",
            "tz",
            "gg",
            "fgw",
            "nyj",
            "drc",
            "gzdt",
            "fzggdt",
            "zcjd",
            "gfxwj",
            "zfxxgk",
            "yjzj",
            "ztzl",
            # 英文
            "policy",
            "notice",
            "document",
            "regulation",
            "announcement",
            "news",
            "affair",
            "govern",
            # 数字编号（政策文件常有）
            r"\d{4}",
            r"[〔\[]\d{4}[〕\]]",
        ]

        # 政策相关的title关键词
        POLICY_TITLE_KEYWORDS = [
            "通知",
            "文件",
            "政策",
            "办法",
            "规定",
            "意见",
            "方案",
            "规划",
            "决定",
            "批复",
            "公告",
            "函",
            "指导",
            "措施",
            "制度",
            "条例",
            "纲要",
            "指南",
            "标准",
            "细则",
            "电力",
            "能源",
            "电网",
            "电价",
            "市场",
            "交易",
            "现货",
            "新能源",
            "光伏",
            "风电",
            "储能",
            "配电",
            "输电",
        ]

        # 合并用户关键词（不要和预定义关键词混在一起）
        predefined_keywords = set(POLICY_TITLE_KEYWORDS)  # 预定义关键词
        user_keywords_set = set(keywords)  # 用户关键词（单独处理）

        # 【改进】使用URL路径模式 + title关键词进行过滤
        # 新权重分配（总分1.0）：
        # - URL路径匹配：0.15（政策相关路径）
        # - 预定义关键词：0.25（政策类型词、能源电力词）
        # - 用户关键词：0.6（最重要！用户搜索意图）
        high_score_urls = []
        skipped_count = 0

        for url_data in discovered:
            url = url_data.get("url", "")
            head_data = url_data.get("head_data", {})
            title = head_data.get("title") or "无标题"

            # 计算自定义相关性分数
            custom_score = 0.0
            matched_reasons = []

            # 1. URL路径匹配（权重0.15）- 政策相关路径
            url_lower = url.lower()
            for pattern in POLICY_URL_PATTERNS:
                if pattern in url_lower:
                    custom_score += 0.15
                    matched_reasons.append(f"URL含'{pattern}'")
                    break

            # 2. 预定义关键词匹配（权重0.25）- 政策类型词、能源词
            title_lower = title.lower()
            predefined_matches = 0
            for keyword in predefined_keywords:
                if keyword.lower() in title_lower:
                    predefined_matches += 1

            if predefined_matches > 0:
                # 匹配越多，分数越高，最高0.25
                custom_score += min(0.25, predefined_matches * 0.08)
                if predefined_matches <= 2:  # 只显示前2个
                    matched_reasons.append(f"预定义词×{predefined_matches}")

            # 3. 用户关键词匹配（权重0.6）- 最重要！
            user_keyword_matches = 0
            matched_user_keywords = []
            for kw in user_keywords_set:
                if kw.lower() in title_lower:
                    user_keyword_matches += 1
                    if len(matched_user_keywords) < 2:  # 只显示前2个匹配的用户关键词
                        matched_user_keywords.append(kw)

            if user_keyword_matches > 0:
                # 匹配越多，分数越高，最高0.6
                user_score = min(0.6, user_keyword_matches * 0.3)
                custom_score += user_score
                matched_reasons.insert(0, f"👤用户词×{user_keyword_matches}({','.join(matched_user_keywords)})")  # 优先显示

            # 过滤：custom_score >= relevance_threshold
            # 默认阈值0.3 = 至少匹配：1个用户关键词 OR (URL路径 + 预定义词)
            if custom_score >= relevance_threshold:
                url_data["custom_score"] = custom_score
                url_data["matched_reasons"] = matched_reasons
                high_score_urls.append(url_data)

                if len(high_score_urls) <= 10:  # 只显示前10个的详细信息
                    print(f"[UrlSeedingCrawler] ✓ 通过: {title[:40]} (自定义分数={custom_score:.2f}, {', '.join(matched_reasons[:2])})")
            else:
                skipped_count += 1
                if skipped_count <= 5:  # 只显示前5个被跳过的
                    print(f"[UrlSeedingCrawler] ✗ 跳过: {title[:40]} (自定义分数={custom_score:.2f} < 阈值{relevance_threshold})")

        # 按自定义分数排序，取top N
        high_score_urls.sort(key=lambda x: x.get("custom_score", 0), reverse=True)
        selected_urls = high_score_urls[: max_pages * 2]  # 取2倍数量，应对去重损失

        stats["after_bm25_filter"] = len(selected_urls)
        print(f"[UrlSeedingCrawler] ✓ 智能过滤后剩余: {len(selected_urls)} 个URL (总共跳过{skipped_count}个)")

        # 显示过滤后分数分布
        if selected_urls:
            top_5_scores = [x.get("custom_score", 0) for x in selected_urls[:5]]
            print(f"[UrlSeedingCrawler] 前5个URL的自定义分数: {[f'{s:.2f}' for s in top_5_scores]}")

        if not selected_urls:
            print("[UrlSeedingCrawler] 智能过滤后无剩余URL，跳过此源")
            return newly_crawled_data, stats

        print("\n[UrlSeedingCrawler] ===== 第3步：已访问URL过滤 =====")

        # 批量检查已访问URL
        all_urls = [u["url"] for u in selected_urls]
        visited_url_map = {}
        try:
            visited_url_map = NewsVisitedUrlService.batch_check_visited(tenant_id, all_urls)
        except Exception as e:
            print(f"[UrlSeedingCrawler] 警告: 批量检查URL失败: {e}")

        # 过滤掉已访问URL
        unvisited_urls = [u for u in selected_urls if not visited_url_map.get(u["url"], False)]

        stats["after_visited_filter"] = len(unvisited_urls)
        print(f"[UrlSeedingCrawler] ✓ 过滤已访问后剩余: {len(unvisited_urls)} 个URL")

        if not unvisited_urls:
            print("[UrlSeedingCrawler] 所有URL均已访问，跳过此源")
            return newly_crawled_data, stats

        # 取最终要爬取的URL数量
        urls_to_crawl = unvisited_urls[:max_pages]

        print("\n[UrlSeedingCrawler] ===== 第4步：精准爬取 =====")
        print(f"[UrlSeedingCrawler] 将爬取 {len(urls_to_crawl)} 个精选URL")

        # 爬取选中的URL
        # 配置爬虫超时时间（大规模爬取优化）
        crawler_config = CrawlerRunConfig(
            page_timeout=20000,  # 页面加载超时：20秒（适合大规模爬取）
            wait_until="domcontentloaded",  # 等待DOM加载完成即可，不等待所有资源
            verbose=False,  # 减少日志输出
        )

        async with AsyncWebCrawler() as crawler:
            for idx, url_data in enumerate(urls_to_crawl):
                url = url_data["url"]
                custom_score = url_data.get("custom_score", 0)
                matched_reasons = url_data.get("matched_reasons", [])
                head_title = url_data.get("head_data", {}).get("title", "")

                print(f"\n[UrlSeedingCrawler] [{idx + 1}/{len(urls_to_crawl)}] 爬取: {head_title[:50]}...")
                print(f"[UrlSeedingCrawler]   URL: {url}")
                print(f"[UrlSeedingCrawler]   自定义分数: {custom_score:.2f} ({', '.join(matched_reasons[:2])})")

                try:
                    result = await crawler.arun(url=url, config=crawler_config, bypass_cache=True)

                    if not result.success:
                        stats["crawled"] += 1
                        urls_to_record.append(
                            {
                                "url": url,
                                "source_id": source_id,
                                "failed": True,
                                "is_policy": False,
                                "collected": False,
                            }
                        )
                        print("[UrlSeedingCrawler]   ✗ 爬取失败")
                        continue

                    stats["crawled"] += 1

                    # 提取内容
                    content_text = self._extract_content(result)
                    if not content_text or len(content_text.strip()) < 100:
                        urls_to_record.append(
                            {
                                "url": url,
                                "source_id": source_id,
                                "failed": False,
                                "is_policy": True,
                                "collected": False,
                                "title": head_title,
                            }
                        )
                        print("[UrlSeedingCrawler]   ✗ 内容过短")
                        continue

                    # 提取标题
                    title = self._extract_title(result) or head_title

                    # 去重检查
                    content_hash = hashlib.sha256(content_text.encode("utf-8")).hexdigest()

                    # 内存去重
                    if content_hash in persistent_hashes:
                        stats["duplicate"] += 1
                        print("[UrlSeedingCrawler]   ✗ 重复内容（内存）")
                        urls_to_record.append(
                            {
                                "url": url,
                                "source_id": source_id,
                                "failed": False,
                                "is_policy": True,
                                "collected": False,
                                "title": title,
                                "page_hash": content_hash,
                            }
                        )
                        continue

                    # 数据库去重
                    try:
                        from api.db.services.news_service import NewsContentService

                        if NewsContentService.model.select().where(NewsContentService.model.original_url == url).exists():
                            stats["duplicate"] += 1
                            print("[UrlSeedingCrawler]   ✗ 重复内容（数据库）")
                            urls_to_record.append(
                                {
                                    "url": url,
                                    "source_id": source_id,
                                    "failed": False,
                                    "is_policy": True,
                                    "collected": False,
                                    "title": title,
                                    "page_hash": content_hash,
                                }
                            )
                            continue
                    except Exception as db_error:
                        print(f"[UrlSeedingCrawler]   ⚠ 数据库去重检查失败: {db_error}")

                    persistent_hashes.add(content_hash)

                    # 下载附件
                    html = getattr(result, "html", None) or ""
                    attachments = await self._download_attachments(html, url, title)

                    # 收集内容
                    article_data = {
                        "url": url,
                        "source_id": source_id,
                        "score": custom_score,  # 使用自定义评分
                        "final_score": custom_score,  # URL Seeding使用自定义评分
                        "content": content_text,
                        "content_hash": content_hash,
                        "title": title,
                        "matched_keywords": matched_reasons,  # 记录匹配原因
                        "crawl_timestamp": datetime.now().isoformat(),
                        "is_policy": True,  # URL Seeding认为所有通过过滤的都是政策相关
                        "attachments": attachments,
                        "attachment_count": len(attachments),
                    }
                    newly_crawled_data.append(article_data)
                    stats["collected"] += 1

                    # 记录成功收集的URL
                    urls_to_record.append(
                        {
                            "url": url,
                            "source_id": source_id,
                            "failed": False,
                            "is_policy": True,
                            "collected": True,
                            "title": title,
                            "page_hash": content_hash,
                        }
                    )

                    attachment_tag = f"📎{len(attachments)}" if attachments else ""
                    print(f"[UrlSeedingCrawler]   ✓ 收集成功 {attachment_tag} [已收集 {stats['collected']}/{max_pages}]")

                    # 达到目标数量，停止爬取
                    if stats["collected"] >= max_pages:
                        print(f"[UrlSeedingCrawler] ✓ 已收集到 {max_pages} 篇内容，停止爬取")
                        break

                except Exception as e:
                    print(f"[UrlSeedingCrawler]   ✗ 爬取出错: {e}")
                    urls_to_record.append(
                        {
                            "url": url,
                            "source_id": source_id,
                            "failed": True,
                            "is_policy": False,
                            "collected": False,
                        }
                    )

        # 批量记录URL访问
        if urls_to_record:
            print(f"\n[UrlSeedingCrawler] 正在记录 {len(urls_to_record)} 个URL访问记录...")
            try:
                NewsVisitedUrlService.batch_record_visits(tenant_id, urls_to_record)
                print("[UrlSeedingCrawler] ✓ URL访问记录已保存")
            except Exception as record_error:
                print(f"[UrlSeedingCrawler] 警告: URL访问记录保存失败: {record_error}")

        # 打印统计摘要
        print("\n[UrlSeedingCrawler] ===== 单源统计摘要 =====")
        print(f"[UrlSeedingCrawler] URL发现: {stats['discovered_urls']} 个")
        print(f"[UrlSeedingCrawler] BM25过滤后: {stats['after_bm25_filter']} 个")
        print(f"[UrlSeedingCrawler] 已访问过滤后: {stats['after_visited_filter']} 个")
        print(f"[UrlSeedingCrawler] 实际爬取: {stats['crawled']} 个")
        print(f"[UrlSeedingCrawler] 重复内容: {stats['duplicate']} 个")
        print(f"[UrlSeedingCrawler] 最终收集: {stats['collected']} 篇")

        return newly_crawled_data, stats

    def _extract_title(self, result) -> str:
        """从爬取结果中提取标题"""
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
                    from bs4 import BeautifulSoup

                    soup = BeautifulSoup(html, "html.parser")
                    title = soup.title.string if soup.title and soup.title.string else title
            except Exception:
                pass
        return (title or "").strip()

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

    async def _download_attachments(self, html: str, url: str, title: str) -> list:
        """下载页面的附件文件"""
        attachments = []
        if not html:
            return attachments

        try:
            found_attachments = await self.attachment_downloader.find_attachments(html, url)

            if found_attachments:
                print(f"[UrlSeedingCrawler]    📎 发现 {len(found_attachments)} 个附件")

                base_dir = "crawl4ai_data"
                safe_title = _sanitize_filename(title[:30] or "untitled")
                attachment_dir = os.path.join(base_dir, "attachments", safe_title)

                for att in found_attachments[:5]:  # 最多下载5个附件
                    download_result = await self.attachment_downloader.download_attachment(url=att["url"], save_dir=attachment_dir, filename=att["filename"])

                    if download_result["success"]:
                        attachments.append(
                            {
                                "filename": download_result["filename"],
                                "filepath": download_result["filepath"],
                                "size": download_result["size"],
                                "url": download_result["url"],
                                "extension": att["extension"],
                                "link_text": att["link_text"],
                            }
                        )
                        print(f"[UrlSeedingCrawler]       ✓ {download_result['filename']}")
                    else:
                        print(f"[UrlSeedingCrawler]       ✗ {att['filename']}")

                print(f"[UrlSeedingCrawler]    ✓ 下载 {len(attachments)}/{len(found_attachments)} 个附件")
        except Exception as e:
            print(f"[UrlSeedingCrawler]    ✗ 附件处理出错: {e}")

        return attachments

    def _save_crawl_log(self, keywords: list, total_collected: int, total_duration: float, source_stats: list):
        """保存详细的爬取日志到文件"""
        import json
        import time

        log_dir = "crawl4ai_data/logs"
        os.makedirs(log_dir, exist_ok=True)

        timestamp = int(time.time() * 1000)
        log_filename = f"url_seeding_log_{timestamp}.json"
        log_path = os.path.join(log_dir, log_filename)

        log_data = {
            "method": "url_seeding",
            "timestamp": timestamp,
            "datetime": datetime.now().isoformat(),
            "keywords": keywords,
            "total_duration_seconds": round(total_duration, 2),
            "total_collected": total_collected,
            "source_count": len(source_stats),
            "sources": source_stats,
        }

        try:
            with open(log_path, "w", encoding="utf-8") as f:
                json.dump(log_data, f, ensure_ascii=False, indent=2)
            print(f"[UrlSeedingCrawler] 日志已保存: {log_path}")
        except Exception as e:
            print(f"[UrlSeedingCrawler] 警告: 日志保存失败: {e}")


# =================================================================================
# 工具函数
# =================================================================================
def _enrich_metadata(article_data: dict, source: dict) -> dict:
    """将新闻源的结构化信息写入文章 metadata 方便后续过滤。"""
    if not isinstance(article_data, dict):
        return article_data

    metadata = article_data.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}

    source_dict = source or {}

    metadata.update(
        {
            "source_id": source_dict.get("id") or metadata.get("source_id"),
            "source_name": source_dict.get("name") or metadata.get("source_name"),
            "source_url": source_dict.get("url") or metadata.get("source_url") or article_data.get("url"),
            "source_type": source_dict.get("source_type") or metadata.get("source_type") or "news",
            "region": source_dict.get("region") or metadata.get("region"),
            "issuer": source_dict.get("issuer") or metadata.get("issuer"),
            "policy_theme": source_dict.get("policy_theme") or metadata.get("policy_theme") or [],
        }
    )

    article_data["metadata"] = metadata
    return article_data


def _sanitize_filename(name: str) -> str:
    """清理字符串，使其成为一个合法的文件名的一部分"""
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    name = re.sub(r"\s+", "_", name)
    return name[:50]


async def _upload_to_knowledgebase(kb_id: str, tenant_id: str, file_path: str, article_data: dict, parse: bool = False, document_id: str = None) -> bool:
    """上传内容到知识库 (改进版 - 支持二进制文件)"""
    try:
        _, kb = KnowledgebaseService.get_by_id(kb_id)
        if not kb:
            print(f"[知识库上传] 知识库 {kb_id} 不存在")
            return False

        doc_name = os.path.basename(file_path)
        doc_id = document_id if document_id else get_uuid()

        # 判断文件类型，决定使用文本还是二进制模式读取
        file_extension = os.path.splitext(file_path)[1].lower()
        binary_extensions = [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".zip", ".rar"]
        is_binary = file_extension in binary_extensions

        # 读取文件内容
        if is_binary:
            # 二进制模式读取
            async with aiofiles.open(file_path, "rb") as f:
                file_content_bytes = await f.read()
            file_content = None  # 二进制文件不需要文本内容
        else:
            # 文本模式读取（JSON等）
            async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
                file_content = await f.read()
            file_content_bytes = file_content.encode("utf-8")

        meta_fields = article_data.get("metadata", {}) if isinstance(article_data, dict) else {}

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

        # 根据原始文件扩展名设置文档名称
        if file_extension:
            doc_name = f"{sanitized_title}{file_extension}"
            doc_suffix = file_extension.lstrip(".")
            doc_type = doc_suffix
        else:
            doc_name = f"{sanitized_title}.json"
            doc_suffix = "json"
            doc_type = "json"

        # location 应该是相对于 bucket 的路径
        doc_id = document_id if document_id else get_uuid()
        storage_location = f"{doc_id}/{doc_name}"

        # 使用 settings.STORAGE_IMPL 进行存储
        settings.STORAGE_IMPL.put(kb_id, storage_location, file_content_bytes)

        # 如果调用方提供了 document_id,则尝试更新该 Document;
        # 否则新建 Document(保持向后兼容)
        if document_id:
            try:
                # 更新已有 Document
                DocumentService.update_by_id(
                    document_id,
                    {
                        "location": storage_location,
                        "size": len(file_content_bytes),
                        "name": doc_name,
                        "suffix": doc_suffix,
                        "type": doc_type,
                        "source_type": "local",
                        "meta_fields": meta_fields,
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
                "size": len(file_content_bytes),
                "type": doc_type,
                "suffix": doc_suffix,
                "parser_id": kb.parser_id,
                "parser_config": kb.parser_config,
                "source_type": "local",
                "created_by": tenant_id,
                "tenant_id": tenant_id,
                "meta_fields": meta_fields,
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
                "type": doc_type,
                "parser_id": kb.parser_id,
                "parser_config": kb.parser_config,
                "tenant_id": tenant_id,
                "size": len(file_content_bytes),
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
async def _async_crawl_from_post_worker(tenant_id: str, source_ids: list, depth: int, max_pages: int, kb_id: str = None, parse: bool = False, log_id: str = None):
    """基于新闻源的异步抓取任务"""
    kb_info = f", 目标知识库: {kb_id}" if kb_id else ""
    print(f"[后台任务] 开始处理 {len(source_ids)} 个新闻源... (深度: {depth}, 每源最大页数: {max_pages}{kb_info})")

    # 更新日志状态为运行中
    if log_id:
        try:
            CrawlTaskLogService.mark(log_id, "running")
        except Exception as e:
            print(f"[后台任务] 警告: 更新日志状态失败: {e}")

    try:
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
                    page_data = _enrich_metadata(page_data, source)
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
        
        # 更新日志状态为完成
        if log_id:
            try:
                CrawlTaskLogService.mark(log_id, "completed")
            except Exception as e:
                print(f"[后台任务] 警告: 更新日志完成状态失败: {e}")
    
    except Exception as e:
        print(f"[后台任务] 发生严重错误: {e}")
        traceback.print_exc()
        # 更新日志状态为失败
        if log_id:
            try:
                CrawlTaskLogService.mark(log_id, "failed", str(e))
            except Exception as mark_err:
                print(f"[后台任务] 警告: 更新日志失败状态失败: {mark_err}")


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
            tenant_id=tenant_id,  # 【新增】传递 tenant_id 用于URL去重
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
            source_stub = next((s for s in sources_from_db if s.get("id") == source_id), {})
            page_data = _enrich_metadata(page_data, source_stub)
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

                    # 上传主文档（JSON文件）
                    await _upload_to_knowledgebase(
                        kb_id=kb_id,
                        tenant_id=tenant_id,
                        file_path=output_file,
                        article_data=page_data,
                        parse=parse,
                        document_id=document_id,
                    )

                    # 上传附件
                    attachments = page_data.get("attachments", [])
                    if attachments:
                        print(f"[知识库集成] 开始上传 {len(attachments)} 个附件...")
                        for idx, attachment in enumerate(attachments):
                            try:
                                attachment_path = attachment.get("filepath")
                                if attachment_path and os.path.exists(attachment_path):
                                    # 为附件创建单独的article_data
                                    attachment_article_data = {
                                        "title": f"{page_title}_附件_{idx + 1}_{attachment.get('filename')}",
                                        "url": attachment.get("url", ""),
                                        "content": f"这是政策文档《{page_title}》的附件文件。\n\n原文链接: {page_data.get('url')}\n附件名称: {attachment.get('filename')}\n文件大小: {attachment.get('size')} bytes",
                                    }

                                    # 上传附件到知识库
                                    attachment_upload_success = await _upload_to_knowledgebase(
                                        kb_id=kb_id,
                                        tenant_id=tenant_id,
                                        file_path=attachment_path,
                                        article_data=attachment_article_data,
                                        parse=parse,
                                        document_id=None,  # 附件作为新文档
                                    )

                                    if attachment_upload_success:
                                        print(f"[知识库集成] ✓ 附件上传成功: {attachment.get('filename')}")
                                    else:
                                        print(f"[知识库集成] ✗ 附件上传失败: {attachment.get('filename')}")
                                else:
                                    print(f"[知识库集成] ✗ 附件文件不存在: {attachment_path}")

                            except Exception as att_err:
                                print(f"[知识库集成] 附件上传出错: {att_err}")

            except Exception as e:
                print(f"[数据库同步] 警告: 写入数据库失败: {e}")

        print(f"\n[主题搜索任务] 完成。共存储了 {total_saved} 篇相关内容。")

    except Exception as e:
        print(f"[主题搜索任务] 发生严重错误: {e}")
        traceback.print_exc()


def _background_crawl_from_post_wrapper(tenant_id: str, source_ids: list, depth: int, max_pages: int, kb_id: str = None, parse: bool = False, log_id: str = None):
    """同步的包装函数，在线程中启动asyncio事件循环"""
    asyncio.run(_async_crawl_from_post_worker(tenant_id, source_ids, depth, max_pages, kb_id, parse, log_id))


def _background_topic_search_wrapper(
    tenant_id: str, source_ids: list, keywords: list, max_depth: int, max_pages_per_source: int, max_crawl_pages_per_source: int, score_threshold: float, kb_id: str = None, parse: bool = False
):
    """主题搜索的同步包装函数"""
    asyncio.run(_async_topic_search_worker(tenant_id, source_ids, keywords, max_depth, max_pages_per_source, max_crawl_pages_per_source, score_threshold, kb_id, parse))


async def _async_url_seeding_search_worker(
    tenant_id: str,
    source_ids: list,
    keywords: list,
    max_pages_per_source: int,
    max_urls_per_source: int,  # 新增：每源最大URL发现数量
    relevance_threshold: float,  # 改名：相关性阈值
    kb_id: str = None,
    parse: bool = False,
):
    """URL Seeding主题搜索的异步任务

    改进点：
    - 使用AsyncUrlSeeder先发现所有URL
    - 自定义智能过滤（URL路径+关键词匹配）替代失效的BM25
    - 只爬取精选URL
    - 移除PolicyFeatureDetector，简化过滤逻辑
    """
    kb_info = f", 目标知识库: {kb_id}" if kb_id else ""
    print(f"[URL Seeding任务] 开始搜索... (关键词: {keywords}, 新闻源数: {len(source_ids)}, 每源最大收集: {max_pages_per_source}{kb_info})")

    try:
        content_hashes = NewsContentService.get_all_content_hashes(tenant_id)
        print(f"[URL Seeding任务] 成功从数据库加载 {len(content_hashes)} 个已存在的历史内容哈希。")
    except Exception as e:
        print(f"[URL Seeding任务] 警告: 从数据库加载历史哈希失败: {e}")
        content_hashes = set()

    # 从数据库加载新闻源
    sources_from_db = []
    for sid in source_ids:
        try:
            _, source_model = NewsSourceService.get_by_id(sid)
            if source_model:
                sources_from_db.append(NewsSourceService.to_dict(source_model))
            else:
                print(f"[URL Seeding任务] 警告: 未在数据库中找到 ID 为 {sid} 的新闻源。")
        except Exception as e:
            print(f"[URL Seeding任务] 错误: 查询新闻源 {sid} 时出错: {e}")

    if not sources_from_db:
        print("[URL Seeding任务] 错误: 没有有效的新闻源，任务终止。")
        return

    url_seeding_crawler = UrlSeedingCrawler()
    instant_task_id = get_uuid()

    try:
        new_articles = await url_seeding_crawler.search_by_url_seeding(
            sources=sources_from_db,
            keywords=keywords,
            tenant_id=tenant_id,
            max_pages_per_source=max_pages_per_source,
            max_urls_per_source=max_urls_per_source,  # 传递最大URL数量
            relevance_threshold=relevance_threshold,  # 使用相关性阈值
            persistent_hashes=content_hashes,
        )

        if not new_articles:
            print("[URL Seeding任务] 未发现任何相关新内容。")
            return

        print(f"[URL Seeding任务] 发现 {len(new_articles)} 篇相关内容，开始处理...")

        total_saved = 0
        for page_data in new_articles:
            content_hash = page_data.get("content_hash")
            source_id = page_data.get("source_id")
            source_stub = next((s for s in sources_from_db if s.get("id") == source_id), {})
            page_data = _enrich_metadata(page_data, source_stub)
            page_title = _sanitize_filename((page_data.get("title") or "untitled"))
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            filename = f"url_seeding_{page_title}_{timestamp}_{content_hash[:16]}.json"

            base_dir = "crawl4ai_data"
            topic_dir = _sanitize_filename("_".join(keywords[:3]))
            output_dir = os.path.join(base_dir, "url_seeding_search", topic_dir)
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

                    # 上传主文档（JSON文件）
                    await _upload_to_knowledgebase(
                        kb_id=kb_id,
                        tenant_id=tenant_id,
                        file_path=output_file,
                        article_data=page_data,
                        parse=parse,
                        document_id=document_id,
                    )

                    # 上传附件
                    attachments = page_data.get("attachments", [])
                    if attachments:
                        print(f"[知识库集成] 开始上传 {len(attachments)} 个附件...")
                        for idx, attachment in enumerate(attachments):
                            try:
                                attachment_path = attachment.get("filepath")
                                if attachment_path and os.path.exists(attachment_path):
                                    attachment_article_data = {
                                        "title": f"{page_title}_附件_{idx + 1}_{attachment.get('filename')}",
                                        "url": attachment.get("url", ""),
                                        "content": f"这是政策文档《{page_title}》的附件文件。\n\n原文链接: {page_data.get('url')}\n附件名称: {attachment.get('filename')}\n文件大小: {attachment.get('size')} bytes",
                                    }

                                    attachment_upload_success = await _upload_to_knowledgebase(
                                        kb_id=kb_id,
                                        tenant_id=tenant_id,
                                        file_path=attachment_path,
                                        article_data=attachment_article_data,
                                        parse=parse,
                                        document_id=None,
                                    )

                                    if attachment_upload_success:
                                        print(f"[知识库集成] ✓ 附件上传成功: {attachment.get('filename')}")
                                    else:
                                        print(f"[知识库集成] ✗ 附件上传失败: {attachment.get('filename')}")
                                else:
                                    print(f"[知识库集成] ✗ 附件文件不存在: {attachment_path}")

                            except Exception as att_err:
                                print(f"[知识库集成] 附件上传出错: {att_err}")

            except Exception as e:
                print(f"[数据库同步] 警告: 写入数据库失败: {e}")

        print(f"\n[URL Seeding任务] 完成。共存储了 {total_saved} 篇相关内容。")

    except Exception as e:
        print(f"[URL Seeding任务] 发生严重错误: {e}")
        traceback.print_exc()


def _background_url_seeding_search_wrapper(
    tenant_id: str,
    source_ids: list,
    keywords: list,
    max_pages_per_source: int,
    max_urls_per_source: int,  # 新增：每源最大URL发现数量
    relevance_threshold: float,  # 改名：相关性阈值
    kb_id: str = None,
    parse: bool = False,
):
    """URL Seeding搜索的同步包装函数"""
    asyncio.run(
        _async_url_seeding_search_worker(
            tenant_id,
            source_ids,
            keywords,
            max_pages_per_source,
            max_urls_per_source,  # 传递最大URL数量
            relevance_threshold,  # 传递相关性阈值
            kb_id,
            parse,
        )
    )


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
        page_size = int(request.args.get("page_size", 50))
        name = request.args.get("name")
        status = request.args.get("status")
        source_type = request.args.get("source_type")
        source_types_param = request.args.get("source_types")
        source_types = None
        if source_types_param:
            source_types = [s.strip() for s in source_types_param.split(",") if s.strip()]
        elif source_type:
            source_types = [source_type]

        sources, total = NewsSourceService.get_by_tenant_id(
            tenant_id=tenant_id, page=page, page_size=page_size, name=name, status=status, source_type=None if source_types else source_type, source_types=source_types
        )

        # 返回当前租户可用的源分组（source_type 列表），便于前端多组点选
        groups = []
        try:
            group_query = (
                NewsSourceService.model.select(NewsSourceService.model.source_type).where((NewsSourceService.model.tenant_id == tenant_id) & (NewsSourceService.model.status != "deleted")).distinct()
            )
            groups = [g.source_type for g in group_query if g.source_type]
        except Exception:
            groups = []

        return get_json_result(data={"sources": sources, "total": total, "page": page, "page_size": page_size, "groups": groups})

    except Exception as e:
        return server_error_response(e)


@manager.route("/news_collector/sources/groups", methods=["GET"])
@token_required
def list_news_source_groups(tenant_id):
    """按 source_type 分组返回源列表"""
    try:
        query = NewsSourceService.model.select().where((NewsSourceService.model.tenant_id == tenant_id) & (NewsSourceService.model.status != "deleted"))
        groups = {}
        for source in query:
            g = source.source_type or "unknown"
            groups.setdefault(g, []).append(NewsSourceService.to_dict(source))
        data = [{"group": group, "sources": items} for group, items in groups.items()]
        return get_json_result(data={"groups": data})
    except Exception as e:
        return server_error_response(e)


@manager.route("/news_collector/sources", methods=["POST"])
@token_required
async def create_news_source(tenant_id):  # <--- 修改1：添加 async
    """创建新闻源 (修复版: 适配异步框架)"""
    try:
        # 1. 强制解析 JSON (适配异步)
        # 这里的 request.get_json() 返回的是一个协程，必须 await 才能拿到真正的 dict/list
        req = await request.get_json(force=True, silent=True)  # <--- 修改2：添加 await

        # --- 调试打印 ---
        # print(f"DEBUG: 接收到的数据类型: {type(req)}")

        # 2. 空值处理
        if req is None:
            return get_json_result(code=RetCode.ARGUMENT_ERROR, message="解析失败：后端接收到的数据为None。请检查Postman Body是否为 JSON")

        # 3. 数据类型判断
        if isinstance(req, list):
            sources_data = req
        elif isinstance(req, dict):
            sources_data = [req]
        else:
            return get_json_result(code=RetCode.ARGUMENT_ERROR, message=f"请求数据格式错误。期望是数组或对象，实际接收到类型: {type(req).__name__}")

        created_sources = []
        errors = []

        # 4. 遍历处理
        for index, item in enumerate(sources_data):
            # 这里的 item 必须是字典
            if not isinstance(item, dict):
                return get_json_result(code=RetCode.ARGUMENT_ERROR, message=f"第 {index + 1} 条数据格式错误，必须是JSON对象")

            if not item.get("name"):
                return get_json_result(code=RetCode.ARGUMENT_ERROR, message=f"第 {index + 1} 条数据缺少名称(name)")
            if not item.get("url"):
                return get_json_result(code=RetCode.ARGUMENT_ERROR, message=f"第 {index + 1} 条数据缺少URL(url)")

            # 补全默认值
            if "status" not in item:
                item["status"] = "active"
            if "fetch_config" not in item:
                item["fetch_config"] = {"selector": None, "encoding": "utf-8", "timeout": 30, "headers": {}}
            if "remark" not in item:
                item["remark"] = ""
            if "source_type" not in item:
                # 数据库使用source_type字段，默认为news
                item["source_type"] = "news"

            # 调用 Service
            # 注意：如果 NewsSourceService.create_source 内部也涉及数据库异步操作，
            # 可能也需要加 await，例如: await NewsSourceService.create_source(...)
            # 但通常ORM层可能是同步的，先试着保持现状，如果报错再改。
            try:
                source = NewsSourceService.create_source(tenant_id=tenant_id, user_id=tenant_id, **item)
                created_sources.append(source)
            except Exception as inner_e:
                print(f"Error creating source {item.get('name')}: {str(inner_e)}")
                # 记录错误但不中断整个循环（可选）
                errors.append(f"'{item.get('name')}': {str(inner_e)}")

        # 如果全部失败
        if not created_sources and errors:
            return get_json_result(code=RetCode.ARGUMENT_ERROR, message=f"批量添加全部失败: {'; '.join(errors)}")

        return get_json_result(data={"sources": created_sources, "count": len(created_sources), "message": "批量添加成功" if not errors else f"部分成功，失败: {'; '.join(errors)}"})

    except Exception as e:
        import traceback

        traceback.print_exc()
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
        try:
            source = NewsSourceService.update_source(source_id=source_id, tenant_id=tenant_id, **req)
            return get_json_result(data={"source": source})
        except ValueError as ve:
            return get_json_result(code=400, message=str(ve))

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

    source_ids = req_data.get("source_ids") or []
    source_types = req_data.get("source_types") or []
    depth = int(req_data.get("depth", 2))
    max_pages_per_source = int(req_data.get("max_pages_per_source", 50))

    if isinstance(source_types, str):
        source_types = [s.strip() for s in source_types.split(",") if s.strip()]

    if not isinstance(source_ids, list):
        return get_json_result(code=400, message="'source_ids' 必须是数组。")

    if source_types:
        type_sources = NewsSourceService.get_by_types(tenant_id, source_types)
        source_ids.extend([s["id"] for s in type_sources])

    # 去重并保持顺序
    seen = set()
    resolved_source_ids = []
    for sid in source_ids:
        if sid and sid not in seen:
            seen.add(sid)
            resolved_source_ids.append(sid)

    if not resolved_source_ids:
        return get_json_result(code=400, message="请提供 source_ids 或 source_types 中至少一项有效内容。")

    try:
        thread = threading.Thread(target=_background_crawl_from_post_wrapper, args=(tenant_id, resolved_source_ids, depth, max_pages_per_source))
        thread.start()

        return get_json_result(
            data={"message": f"已成功启动后台即时抓取任务，将从数据库加载并处理 {len(resolved_source_ids)} 个新闻源。", "source_ids": resolved_source_ids, "source_types": source_types}
        )

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

    source_ids = req_data.get("source_ids") or []
    source_types = req_data.get("source_types") or []
    keywords = req_data.get("keywords")
    max_depth = int(req_data.get("max_depth", 2))
    max_pages_per_source = int(req_data.get("max_pages_per_source", 5))
    max_crawl_pages_per_source = int(req_data.get("max_crawl_pages_per_source", 100))
    score_threshold = float(req_data.get("score_threshold", 0.3))
    kb_id = req_data.get("kb_id")
    parse = req_data.get("parse", False)

    # 参数验证
    if isinstance(source_types, str):
        source_types = [s.strip() for s in source_types.split(",") if s.strip()]
    if not isinstance(source_ids, list):
        return get_json_result(code=400, message="'source_ids' 必须是数组")

    if not keywords or not isinstance(keywords, list) or len(keywords) == 0:
        return get_json_result(code=400, message="关键词列表 (keywords) 不能为空，应为非空数组")

    if source_types:
        type_sources = NewsSourceService.get_by_types(tenant_id, source_types)
        source_ids.extend([s["id"] for s in type_sources])

    seen = set()
    resolved_source_ids = []
    for sid in source_ids:
        if sid and sid not in seen:
            seen.add(sid)
            resolved_source_ids.append(sid)

    if not resolved_source_ids:
        return get_json_result(code=400, message="请提供 source_ids 或 source_types 中至少一项有效内容。")

    # 验证知识库（如果指定）
    if kb_id:
        if not KnowledgebaseService.accessible(kb_id, tenant_id):
            return get_json_result(code=403, message=f"无权访问知识库 {kb_id} 或知识库不存在。")

    try:
        thread = threading.Thread(
            target=_background_topic_search_wrapper, args=(tenant_id, resolved_source_ids, keywords, max_depth, max_pages_per_source, max_crawl_pages_per_source, score_threshold, kb_id, parse)
        )
        thread.start()

        return get_json_result(
            data={
                "message": f"已成功启动主题搜索任务，关键词: {keywords}，新闻源数: {len(resolved_source_ids)}",
                "params": {
                    "source_ids": resolved_source_ids,
                    "source_types": source_types,
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


# ========== URL Seeding智能搜索抓取 (方案A) ==========


@manager.route("/news_collector/url_seeding_search", methods=["POST"])
@token_required
async def url_seeding_search_api(tenant_id):
    """
    URL Seeding智能搜索抓取（改进版）：先发现URL，再智能过滤，后精准爬取

    改进点（相比topic_search）：
    1. 使用AsyncUrlSeeder快速发现所有URL（sitemap + Common Crawl）
    2. **自定义智能过滤**：URL路径模式匹配 + title关键词匹配
       - 原因：crawl4ai的BM25评分机制存在问题（所有URL返回相同分数0.500）
       - 改用URL路径模式（zcfg、zcwj、policy等）+ title关键词进行过滤
    3. 只爬取高分URL，避免浪费资源
    4. 超时优化：页面加载20秒，附件下载25秒（适合大规模爬取）
    5. 预期性能提升：快速URL发现 + 精准过滤 + 高效爬取

    请求体:
    {
        "source_ids": ["id1", "id2"],           // 新闻源ID列表
        "keywords": ["电力市场", "现货交易"],     // 关键词列表
        "max_pages_per_source": 30,             // 每源最大收集篇数 (可选, 默认30)
        "max_urls_per_source": 1000,            // 每源最大URL发现数量 (可选, 默认1000)
                                                // 从sitemap+CommonCrawl发现的URL总数上限
                                                // 推荐值：1000（平衡速度和覆盖度）
                                                // 更多：2000-5000（更全面但更慢）
                                                // 更少：500（更快但可能遗漏）
        "relevance_threshold": 0.3,             // 相关性阈值 (可选, 默认0.3)
                                                // 评分范围0-1.0：URL路径0.15 + 预定义词0.25 + 用户词0.6
                                                // 用户关键词权重最高（60%），优先匹配用户搜索意图
                                                // 推荐值：0.3（至少匹配URL或部分关键词）
                                                // 更严格：0.5（需要匹配用户关键词）
                                                // 更宽松：0.2（匹配部分即可）
                                                // 注：为兼容旧代码，仍支持"bm25_threshold"参数名
        "kb_id": "knowledge_base_id",           // 目标知识库ID (可选)
        "parse": false                          // 是否自动解析 (可选, 默认false)
    }

    返回:
    {
        "code": 0,
        "message": "已成功启动URL Seeding智能搜索任务...",
        "data": {
            "params": {
                "source_ids": [...],
                "keywords": [...],
                "max_pages_per_source": 30,
                "max_urls_per_source": 1000,
                "relevance_threshold": 0.3
            }
        }
    }
    """
    req_data = await request.get_json()

    source_ids = req_data.get("source_ids") or []
    source_types = req_data.get("source_types") or []
    keywords = req_data.get("keywords")
    max_pages_per_source = int(req_data.get("max_pages_per_source", 30))
    max_urls_per_source = int(req_data.get("max_urls_per_source", 1000))  # 新增：每源最大URL发现数量，默认1000

    # 兼容旧参数名（bm25_threshold）和新参数名（relevance_threshold）
    relevance_threshold = float(req_data.get("relevance_threshold") or req_data.get("bm25_threshold", 0.3))

    kb_id = req_data.get("kb_id")
    parse = req_data.get("parse", False)

    # 参数验证
    if isinstance(source_types, str):
        source_types = [s.strip() for s in source_types.split(",") if s.strip()]
    if not isinstance(source_ids, list):
        return get_json_result(code=400, message="'source_ids' 必须是数组")

    if not keywords or not isinstance(keywords, list) or len(keywords) == 0:
        return get_json_result(code=400, message="关键词列表 (keywords) 不能为空，应为非空数组")

    if source_types:
        type_sources = NewsSourceService.get_by_types(tenant_id, source_types)
        source_ids.extend([s["id"] for s in type_sources])

    seen = set()
    resolved_source_ids = []
    for sid in source_ids:
        if sid and sid not in seen:
            seen.add(sid)
            resolved_source_ids.append(sid)

    if not resolved_source_ids:
        return get_json_result(code=400, message="请提供 source_ids 或 source_types 中至少一项有效内容。")

    # 验证知识库（如果指定）
    if kb_id:
        if not KnowledgebaseService.accessible(kb_id, tenant_id):
            return get_json_result(code=403, message=f"无权访问知识库 {kb_id} 或知识库不存在。")

    try:
        thread = threading.Thread(
            target=_background_url_seeding_search_wrapper,
            args=(
                tenant_id,
                resolved_source_ids,
                keywords,
                max_pages_per_source,
                max_urls_per_source,  # 传递最大URL数量
                relevance_threshold,  # 传递相关性阈值
                kb_id,
                parse,
            ),
        )
        thread.start()

        return get_json_result(
            data={
                "message": f"已成功启动URL Seeding智能搜索任务，关键词: {keywords}，新闻源数: {len(resolved_source_ids)}",
                "params": {
                    "source_ids": resolved_source_ids,
                    "source_types": source_types,
                    "keywords": keywords,
                    "max_pages_per_source": max_pages_per_source,
                    "max_urls_per_source": max_urls_per_source,  # 返回最大URL数量
                    "relevance_threshold": relevance_threshold,  # 返回实际使用的阈值
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


# ========== 爬虫目标分组管理 ==========


@manager.route("/news_collector/target_groups", methods=["GET"])
@token_required
def list_target_groups(tenant_id):
    try:
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 50))
        status = request.args.get("status")
        groups, total = CrawlGroupService.list_by_tenant(tenant_id=tenant_id, status=status, page=page, page_size=page_size)
        return get_json_result(data={"groups": groups, "total": total, "page": page, "page_size": page_size})
    except Exception as e:
        return server_error_response(e)


@manager.route("/news_collector/target_groups", methods=["POST"])
@token_required
def create_target_group(tenant_id):
    try:
        req = request.get_json()
        name = req.get("name") if isinstance(req, dict) else None
        description = req.get("description") if isinstance(req, dict) else None
        if not name:
            return get_json_result(code=400, message="name 不能为空")
        group = CrawlGroupService.create_group(tenant_id=tenant_id, name=name, description=description)
        return get_json_result(data={"group": group})
    except Exception as e:
        return server_error_response(e)


@manager.route("/news_collector/target_groups/<group_id>", methods=["PUT"])
@token_required
def update_target_group(tenant_id, group_id):
    try:
        req = request.get_json()
        group = CrawlGroupService.update_group(tenant_id=tenant_id, group_id=group_id, **(req or {}))
        return get_json_result(data={"group": group})
    except Exception as e:
        return server_error_response(e)


@manager.route("/news_collector/target_groups/<group_id>", methods=["DELETE"])
@token_required
def delete_target_group(tenant_id, group_id):
    try:
        CrawlGroupService.soft_delete(tenant_id=tenant_id, group_id=group_id)
        return get_json_result(message="删除成功")
    except Exception as e:
        return server_error_response(e)


# ========== 爬虫目标管理 ==========


@manager.route("/news_collector/targets", methods=["GET"])
@token_required
def list_targets(tenant_id):
    try:
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 50))
        status = request.args.get("status")
        group_id = request.args.get("group_id")
        targets, total = CrawlTargetService.list_by_tenant(tenant_id=tenant_id, group_id=group_id, status=status, page=page, page_size=page_size)
        return get_json_result(data={"targets": targets, "total": total, "page": page, "page_size": page_size})
    except Exception as e:
        return server_error_response(e)


@manager.route("/news_collector/targets", methods=["POST"])
@token_required
def create_target(tenant_id):
    try:
        req = request.get_json()
        if not isinstance(req, dict):
            return get_json_result(code=400, message="请求体必须是 JSON 对象")
        name = req.get("name")
        source_id = req.get("source_id")
        if not name:
            return get_json_result(code=400, message="name 不能为空")
        if not source_id:
            return get_json_result(code=400, message="source_id 不能为空")

        target = CrawlTargetService.create_target(
            tenant_id=tenant_id,
            name=name,
            source_id=source_id,
            group_id=req.get("group_id"),
            start_url=req.get("start_url"),
            kb_id=req.get("kb_id"),
            parse=req.get("parse", False),
            max_depth=int(req.get("max_depth", 2)),
            max_pages_per_source=int(req.get("max_pages_per_source", 50)),
            max_crawl_pages_per_source=int(req.get("max_crawl_pages_per_source", 100)),
            status=req.get("status", "active"),
            remark=req.get("remark"),
        )
        return get_json_result(data={"target": target})
    except Exception as e:
        return server_error_response(e)


@manager.route("/news_collector/targets/<target_id>", methods=["PUT"])
@token_required
def update_target(tenant_id, target_id):
    try:
        req = request.get_json()
        target = CrawlTargetService.update_target(tenant_id=tenant_id, target_id=target_id, **(req or {}))
        return get_json_result(data={"target": target})
    except Exception as e:
        return server_error_response(e)


@manager.route("/news_collector/targets/<target_id>", methods=["DELETE"])
@token_required
def delete_target(tenant_id, target_id):
    try:
        CrawlTargetService.soft_delete(tenant_id=tenant_id, target_id=target_id)
        return get_json_result(message="删除成功")
    except Exception as e:
        return server_error_response(e)


@manager.route("/news_collector/targets/run", methods=["POST"])
@token_required
def run_targets(tenant_id):
    """触发选定爬虫目标的即时抓取，按目标配置启动现有爬虫流程"""
    try:
        req = request.get_json()
        target_ids = req.get("target_ids") if isinstance(req, dict) else None
        if not target_ids or not isinstance(target_ids, list):
            return get_json_result(code=400, message="target_ids 必须是非空数组")

        targets = CrawlTargetService.get_by_ids(tenant_id=tenant_id, target_ids=target_ids)
        if not targets:
            return get_json_result(code=404, message="未找到有效的爬虫目标")

        dispatched = []
        for tgt in targets:
            if tgt.get("status") == "deleted" or not tgt.get("source_id"):
                continue
            depth = int(tgt.get("max_depth", 2))
            max_pages = int(tgt.get("max_pages_per_source", 50))
            kb_id = tgt.get("kb_id")
            parse = bool(tgt.get("parse", False))

            log = CrawlTaskLogService.create_log(
                tenant_id=tenant_id,
                target_id=tgt["id"],
                status="dispatched",
                run_type="manual",
                params={"depth": depth, "max_pages_per_source": max_pages, "kb_id": kb_id, "parse": parse, "source_id": tgt.get("source_id")},
            )

            thread = threading.Thread(target=_background_crawl_from_post_wrapper, args=(tenant_id, [tgt.get("source_id")], depth, max_pages, kb_id, parse))
            thread.start()

            dispatched.append({"target_id": tgt["id"], "log_id": log.get("id"), "source_id": tgt.get("source_id")})

        if not dispatched:
            return get_json_result(code=400, message="未找到可运行的目标，可能已删除或缺少 source_id")

        return get_json_result(data={"dispatched": dispatched, "count": len(dispatched)})

    except Exception as e:
        return server_error_response(e)


# ========== 目标运行记录（task_logs） ==========


@manager.route("/news_collector/task_logs", methods=["GET"])
@token_required
def list_task_logs(tenant_id):
    """分页查看爬虫目标的运行记录，用于前端展示“最近运行/失败原因/参数快照”。"""
    try:
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 50))
        status = request.args.get("status")
        target_id = request.args.get("target_id")

        logs, total = CrawlTaskLogService.list_by_tenant(
            tenant_id=tenant_id,
            target_id=target_id,
            status=status,
            page=page,
            page_size=page_size,
        )
        return get_json_result(data={"logs": logs, "total": total, "page": page, "page_size": page_size})
    except Exception as e:
        return server_error_response(e)
