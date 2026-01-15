# -*- coding: utf-8 -*-
"""
主题爬虫模块 - TopicCrawler
基于内容评分的主题搜索爬虫
"""

import asyncio
import hashlib
import json
import os
import traceback
from datetime import datetime

from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
from crawl4ai.content_scraping_strategy import LXMLWebScrapingStrategy
from crawl4ai.deep_crawling import BestFirstCrawlingStrategy
from crawl4ai.deep_crawling.scorers import KeywordRelevanceScorer
from crawl4ai.deep_crawling.filters import FilterChain, ContentTypeFilter

from ..utils import ChineseContentScorer, PolicyFeatureDetector, AttachmentDownloader, sanitize_filename


class TopicCrawler:
    """基于内容评分的主题搜索爬虫 - 优化版（Streaming）

    优化内容：
    1. 启用BestFirst + Streaming模式：边发现边爬取边处理
    2. 无需等待URL发现完成，按评分从高到低实时返回结果
    3. 每个源使用独立的浏览器配置，避免跨源的上下文冲突
    4. 改进的资源管理，确保爬虫正确关闭
    5. 集成政策文档识别功能
    6. 自动检测和下载政策附件

    性能提升：
    - 消除了URL发现阶段的等待时间
    - 高分结果优先处理，可以提前达到收集目标
    - 流式处理降低内存占用
    """

    def __init__(self):
        self.content_scorer = None
        self.policy_detector = PolicyFeatureDetector()
        self.attachment_downloader = AttachmentDownloader()

    async def search_by_topic_from_sources(
        self,
        sources: list,
        keywords: list,
        tenant_id: str,
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
        all_source_stats = []

        print("\\n[TopicCrawler] 开始多源主题搜索爬取（内容评分模式）")
        print(f"[TopicCrawler] 新闻源数量: {len(sources)}")
        print(f"[TopicCrawler] 关键词: {keywords}")
        print(f"[TopicCrawler] 每源最大收集: {max_pages_per_source}, 每源最大爬取: {max_crawl_pages_per_source}")
        print(f"[TopicCrawler] 内容评分阈值: {score_threshold}")

        # 🔧 创建通用browser_config
        browser_config = BrowserConfig(
            headless=True,
            verbose=False,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            extra_args=[
                "--disable-gpu",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-extensions",
                "--disable-images",
                "--blink-settings=imagesEnabled=false",
            ],
        )

        # 🔧 遍历所有源，为每个源创建独立的crawler实例，确保状态隔离
        for i, source in enumerate(sources):
            # 🔧 [关键修复] 强制重置 deep_crawl_active 状态
            # 防止上一轮的ContextVar cleanup失败导致本轮误判为递归调用而降级为非Streaming模式
            try:
                from crawl4ai.deep_crawling.base_strategy import deep_crawl_active

                deep_crawl_active.set(False)
            except Exception:
                pass

            source_id = source.get("id")
            source_name = source.get("name")
            start_url = source.get("url")

            if not start_url:
                continue

            print(f"\\n[TopicCrawler] === 处理源 {i + 1}/{len(sources)}: {source_name} ===")

            source_start_time = time.time()

            # 🔧 [架构改进] 使用独立的Task运行爬虫，确保ContextVar隔离
            async def _run_isolated_crawl():
                async with AsyncWebCrawler(config=browser_config) as crawler:
                    return await self._crawl_single_source(
                        start_url=start_url,
                        source_id=source_id,
                        source_name=source_name,
                        tenant_id=tenant_id,
                        keywords=keywords,
                        max_depth=max_depth,
                        max_pages=max_pages_per_source,
                        max_crawl_pages=max_crawl_pages_per_source,
                        score_threshold=score_threshold,
                        persistent_hashes=persistent_hashes,
                        crawler=crawler,
                    )

            try:
                task = asyncio.create_task(_run_isolated_crawl())
                source_articles, source_stats = await task

                source_duration = time.time() - source_start_time
                source_stats["duration_seconds"] = round(source_duration, 2)
                all_source_stats.append(source_stats)

                all_crawled_data.extend(source_articles)
                print(f"[TopicCrawler] 源 '{source_name}' 完成: 收集 {len(source_articles)} 篇，耗时 {source_duration:.1f}秒")

            except Exception as e:
                print(f"[TopicCrawler] 处理源 '{source_name}' 时发生错误: {e}")
                traceback.print_exc()

                all_source_stats.append({"source_id": source_id, "source_name": source_name, "error": str(e), "duration_seconds": round(time.time() - source_start_time, 2)})

            if i < len(sources) - 1:
                print("[TopicCrawler] 等待资源释放...")
                await asyncio.sleep(2)

        total_duration = time.time() - start_time

        self._save_crawl_log(keywords=keywords, total_collected=len(all_crawled_data), total_duration=total_duration, source_stats=all_source_stats)

        print("\\n[TopicCrawler] ========== 爬取任务完成 ==========")
        print(f"[TopicCrawler] 总耗时: {total_duration:.1f}秒")
        print(f"[TopicCrawler] 共收集: {len(all_crawled_data)} 篇政策内容")
        print("[TopicCrawler] 日志已保存至: crawl4ai_data/logs/")

        return all_crawled_data

    async def _crawl_single_source(
        self,
        start_url: str,
        source_id: str,
        source_name: str,
        tenant_id: str,
        keywords: list,
        max_depth: int,
        max_pages: int,
        max_crawl_pages: int,
        score_threshold: float,
        persistent_hashes: set,
        crawler: AsyncWebCrawler,
    ):
        """爬取单个新闻源 - Streaming优化版

        参数说明：
        - max_pages: 最终收集的政策文档数量（目标）
        - max_crawl_pages: 最多爬取多少个页面（总页面数限制）

        返回：
        - (newly_crawled_data, source_stats) 元组

        优化点：
        1. BestFirst + Streaming：边发现边爬取边处理，无需等待
        2. 结果按评分从高到低返回，优先处理高价值内容
        3. 集成URL访问记录，跳过已访问URL
        4. 批量记录URL访问
        """
        from api.db.services.news_service import NewsVisitedUrlService, NewsContentService

        stats = {
            "source_id": source_id,
            "source_name": source_name,
            "crawl4ai_returned": 0,
            "skipped_visited": 0,
            "skipped_failed": 0,
            "processed": 0,
            "policy_found": 0,
            "policy_low_score": 0,
            "policy_duplicate": 0,
            "collected": 0,
        }

        newly_crawled_data = []
        urls_to_record = []

        print(f"[TopicCrawler] 目标: 收集 {max_pages} 篇政策内容")
        print(f"[TopicCrawler] 限制: 最多爬取 {max_crawl_pages} 个页面")
        print("[TopicCrawler] 策略: BestFirst + Streaming（边发现边处理，无需等待）")
        print("[TopicCrawler] 超时设置: 10秒/页")

        # ✅ 批量预加载已访问URL（高效查重）
        print(f"[TopicCrawler] 正在批量加载已访问URL哈希 (SourceID: {source_id})...")
        visited_url_hashes = set()
        try:
            visited_url_hashes = NewsVisitedUrlService.get_visited_url_hashes_by_source(tenant_id, source_id)
            visited_stats = NewsVisitedUrlService.get_visited_count(tenant_id, source_id)
            print(f"[TopicCrawler] ✓ 已加载 {len(visited_url_hashes)} 个已访问URL哈希到内存")
            print(f"[TopicCrawler]   - 统计: 总计{visited_stats['total']}个URL (政策{visited_stats['policy']}, 已收集{visited_stats['collected']}, 失败{visited_stats['failed']})")
        except Exception as e:
            print(f"[TopicCrawler] 警告: 加载已访问URL哈希失败: {e}")

        # 关键词评分器
        keyword_scorer = KeywordRelevanceScorer(
            keywords=[
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
                "gzdt",
                "fzggdt",
                "zcjd",
                "zcwj",
                "gfxwj",
                "zfxxgk",
                "yjzj",
                "ztzl",
                "bmxx",
                "电力市场",
                "能源政策",
                "电价政策",
                "市场交易",
            ]
            + keywords,
            weight=0.3,
        )

        filter_chain = FilterChain([ContentTypeFilter(allowed_types=["text/html"])])

        # 🔧 动态计算max_pages：考虑已访问URL数量，确保能获取足够的新页面
        adjusted_max_pages = max_crawl_pages + len(visited_url_hashes) + 100
        print(f"[TopicCrawler] 动态调整crawl4ai限制: {adjusted_max_pages} 页 (目标新页面{max_crawl_pages} + 已访问{len(visited_url_hashes)} + 缓冲100)")

        config = CrawlerRunConfig(
            deep_crawl_strategy=BestFirstCrawlingStrategy(
                max_depth=max_depth,
                include_external=False,
                max_pages=adjusted_max_pages,  # 🔧 动态计算，适应已访问URL数量
                url_scorer=keyword_scorer,
                filter_chain=filter_chain,
            ),
            scraping_strategy=LXMLWebScrapingStrategy(),
            stream=True,  # ✅ 恢复Streaming模式
            verbose=True,  # 开启Verbose以便查看crawl4ai内部日志
            page_timeout=30000,
            wait_until="commit",
            delay_before_return_html=2.0,
        )

        try:
            print("[TopicCrawler] 开始智能爬取（BestFirst + Streaming）...")
            print("[TopicCrawler] 结果将按评分从高到低实时返回...")

            # ✅ 直接使用传入的crawler实例，避免创建新实例导致状态冲突
            # ✅ 调用arun并检查返回类型
            result_obj = await crawler.arun(start_url, config=config)

            # 🔧 处理crawl4ai返回类型不一致的问题
            if hasattr(result_obj, "__aiter__"):
                # Streaming模式：返回异步生成器
                print("[TopicCrawler] 检测到异步生成器，使用Streaming模式")
                results_iter = result_obj
            else:
                # 非Streaming模式：返回CrawlResultContainer，转换为异步生成器
                print("[TopicCrawler] 检测到CrawlResultContainer，转换为异步迭代器")
                print(f"[TopicCrawler] 调试: result_obj类型={type(result_obj).__name__}")
                print(f"[TopicCrawler] 调试: hasattr(results)={hasattr(result_obj, 'results')}")
                print(f"[TopicCrawler] 调试: 可迭代={hasattr(result_obj, '__iter__')}")

                async def async_wrapper():
                    # 尝试多种方式获取结果列表
                    if hasattr(result_obj, "results"):
                        results = result_obj.results
                    elif hasattr(result_obj, "__iter__") and not isinstance(result_obj, str):
                        results = list(result_obj)
                    else:
                        results = [result_obj]
                    print(f"[TopicCrawler] 调试: results数量={len(results) if hasattr(results, '__len__') else '未知'}")
                    if results and len(results) > 0:
                        first_result = results[0]
                        print(f"[TopicCrawler] 调试: 第一个结果类型={type(first_result).__name__}")
                        print(f"[TopicCrawler] 调试: 第一个结果URL={getattr(first_result, 'url', '无URL')}")
                        print(f"[TopicCrawler] 调试: 第一个结果success={getattr(first_result, 'success', '未知')}")
                    for r in results:
                        yield r

                results_iter = async_wrapper()

            # 统一使用async for处理结果
            try:
                async for result in results_iter:
                    # 达到收集目标
                    if stats["collected"] >= max_pages:
                        print(f"[TopicCrawler] ✓ 已收集到 {max_pages} 篇政策内容，停止处理")
                        break

                    url = result.url if hasattr(result, "url") else None
                    if not url:
                        continue

                    # ✅ 高效查重：在内存Set中查找（O(1)复杂度）
                    url_hash = NewsVisitedUrlService._url_hash(url)
                    if url_hash in visited_url_hashes:
                        stats["skipped_visited"] += 1
                        if stats["skipped_visited"] % 20 == 1:
                            print(f"[TopicCrawler] 跳过已访问URL (已跳过{stats['skipped_visited']}个)")
                        continue

                    stats["crawl4ai_returned"] += 1

                    # 🔧 修复：达到新页面爬取限制（只计数新页面，已访问URL不计入）
                    if stats["crawl4ai_returned"] >= max_crawl_pages:
                        print(f"[TopicCrawler] ✓ 已获取 {max_crawl_pages} 个新页面，停止爬取")
                        break

                    if not result.success:
                        stats["skipped_failed"] += 1
                        urls_to_record.append({"url": url, "source_id": source_id, "failed": True, "is_policy": False, "collected": False})
                        continue

                    stats["processed"] += 1

                    content_text = self._extract_content(result)
                    if not content_text or len(content_text.strip()) < 100:
                        urls_to_record.append({"url": url, "source_id": source_id, "failed": False, "is_policy": False, "collected": False})
                        continue

                    title = self._extract_title(result)

                    html = getattr(result, "html", None) or ""
                    policy_info = self.policy_detector.detect(html, title, content_text, url)

                    if not policy_info["is_policy"]:
                        urls_to_record.append({"url": url, "source_id": source_id, "failed": False, "is_policy": False, "collected": False, "title": title})
                        if stats["processed"] % 10 == 0:
                            print(f"[TopicCrawler] 已处理 {stats['processed']} 页 | 发现 {stats['policy_found']} 个政策 | 收集 {stats['collected']} 篇")
                        continue

                    stats["policy_found"] += 1
                    depth = result.metadata.get("depth", 0) if result.metadata else 0

                    content_score = self.content_scorer.score(content_text, title)
                    matched_keywords = self.content_scorer.get_matched_keywords(content_text + " " + title)
                    policy_score = policy_info["score"]
                    final_score = content_score * 0.7 + policy_score * 0.3  # 🔧 提高内容权重，避免收集无关政策

                    link_score = result.metadata.get("score", 0.0) if result.metadata else 0.0
                    print(
                        f"[TopicCrawler] 🏛️ 政策#{stats['policy_found']} | 深度{depth} | "
                        f"链接分{link_score:.2f} | 综合分{final_score:.2f} "
                        f"(内容{content_score:.2f}/政策{policy_score:.2f}) | {title[:30]}..."
                    )

                    if final_score < score_threshold:
                        stats["policy_low_score"] += 1
                        print("[TopicCrawler]    ⊗ 分数过低，跳过")
                        urls_to_record.append({"url": url, "source_id": source_id, "failed": False, "is_policy": True, "collected": False, "title": title})
                        continue

                    content_hash = hashlib.sha256(content_text.encode("utf-8")).hexdigest()

                    if content_hash in persistent_hashes:
                        stats["policy_duplicate"] += 1
                        print("[TopicCrawler]    ⊗ 重复内容（哈希），跳过")
                        urls_to_record.append({"url": url, "source_id": source_id, "failed": False, "is_policy": True, "collected": False, "title": title, "page_hash": content_hash})
                        continue

                    try:
                        if NewsContentService.model.select().where(NewsContentService.model.original_url == url).exists():
                            stats["policy_duplicate"] += 1
                            print("[TopicCrawler]    ⊗ URL已存在数据库，跳过")
                            urls_to_record.append({"url": url, "source_id": source_id, "failed": False, "is_policy": True, "collected": False, "title": title, "page_hash": content_hash})
                            continue
                    except Exception as db_error:
                        print(f"[TopicCrawler]    ⚠ 数据库去重检查失败: {db_error}")

                    persistent_hashes.add(content_hash)

                    attachments = await self._download_attachments(html, url, title)

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

                    urls_to_record.append({"url": url, "source_id": source_id, "failed": False, "is_policy": True, "collected": True, "title": title, "page_hash": content_hash})

                    attachment_tag = f"📎{len(attachments)}" if attachments else ""
                    print(f"[TopicCrawler]    ✓ 收集成功 {attachment_tag} [已收集 {stats['collected']}/{max_pages}]")

            except Exception:
                raise
        except Exception as e:
            error_str = str(e)
            if "was created in a different Context" in error_str:
                print("[TopicCrawler] 忽略ContextVar错误（crawl4ai已知问题）")
            elif "Target page, context or browser has been closed" in error_str:
                print("[TopicCrawler] 浏览器已关闭，停止当前源爬取")
            elif "net::ERR_ABORTED" in error_str:
                print("[TopicCrawler] 页面请求被中断")
            else:
                print(f"[TopicCrawler] 源爬取错误: {e}")
                traceback.print_exc()

        await asyncio.sleep(0.5)

        if urls_to_record:
            print(f"[TopicCrawler] 正在记录 {len(urls_to_record)} 个URL访问记录...")
            try:
                NewsVisitedUrlService.batch_record_visits(tenant_id, urls_to_record)
                print("[TopicCrawler] URL访问记录已保存")
            except Exception as record_error:
                print(f"[TopicCrawler] 警告: URL访问记录保存失败: {record_error}")

        print("\\n[TopicCrawler] ===== 单源统计摘要 =====")
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
                print(f"[TopicCrawler]    📎 发现 {len(found_attachments)} 个附件")

                base_dir = "crawl4ai_data"
                safe_title = sanitize_filename(title[:30] or "untitled")
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
        log_dir = "crawl4ai_data/logs"
        os.makedirs(log_dir, exist_ok=True)

        timestamp = int(datetime.now().timestamp() * 1000)
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
