# -*- coding: utf-8 -*-
"""
基础爬虫模块 - LibraryCrawler
"""

import hashlib
import json
from datetime import datetime
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler

from common.misc_utils import get_uuid


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
