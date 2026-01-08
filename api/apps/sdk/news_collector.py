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
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=60)) as response:
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
                        "--disable-images",  # 【新增】禁用图片加载，加快速度
                        "--blink-settings=imagesEnabled=false",  # 【新增】彻底禁用图片
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
        """爬取单个新闻源 - 专注政策文档（简化版）

        参数说明：
        - max_pages: 最终收集的政策文档数量（目标）
        - max_crawl_pages: 最多爬取多少个页面（总页面数限制）

        简化后的工作流程：
        1. 爬取最多 max_crawl_pages 个页面
        2. 对每个页面检测是否为政策，筛选出政策页面
        3. 政策页面中符合分数要求的才收集
        4. 停止条件：收集到 max_pages 篇 或 爬取了 max_crawl_pages 个页面
        """
        newly_crawled_data = []
        visited_urls = set()
        pages_processed = 0  # 总页面计数（包括政策和非政策）
        policy_pages_found = 0  # 政策页面计数（仅用于日志）
        link_scores_sum = 0.0  # 用于计算平均链接分
        link_scores_count = 0  # 参与计算的链接数
        enable_link_score_filter = True  # 是否启用链接分过滤
        failed_pages = 0  # 【新增】失败页面计数（超时、网络错误等）

        print(f"[TopicCrawler] 目标: 收集 {max_pages} 篇政策内容")
        print(f"[TopicCrawler] 限制: 最多爬取 {max_crawl_pages} 个页面")
        print("[TopicCrawler] 策略: 智能BestFirst（优先爬取政策相关链接）")
        print("[TopicCrawler] 超时设置: 8秒/页")

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
                # 英文关键词（政府网站URL可能包含）
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
                "drc",  # 拼音缩写
                "news",
                "xw",
                "dt",
                "zwgk",  # 新闻、动态、政务公开
                # 【新增】地方政府网站常见URL模式
                "gzdt",
                "fzggdt",
                "zcjd",
                "zcwj",
                "gfxwj",  # 工作动态、政策解读、政策文件
                "zfxxgk",
                "yjzj",
                "ztzl",
                "bmxx",  # 政府信息公开、预警专栏、专题专栏
                # 组合关键词
                "电力市场",
                "能源政策",
                "电价政策",
                "市场交易",
            ]
            + keywords,  # 加上用户提供的搜索关键词
            weight=0.3,  # 关键词权重（0.0-1.0），越高越重要
        )

        # 2. 内容相关性过滤器：过滤无关链接
        # relevance_filter = ContentRelevanceFilter(
        #     query=" ".join(keywords) + " 电力能源政策文件通知",  # 查询文本
        #     threshold=0.5,  # 相关度阈值（0.0-1.0），低于此值的链接会被过滤
        # )

        # 3. URL模式过滤器：使用通配符匹配政策相关URL
        # url_filter = URLPatternFilter(
        #     patterns=[
        #         "*policy*",
        #         "*zc*",
        #         "*wj*",
        #         "*tz*",
        #         "*gg*",  # 政策、文件、通知、公告拼音
        #         "*fgw*",
        #         "*nyj*",
        #         "*drc*",  # 发改委、能源局、发改委拼音
        #         "*news*",
        #         "*xw*",
        #         "*dt*",  # 新闻、动态
        #         "*/20[2-9][0-9]/*",  # 日期路径（2020-2099）
        #         "*/c_[0-9]*",  # 常见政府网站文章格式
        #     ]
        # )

        # 4. 组合过滤器
        filter_chain = FilterChain(
            [
                ContentTypeFilter(allowed_types=["text/html"]),  # 只爬HTML页面
                # relevance_filter,  # 暂时注释，避免过度过滤
                # url_filter,        # 暂时注释，观察效果
            ]
        )

        # 5. 配置 BestFirst 策略
        config = CrawlerRunConfig(
            deep_crawl_strategy=BestFirstCrawlingStrategy(
                max_depth=max_depth,
                include_external=False,  # 只爬取同域名链接
                max_pages=max_crawl_pages,  # 限制总页面数
                url_scorer=keyword_scorer,  # 使用关键词评分器
                filter_chain=filter_chain,  # 应用过滤链
            ),
            scraping_strategy=LXMLWebScrapingStrategy(),
            stream=False,  # 改回批量模式，stream 模式太不稳定
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
                    print(f"[TopicCrawler] 爬取完成，获得 {len(results_list)} 个页面（已按链接评分排序）")
                elif hasattr(crawl_result, "results") and crawl_result.results:
                    results_list = crawl_result.results
                    print(f"[TopicCrawler] 爬取完成，获得 {len(results_list)} 个页面")
                else:
                    print("[TopicCrawler] 警告：未获取到结果")
                    results_list = []

                # 遍历所有结果（已按BestFirst评分排序）
                for result in results_list:
                    # 停止条件1：已收集到足够的政策内容
                    if len(newly_crawled_data) >= max_pages:
                        print(f"[TopicCrawler] ✓ 已收集到 {max_pages} 篇政策内容，停止爬取")
                        break

                    # 停止条件2：已爬取足够多的页面
                    if pages_processed >= max_crawl_pages:
                        print(f"[TopicCrawler] ✓ 已处理 {max_crawl_pages} 个页面（政策: {policy_pages_found}, 收集: {len(newly_crawled_data)}），停止爬取")
                        break

                    pages_processed += 1

                    if not result.success:
                        failed_pages += 1
                        # 【新增】记录失败原因（仅前10个失败页面输出详细信息）
                        if failed_pages <= 10:
                            error_msg = getattr(result, "error_message", "Unknown error")
                            print(f"[TopicCrawler] ✗ 页面失败 #{failed_pages}: {result.url[:80]}...")
                            if "Timeout" in str(error_msg) or "timeout" in str(error_msg):
                                print("[TopicCrawler]    原因: 页面加载超时（已忽略）")
                            elif error_msg:
                                print(f"[TopicCrawler]    原因: {str(error_msg)[:100]}")
                        elif failed_pages % 10 == 0:
                            print(f"[TopicCrawler] 已跳过 {failed_pages} 个失败页面")
                        continue

                    url = result.url
                    if url in visited_urls:
                        continue
                    visited_urls.add(url)

                    # 获取链接评分（BestFirst策略会给每个结果打分）
                    link_score = result.metadata.get("score", 0.0) if result.metadata else 0.0

                    # 统计链接分用于诊断
                    link_scores_sum += link_score
                    link_scores_count += 1

                    # 【提前提取title和content】供后续debug和过滤使用
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

                    # 【调试】查看实际的链接和评分信息（仅前5个页面）
                    if pages_processed <= 5:
                        print(f"[DEBUG] 页面 {pages_processed}:")
                        print(f"  URL: {url}")
                        print(f"  Title: {title[:50] if title else 'None'}")
                        print(f"  链接分: {link_score:.3f}")
                        # 查看是否有其他评分相关信息
                        if result.metadata:
                            print(f"  Depth: {result.metadata.get('depth', '?')}")
                            print(f"  Parent URL: {result.metadata.get('parent_url', 'None')}")
                            # 【新增】查看anchor_text和其他可能影响评分的信息
                            anchor_text = result.metadata.get("anchor_text", "")
                            print(f"  Anchor Text: {anchor_text[:50] if anchor_text else 'None'}")
                            # 显示所有metadata keys以便诊断
                            print(f"  Metadata Keys: {list(result.metadata.keys())}")

                    # 【诊断】检查KeywordRelevanceScorer是否工作
                    if pages_processed == 20:
                        avg_link_score = link_scores_sum / link_scores_count if link_scores_count > 0 else 0.0
                        print("\n[TopicCrawler] ⚠️  链接评分诊断（前20页）：")
                        print(f"  平均链接分: {avg_link_score:.4f}")
                        if avg_link_score < 0.01:
                            print("  警告：链接分过低！KeywordRelevanceScorer可能未生效")
                            print("  可能原因：")
                            print("    1. 政府网站URL为编码ID，不包含关键词")
                            print("    2. Anchor text为通用文本（'更多'、'详情'等）")
                            print("    3. 中文关键词支持问题")
                            print("  当前策略：禁用链接分过滤，完全依赖PolicyFeatureDetector\n")
                            enable_link_score_filter = False  # 禁用链接分过滤

                    # 【关键过滤】链接分过低的页面直接跳过（节省资源）
                    # 注意：如果诊断发现链接分无效，此过滤器会被禁用
                    if enable_link_score_filter:
                        MIN_LINK_SCORE = 0.05  # 降低阈值，避免过滤所有内容
                        if link_score > 0 and link_score < MIN_LINK_SCORE and pages_processed > 1:  # 首页除外
                            if pages_processed % 10 == 0:
                                print(f"[TopicCrawler] 跳过低分链接 (链接分{link_score:.2f}) | 已处理 {pages_processed} 页")
                            continue

                    if not content_text or len(content_text.strip()) < 100:
                        continue

                    # ===== 【关键1】先检测是否为政策文档 =====
                    html = getattr(result, "html", None) or ""
                    policy_info = self.policy_detector.detect(html, title, content_text, url)

                    # 如果不是政策文档，直接跳过
                    if not policy_info["is_policy"]:
                        if pages_processed % 10 == 0:  # 每10个页面输出一次，避免日志过多
                            print(f"[TopicCrawler] 已处理 {pages_processed} 页 | 发现 {policy_pages_found} 个政策页面 | 收集 {len(newly_crawled_data)} 篇")
                        continue

                    # ===== 【关键2】这是政策页面，计数+1 =====
                    policy_pages_found += 1
                    depth = result.metadata.get("depth", 0) if result.metadata else 0

                    # 计算内容相关性和综合分数
                    content_score = self.content_scorer.score(content_text, title)
                    matched_keywords = self.content_scorer.get_matched_keywords(content_text + " " + title)
                    policy_score = policy_info["score"]
                    final_score = content_score * 0.5 + policy_score * 0.5

                    # 显示详细评分（包括BestFirst的链接评分）
                    print(
                        f"[TopicCrawler] 🏛️ 政策#{policy_pages_found} | 深度{depth} | 链接分{link_score:.2f} | 综合分{final_score:.2f} (内容{content_score:.2f}/政策{policy_score:.2f}) | {title[:30]}..."
                    )

                    # 检查分数是否达标
                    if final_score < score_threshold:
                        print("[TopicCrawler]    ⊗ 分数过低，跳过")
                        continue

                    # ===== 【关键3】去重检查（内容哈希 + 数据库URL）=====
                    # 3.1 内存去重：基于内容哈希
                    content_hash = hashlib.sha256(content_text.encode("utf-8")).hexdigest()
                    if content_hash in persistent_hashes:
                        print("[TopicCrawler]    ⊗ 重复内容（哈希），跳过")
                        continue

                    # 3.2 数据库去重：基于URL（避免重复收集已入库的内容）
                    try:
                        from api.db.services.news_service import NewsContentService

                        if NewsContentService.model.select().where(NewsContentService.model.original_url == url).exists():
                            print("[TopicCrawler]    ⊗ URL已存在数据库，跳过")
                            continue
                    except Exception as db_check_error:
                        # 数据库检查失败不影响爬取，继续处理
                        print(f"[TopicCrawler]    ⚠ 数据库去重检查失败: {db_check_error}")

                    persistent_hashes.add(content_hash)

                    # 查找并下载附件
                    attachments = []
                    if html:
                        try:
                            found_attachments = await self.attachment_downloader.find_attachments(html, url)

                            if found_attachments:
                                print(f"[TopicCrawler]    📎 发现 {len(found_attachments)} 个附件")

                                base_dir = "crawl4ai_data"
                                safe_title = _sanitize_filename(title[:30] or "untitled")
                                attachment_dir = os.path.join(base_dir, "attachments", safe_title)

                                for att in found_attachments[:5]:
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
                        "is_policy": True,  # 这里一定是政策
                        "policy_score": policy_score,
                        "policy_features": policy_info["features"],
                        "attachments": attachments,
                        "attachment_count": len(attachments),
                    }
                    newly_crawled_data.append(article_data)

                    attachment_tag = f"📎{len(attachments)}" if attachments else ""
                    print(f"[TopicCrawler]    ✓ 收集成功 {attachment_tag} [已收集 {len(newly_crawled_data)}/{max_pages}]")

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

        print(f"[TopicCrawler] 单源完成: 处理 {pages_processed} 页, 发现 {policy_pages_found} 个政策页面, 收集 {len(newly_crawled_data)} 篇")
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
            if "type" not in item:
                # 根据你的数据库模型，type 不能为空
                return get_json_result(code=RetCode.ARGUMENT_ERROR, message=f"第 {index + 1} 条数据缺少类型(type)")

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
