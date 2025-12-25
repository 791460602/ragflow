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
新闻收集器Web版API (精简版)

用于Web前端的登录态访问，与sdk版本保持相同的业务逻辑

功能：
1. 新闻源 CRUD 管理
2. 即时抓取（精确模式/自动模式）
3. 主题搜索抓取（关键词相关性爬取）- 基于source_ids
4. 内容哈希管理（持久化去重）
"""

from quart import request
from api.apps import login_required, current_user
from api.utils.api_utils import get_json_result, server_error_response, validate_request
from api.db.services.news_service import NewsSourceService, NewsContentService
from api.db.services.knowledgebase_service import KnowledgebaseService
from api.db.services.user_service import TenantService
import threading
import traceback


# ========== 新闻源管理 CRUD ==========


@manager.route("/sources", methods=["GET"])  # noqa: F821
@login_required
def list_news_sources():
    """获取新闻源列表"""
    try:
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 20))
        name = request.args.get("name")
        status = request.args.get("status")
        source_type = request.args.get("source_type")
        source_types_param = request.args.get("source_types")
        source_types = None
        if source_types_param:
            source_types = [s.strip() for s in source_types_param.split(',') if s.strip()]
        elif source_type:
            source_types = [source_type]

        sources, total = NewsSourceService.get_by_tenant_id(
            tenant_id=current_user.id,
            page=page,
            page_size=page_size,
            name=name,
            status=status,
            source_type=None if source_types else source_type,
            source_types=source_types
        )

        groups = []
        try:
            group_query = NewsSourceService.model.select(NewsSourceService.model.source_type).where(
                (NewsSourceService.model.tenant_id == current_user.id) &
                (NewsSourceService.model.status != 'deleted')
            ).distinct()
            groups = [g.source_type for g in group_query if g.source_type]
        except Exception:
            groups = []

        return get_json_result(data={"sources": sources, "total": total, "page": page, "page_size": page_size, "groups": groups})

    except Exception as e:
        return server_error_response(e)


@manager.route("/sources/groups", methods=["GET"])  # noqa: F821
@login_required
def list_news_source_groups():
    """按 source_type 返回分组"""
    try:
        query = NewsSourceService.model.select().where(
            (NewsSourceService.model.tenant_id == current_user.id) &
            (NewsSourceService.model.status != 'deleted')
        )
        groups = {}
        for source in query:
            g = source.source_type or 'unknown'
            groups.setdefault(g, []).append(NewsSourceService.to_dict(source))
        data = [{"group": group, "sources": items} for group, items in groups.items()]
        return get_json_result(data={"groups": data})
    except Exception as e:
        return server_error_response(e)


@manager.route("/sources", methods=["POST"])  # noqa: F821
@login_required
@validate_request("name", "url")
async def create_news_source():
    """创建新闻源"""
    try:
        req = await request.get_json()

        try:
            source = NewsSourceService.create_source(tenant_id=current_user.id, user_id=current_user.id, **req)
            return get_json_result(data={"source": source})
        except ValueError as ve:
            return get_json_result(code=400, message=str(ve))

    except Exception as e:
        return server_error_response(e)


@manager.route("/sources/<source_id>", methods=["GET"])  # noqa: F821
@login_required
def get_news_source(source_id):
    """获取单个新闻源详情"""
    try:
        _, source_model = NewsSourceService.get_by_id(source_id)

        if not source_model:
            return get_json_result(code=404, message="新闻源不存在")

        source_dict = NewsSourceService.to_dict(source_model)

        if source_dict.get("tenant_id") != current_user.id:
            return get_json_result(code=404, message="新闻源不存在或无权限访问")

        return get_json_result(data={"source": source_dict})

    except Exception as e:
        return server_error_response(e)


@manager.route("/sources/<source_id>", methods=["PUT"])  # noqa: F821
@login_required
async def update_news_source(source_id):
    """更新新闻源"""
    try:
        req = await request.get_json()
        try:
            source = NewsSourceService.update_source(source_id=source_id, tenant_id=current_user.id, **req)
            return get_json_result(data={"source": source})
        except ValueError as ve:
            return get_json_result(code=400, message=str(ve))

    except ValueError as e:
        return get_json_result(code=404, message=str(e))
    except Exception as e:
        return server_error_response(e)


@manager.route("/sources/<source_id>", methods=["DELETE"])  # noqa: F821
@login_required
def delete_news_source(source_id):
    """删除新闻源"""
    try:
        NewsSourceService.update_source(source_id=source_id, tenant_id=current_user.id, status="deleted")

        return get_json_result(message="删除成功")

    except ValueError as e:
        return get_json_result(code=404, message=str(e))
    except Exception as e:
        return server_error_response(e)


# ========== 即时抓取功能 ==========


@manager.route("/crawl_from_post", methods=["POST"])  # noqa: F821
@login_required
async def crawl_from_post_web():
    """
    即时抓取接口（Web版）
    接收一个包含新闻源ID列表、控制参数和目标知识库ID的对象，
    并为它们启动一个即时的、数据库驱动的后台抓取任务。
    """
    try:
        req_data = await request.get_json()

        source_ids = req_data.get("source_ids")
        depth = int(req_data.get("depth", 2))
        max_pages_per_source = int(req_data.get("max_pages_per_source", 50))
        kb_id = req_data.get("kb_id")
        parse = req_data.get("parse", False)

        if not isinstance(source_ids, list) or not source_ids:
            return get_json_result(code=400, message="请求体必须包含一个名为 'source_ids' 的非空数组。")

        # 验证知识库ID
        if not kb_id:
            return get_json_result(code=400, message="请选择目标知识库（kb_id 参数缺失）。")

        tenant_id = current_user.id

        if not KnowledgebaseService.accessible(kb_id, tenant_id):
            return get_json_result(code=403, message=f"无权访问知识库 {kb_id} 或知识库不存在。")

        # 导入后台任务处理函数
        from api.apps.sdk.news_collector import _background_crawl_from_post_wrapper

        # 启动后台线程
        thread = threading.Thread(target=_background_crawl_from_post_wrapper, args=(tenant_id, source_ids, depth, max_pages_per_source, kb_id, parse))
        thread.start()

        return get_json_result(data={"message": f"已成功启动后台即时抓取任务，将从数据库加载并处理 {len(source_ids)} 个新闻源，内容将上传到知识库 {kb_id}。"})

    except Exception as e:
        traceback.print_exc()
        return server_error_response(e)


# ========== 主题搜索抓取 (改进版) ==========


@manager.route("/topic_search", methods=["POST"])  # noqa: F821
@login_required
async def topic_search_web():
    """
    主题搜索抓取接口（Web版）- 改进版
    根据关键词从多个新闻源进行智能爬取，优先抓取与主题相关的内容。

    改进点：
    1. 使用 source_ids 替代 start_url
    2. 跳过低分/重复内容时继续搜索，确保收集到足够数量的新内容

    请求体:
    {
        "source_ids": ["id1", "id2"],           // 新闻源ID列表
        "keywords": ["电力市场", "现货交易"],     // 关键词列表
        "max_depth": 2,                          // 爬取深度 (可选, 默认2)
        "max_pages_per_source": 30,              // 每个源最大页面数 (可选, 默认30)
        "total_max_pages": 100,                  // 总最大页面数 (可选, 默认100)
        "score_threshold": 0.3,                  // 相关性分数阈值 (可选, 默认0.3)
        "kb_id": "knowledge_base_id",            // 目标知识库ID (可选)
        "parse": false                           // 是否自动解析 (可选, 默认false)
    }
    """
    try:
        req_data = await request.get_json()

        source_ids = req_data.get("source_ids")
        keywords = req_data.get("keywords")
        max_depth = int(req_data.get("max_depth", 2))
        max_pages_per_source = int(req_data.get("max_pages_per_source", 30))
        # 兼容前端旧字段 max_crawl_pages_per_source
        total_max_pages = int(req_data.get("total_max_pages", req_data.get("max_crawl_pages_per_source", 100)))
        score_threshold = float(req_data.get("score_threshold", 0.3))
        kb_id = req_data.get("kb_id")
        parse = req_data.get("parse", False)

        # 参数验证
        if not source_ids or not isinstance(source_ids, list) or len(source_ids) == 0:
            return get_json_result(code=400, message="新闻源ID列表 (source_ids) 不能为空，应为非空数组")

        if not keywords or not isinstance(keywords, list) or len(keywords) == 0:
            return get_json_result(code=400, message="关键词列表 (keywords) 不能为空，应为非空数组")

        tenant_id = current_user.id

        # 验证知识库（如果指定）
        if kb_id and not KnowledgebaseService.accessible(kb_id, tenant_id):
            return get_json_result(code=403, message=f"无权访问知识库 {kb_id} 或知识库不存在。")

        # 导入后台任务处理函数
        from api.apps.sdk.news_collector import _background_topic_search_wrapper

        # 启动后台线程
        thread = threading.Thread(target=_background_topic_search_wrapper, args=(tenant_id, source_ids, keywords, max_depth, max_pages_per_source, total_max_pages, score_threshold, kb_id, parse))
        thread.start()

        return get_json_result(
            data={
                "message": f"已成功启动主题搜索任务，关键词: {keywords}，新闻源数: {len(source_ids)}",
                "params": {
                    "source_ids": source_ids,
                    "keywords": keywords,
                    "max_depth": max_depth,
                    "max_pages_per_source": max_pages_per_source,
                    "total_max_pages": total_max_pages,
                    "score_threshold": score_threshold,
                    "kb_id": kb_id,
                },
            }
        )

    except Exception as e:
        traceback.print_exc()
        return server_error_response(e)


# ========== 知识库管理 ==========


@manager.route("/datasets", methods=["GET"])  # noqa: F821
@login_required
def list_datasets_web():
    """获取当前用户的知识库列表"""
    try:
        tenant_id = current_user.id
        
        # 获取用户所在的租户列表
        tenants = TenantService.get_joined_tenants_by_user_id(tenant_id)
        joined_tenant_ids = [m["tenant_id"] for m in tenants]
        
        # 获取知识库列表
        kbs, total = KnowledgebaseService.get_list(
            joined_tenant_ids=joined_tenant_ids,
            user_id=tenant_id,
            page_number=1,
            items_per_page=1000,
            orderby="create_time",
            desc=True,
            id=None,
            name=None
        )
        
        # 转换为简化格式
        datasets = []
        for kb in kbs:
            datasets.append({
                "id": kb.get("id"),
                "name": kb.get("name")
            })
        
        return get_json_result(data=datasets)
    
    except Exception as e:
        return server_error_response(e)


# ========== 内容哈希管理 ==========


@manager.route("/contents/hashes", methods=["GET"])  # noqa: F821
@login_required
def list_content_hashes_web():
    """
    获取已存储内容的哈希列表（带分页）。
    用于查看和调试持久化去重数据库。
    """
    try:
        page = int(request.args.get("page", 1))
        page_size = int(request.args.get("page_size", 20))

        records, total = NewsContentService.get_hashes_paginated(tenant_id=current_user.id, page=page, page_size=page_size)

        return get_json_result(data={"records": records, "total": total, "page": page, "page_size": page_size})

    except Exception as e:
        return server_error_response(e)


@manager.route("/contents", methods=["DELETE"])  # noqa: F821
@login_required
def delete_all_contents_web():
    """
    清除所有已存储的内容记录和哈希值。
    这是一个危险操作，用于完全重置抓取历史。
    """
    try:
        deleted_count = NewsContentService.delete_by_tenant_id(current_user.id)
        return get_json_result(message=f"成功删除 {deleted_count} 条内容记录。抓取历史已重置。")

    except Exception as e:
        return server_error_response(e)
