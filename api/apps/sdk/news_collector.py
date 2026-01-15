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
from api.db.services.news_service import NewsSourceService, NewsContentService, NewsVisitedUrlService, CrawlGroupService, CrawlTargetService, CrawlTaskLogService
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
from urllib.parse import urlparse
import json
import aiofiles

# 【智能爬取】导入 BestFirst 策略和评分器

# 【URL Seeding】导入 URL 发现和配置

# =================================================================================
# 导入重构后的模块
# =================================================================================
# 爬虫类
from .crawlers import (
    LibraryCrawler,
    TopicCrawler,
    UrlSeedingCrawler,
)

# 工具类
from .utils import (
    enrich_metadata,
    sanitize_filename,
)


# =================================================================================
# 原始的类定义已经被提取到独立模块中
# LibraryCrawler → crawlers/base_crawler.py
# TopicCrawler → crawlers/topic_crawler.py (已优化: BestFirst + Streaming)
# UrlSeedingCrawler → crawlers/url_seeding_crawler.py
# ChineseContentScorer → utils/scorers.py
# PolicyFeatureDetector → utils/detectors.py
# AttachmentDownloader → utils/downloaders.py
# enrich_metadata, sanitize_filename → utils/helpers.py
# =================================================================================


# ==================================================================================
# 所有类定义已提取到独立模块（见上方导入部分）
# 本文件现在只包含辅助函数和API端点定义
# ==================================================================================


# =================================================================================
# 辅助函数（用于后台任务）
# =================================================================================
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

        sanitized_title = sanitize_filename(article_title)
        if not sanitized_title:
            sanitized_title = sanitize_filename(f"Untitled_{datetime.now().strftime('%Y%m%d%H%M%S')}")

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
                    page_data = enrich_metadata(page_data, source)
                    page_title = sanitize_filename((page_data.get("title") or "untitled"))
                    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
                    filename = f"{page_title}_{timestamp}_{content_hash[:16]}.json"

                    base_dir = "crawl4ai_data"
                    site_domain = sanitize_filename(urlparse(start_url).netloc)
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
        print(f"[主题搜索任务] 成功从数据库加载 {len(content_hashes)} 个已存在的历史内容哈希 (TenantID: {tenant_id})。")
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
            page_data = enrich_metadata(page_data, source_stub)
            page_title = sanitize_filename((page_data.get("title") or "untitled"))
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            filename = f"topic_{page_title}_{timestamp}_{content_hash[:16]}.json"

            base_dir = "crawl4ai_data"
            topic_dir = sanitize_filename("_".join(keywords[:3]))
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
            page_data = enrich_metadata(page_data, source_stub)
            page_title = sanitize_filename((page_data.get("title") or "untitled"))
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            filename = f"url_seeding_{page_title}_{timestamp}_{content_hash[:16]}.json"

            base_dir = "crawl4ai_data"
            topic_dir = sanitize_filename("_".join(keywords[:3]))
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


@manager.route("/news_collector/hashes", methods=["GET"])
@token_required
def list_all_hashes(tenant_id):
    """
    统一查询所有哈希记录（内容哈希 + URL哈希）

    参数:
        type: 哈希类型 (可选: "content", "url", "all"，默认"all")
        page: 页码（默认1）
        page_size: 每页数量（默认20）
        source_id: 源ID（仅对URL哈希有效，可选）

    返回:
    {
        "code": 0,
        "data": {
            "summary": {
                "content_total": 500,
                "url_total": 1200
            },
            "content_hashes": {
                "records": [...],
                "total": 500
            },
            "url_hashes": {
                "records": [...],
                "total": 1200
            }
        }
    }
    """
    try:
        hash_type = request.args.get("type", "all")
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 20))
        source_id = request.args.get("source_id")

        result = {}

        # 汇总统计
        if hash_type in ["all", "content"]:
            content_hashes = NewsContentService.get_all_content_hashes(tenant_id)
            result["content_total"] = len(content_hashes)

        if hash_type in ["all", "url"]:
            url_hashes = NewsVisitedUrlService.get_all_url_hashes(tenant_id)
            result["url_total"] = len(url_hashes)

        # 分页数据
        if hash_type in ["all", "content"]:
            content_records, content_total = NewsContentService.get_hashes_paginated(tenant_id=tenant_id, page=page, page_size=page_size)
            result["content_hashes"] = {"records": content_records, "total": content_total, "page": page, "page_size": page_size}

        if hash_type in ["all", "url"]:
            url_records, url_total = NewsVisitedUrlService.get_url_hashes_paginated(tenant_id=tenant_id, source_id=source_id, page=page, page_size=page_size)
            result["url_hashes"] = {"records": url_records, "total": url_total, "page": page, "page_size": page_size}

        return get_json_result(data=result)

    except Exception as e:
        return server_error_response(e)


@manager.route("/news_collector/hashes", methods=["DELETE"])
@token_required
def delete_all_hashes(tenant_id):
    """
    统一清除所有哈希记录（内容哈希 + URL哈希）

    参数:
        type: 要删除的哈希类型 (可选: "content", "url", "all"，默认"all")
        source_id: 源ID（仅对URL哈希有效，可选）

    返回:
    {
        "code": 0,
        "message": "成功删除 X 条内容记录，Y 条URL访问记录。",
        "data": {
            "deleted_content": X,
            "deleted_urls": Y
        }
    }

    用途:
    - type=content: 只清除内容去重记录
    - type=url: 只清除URL访问记录
    - type=all: 清除所有记录（完全重置）
    """
    try:
        hash_type = request.args.get("type", "all")
        source_id = request.args.get("source_id")

        deleted_content = 0
        deleted_urls = 0

        # 删除内容哈希
        if hash_type in ["all", "content"]:
            deleted_content = NewsContentService.delete_by_tenant_id(tenant_id)

        # 删除URL访问记录
        if hash_type in ["all", "url"]:
            if source_id:
                deleted_urls = NewsVisitedUrlService.clear_by_source(tenant_id, source_id)
            else:
                deleted_urls = NewsVisitedUrlService.clear_all(tenant_id)

        message_parts = []
        if deleted_content > 0:
            message_parts.append(f"删除 {deleted_content} 条内容记录")
        if deleted_urls > 0:
            if source_id:
                message_parts.append(f"删除源 {source_id} 的 {deleted_urls} 条URL访问记录")
            else:
                message_parts.append(f"删除 {deleted_urls} 条URL访问记录")

        message = "成功" + "，".join(message_parts) + "。" if message_parts else "没有记录被删除。"

        return get_json_result(message=message, data={"deleted_content": deleted_content, "deleted_urls": deleted_urls, "type": hash_type, "source_id": source_id})

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
