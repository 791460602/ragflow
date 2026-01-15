# -*- coding: utf-8 -*-
"""
URL Seeding爬虫模块 - UrlSeedingCrawler
"""

import asyncio
import hashlib
import json
import os
import traceback
from datetime import datetime

from bs4 import BeautifulSoup
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig, AsyncUrlSeeder, SeedingConfig

from ..utils import AttachmentDownloader, sanitize_filename


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

        # 从完整URL中提取域名（AsyncUrlSeeder需要域名，不是完整URL）
        from urllib.parse import urlparse

        parsed = urlparse(start_url)
        domain = parsed.netloc or parsed.path  # 如果是相对URL，使用path
        if not domain:
            print(f"[UrlSeedingCrawler] ✗ 无法从 {start_url} 提取域名")
            return newly_crawled_data, stats

        print(f"[UrlSeedingCrawler] 源URL: {start_url}")
        print(f"[UrlSeedingCrawler] 提取域名: {domain}")

        try:
            # 使用AsyncUrlSeeder发现URL
            async with AsyncUrlSeeder() as seeder:
                # 策略1：sitemap+cc（推荐，覆盖最全）
                config = SeedingConfig(
                    source="sitemap+cc",  # sitemap + Common Crawl
                    extract_head=True,  # 提取head元数据（title, description）- 用于后续自定义评分
                    max_urls=max_urls,  # 每源最多发现的URL数量（用户可配置）
                    concurrency=10,  # 并发worker数量
                    filter_nonsense_urls=True,  # 过滤无用URL（robots.txt、sitemap.xml等）
                    verbose=False,  # 不显示详细日志
                )

                print(f"[UrlSeedingCrawler] 正在从 {domain} 发现URL（策略: sitemap+CommonCrawl）...")
                discovered = await seeder.urls(domain, config)

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
                        max_urls=max_urls,
                        filter_nonsense_urls=True,
                    )
                    try:
                        discovered_cc = await seeder.urls(domain, config_cc)
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
                            max_urls=max_urls,
                            filter_nonsense_urls=True,
                        )
                        try:
                            discovered_sitemap = await seeder.urls(domain, config_sitemap)
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

        # ✅ 批量预加载已访问URL哈希（更高效）
        visited_url_hashes = set()
        try:
            visited_url_hashes = NewsVisitedUrlService.get_visited_url_hashes_by_source(tenant_id, source_id)
            print(f"[UrlSeedingCrawler] ✓ 已加载 {len(visited_url_hashes)} 个已访问URL哈希")
        except Exception as e:
            print(f"[UrlSeedingCrawler] 警告: 加载URL哈希失败: {e}")

        # 过滤掉已访问URL（在内存中查找）
        unvisited_urls = []
        for u in selected_urls:
            url_hash = NewsVisitedUrlService._url_hash(u["url"])
            if url_hash not in visited_url_hashes:
                unvisited_urls.append(u)

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
                        print(f"[UrlSeedingCrawler]       ✓ {download_result['filename']}")
                    else:
                        print(f"[UrlSeedingCrawler]       ✗ {att['filename']}")

                print(f"[UrlSeedingCrawler]    ✓ 下载 {len(attachments)}/{len(found_attachments)} 个附件")
        except Exception as e:
            print(f"[UrlSeedingCrawler]    ✗ 附件处理出错: {e}")

        return attachments

    def _save_crawl_log(self, keywords: list, total_collected: int, total_duration: float, source_stats: list):
        """保存详细的爬取日志到文件"""
        log_dir = "crawl4ai_data/logs"
        os.makedirs(log_dir, exist_ok=True)

        timestamp = int(datetime.now().timestamp() * 1000)
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
