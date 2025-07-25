#
#  新闻收集器API模块
#
#  提供新闻源管理、抓取任务和新闻内容的API接口
#

import json
import logging
from datetime import datetime
from flask import request
from flask_login import login_required, current_user
from api.utils.api_utils import get_json_result, get_data_error_result, validate_request
from api.db.services.knowledgebase_service import KnowledgebaseService
from api.db.services.news_service import NewsSourceService, NewsTaskService, NewsContentService
from api.db.services.news_integration_service import NewsDocumentIntegrationService
from api.db.services.user_service import UserTenantService

logger = logging.getLogger(__name__)


def get_user_tenant():
    """获取当前用户的租户信息"""
    if not current_user.is_authenticated:
        return None, None
    
    # 获取用户的租户信息
    tenant_info = UserTenantService.query(user_id=current_user.id)
    if not tenant_info:
        return current_user.id, None
    
    return current_user.id, tenant_info[0].tenant_id


@manager.route('/sources', methods=['GET'])  # noqa: F821
@login_required
def get_sources():
    """获取新闻源列表"""
    try:
        user_id, tenant_id = get_user_tenant()
        if not tenant_id:
            return get_data_error_result(message="无法获取租户信息")
        
        sources = NewsSourceService.get_by_user(user_id, tenant_id, status="active")
        sources_list = [source.to_dict() for source in sources]
        
        return get_json_result(data=sources_list)
    except Exception as e:
        logger.error(f"获取新闻源失败: {e}")
        return get_data_error_result(message="获取新闻源失败")


@manager.route('/sources', methods=['POST'])  # noqa: F821
@login_required
@validate_request("name", "url")
def create_source():
    """创建新闻源"""
    try:
        user_id, tenant_id = get_user_tenant()
        if not tenant_id:
            return get_data_error_result(message="无法获取租户信息")
        
        req = request.json
        
        source = NewsSourceService.create_source(
            name=req["name"],
            url=req["url"],
            user_id=user_id,
            tenant_id=tenant_id,
            remark=req.get("remark", ""),
            fetch_config=req.get("fetch_config", {})
        )
        
        return get_json_result(data=source.to_dict())
        
    except Exception as e:
        logger.error(f"创建新闻源失败: {e}")
        return get_data_error_result(message="创建新闻源失败")


@manager.route('/sources/<source_id>', methods=['GET'])  # noqa: F821
@login_required
def get_source(source_id):
    """获取单个新闻源"""
    try:
        user_id, tenant_id = get_user_tenant()
        if not tenant_id:
            return get_data_error_result(message="无法获取租户信息")
        
        source = NewsSourceService.get_by_id(source_id)
        if not source or source.user_id != user_id or source.tenant_id != tenant_id:
            return get_data_error_result(message="新闻源不存在")
        
        return get_json_result(data=source.to_dict())
        
    except Exception as e:
        logger.error(f"获取新闻源失败: {e}")
        return get_data_error_result(message="获取新闻源失败")


@manager.route('/sources/<source_id>', methods=['PUT'])  # noqa: F821
@login_required
def update_source(source_id):
    """更新新闻源"""
    try:
        user_id, tenant_id = get_user_tenant()
        if not tenant_id:
            return get_data_error_result(message="无法获取租户信息")
        
        # 验证新闻源是否存在且属于当前用户
        source = NewsSourceService.get_by_id(source_id)
        if not source or source.user_id != user_id or source.tenant_id != tenant_id:
            return get_data_error_result(message="新闻源不存在")
        
        req = request.json
        
        # 更新新闻源
        success = NewsSourceService.update_source(source_id, **req)
        if not success:
            return get_data_error_result(message="更新失败")
        
        # 重新获取更新后的数据
        updated_source = NewsSourceService.get_by_id(source_id)
        return get_json_result(data=updated_source.to_dict())
        
    except Exception as e:
        logger.error(f"更新新闻源失败: {e}")
        return get_data_error_result(message="更新新闻源失败")


@manager.route('/sources/<source_id>', methods=['DELETE'])  # noqa: F821
@login_required
def delete_source(source_id):
    """删除新闻源"""
    try:
        user_id, tenant_id = get_user_tenant()
        if not tenant_id:
            return get_data_error_result(message="无法获取租户信息")
        
        success = NewsSourceService.delete_source(source_id, user_id)
        if not success:
            return get_data_error_result(message="新闻源不存在或删除失败")
        
        return get_json_result(data={"message": "删除成功"})
        
    except Exception as e:
        logger.error(f"删除新闻源失败: {e}")
        return get_data_error_result(message="删除新闻源失败")


@manager.route('/tasks', methods=['GET'])  # noqa: F821
@login_required
def get_tasks():
    """获取抓取任务列表"""
    try:
        user_id, tenant_id = get_user_tenant()
        if not tenant_id:
            return get_data_error_result(message="无法获取租户信息")
        
        tasks = NewsTaskService.get_by_user(user_id, tenant_id)
        tasks_list = [task.to_dict() for task in tasks]
        
        return get_json_result(data=tasks_list)
    except Exception as e:
        logger.error(f"获取任务失败: {e}")
        return get_data_error_result(message="获取任务失败")


@manager.route('/tasks', methods=['POST'])  # noqa: F821
@login_required
@validate_request("task_name", "kb_id", "source_ids")
def create_task():
    """创建抓取任务"""
    try:
        user_id, tenant_id = get_user_tenant()
        if not tenant_id:
            return get_data_error_result(message="无法获取租户信息")
        
        req = request.json
        
        task = NewsTaskService.create_task(
            task_name=req["task_name"],
            kb_id=req["kb_id"],
            source_ids=req["source_ids"],
            user_id=user_id,
            tenant_id=tenant_id,
            auto_parse=req.get("auto_parse", True),
            max_articles_per_source=req.get("max_articles_per_source", 10)
        )
        
        return get_json_result(data=task.to_dict())
        
    except ValueError as e:
        return get_data_error_result(message=str(e))
    except Exception as e:
        logger.error(f"创建任务失败: {e}")
        return get_data_error_result(message="创建任务失败")


@manager.route('/tasks/<task_id>', methods=['GET'])  # noqa: F821
@login_required
def get_task(task_id):
    """获取单个任务"""
    try:
        user_id, tenant_id = get_user_tenant()
        if not tenant_id:
            return get_data_error_result(message="无法获取租户信息")
        
        task = NewsTaskService.get_by_id(task_id)
        if not task or task.user_id != user_id or task.tenant_id != tenant_id:
            return get_data_error_result(message="任务不存在")
        
        return get_json_result(data=task.to_dict())
        
    except Exception as e:
        logger.error(f"获取任务失败: {e}")
        return get_data_error_result(message="获取任务失败")


@manager.route('/tasks/<task_id>/execute', methods=['POST'])  # noqa: F821
@login_required
def execute_task(task_id):
    """执行抓取任务"""
    try:
        user_id, tenant_id = get_user_tenant()
        if not tenant_id:
            return get_data_error_result(message="无法获取租户信息")
        
        task = NewsTaskService.get_by_id(task_id)
        if not task or task.user_id != user_id or task.tenant_id != tenant_id:
            return get_data_error_result(message="任务不存在")
        
        if task.status == "running":
            return get_data_error_result(message="任务正在运行中")
        
        # 更新任务状态为运行中
        NewsTaskService.update_task_status(task_id, "running")
        
        # 使用集成服务执行任务
        try:
            results = NewsDocumentIntegrationService.execute_news_task_with_integration(task_id)
            
            # 重新获取更新后的任务
            updated_task = NewsTaskService.get_by_id(task_id)
            return get_json_result(data={
                "message": "任务执行成功", 
                "task": updated_task.to_dict(),
                "results": results
            })
            
        except Exception as e:
            logger.error(f"任务执行失败: {e}")
            # 执行失败，更新任务状态
            NewsTaskService.update_task_status(task_id, "failed", error_message=str(e))
            return get_data_error_result(message=f"任务执行失败: {str(e)}")
        
    except Exception as e:
        logger.error(f"执行任务失败: {e}")
        return get_data_error_result(message="执行任务失败")


@manager.route('/tasks/<task_id>/documents', methods=['GET'])  # noqa: F821
@login_required
def get_task_documents(task_id):
    """获取任务产生的文档列表"""
    try:
        user_id, tenant_id = get_user_tenant()
        if not tenant_id:
            return get_data_error_result(message="无法获取租户信息")
        
        task = NewsTaskService.get_by_id(task_id)
        if not task or task.user_id != user_id or task.tenant_id != tenant_id:
            return get_data_error_result(message="任务不存在")
        
        # 获取任务产生的文档
        documents = NewsDocumentIntegrationService.get_news_documents_by_task(task_id)
        
        return get_json_result(data={
            "task_id": task_id,
            "documents": documents,
            "total": len(documents)
        })
        
    except Exception as e:
        logger.error(f"获取任务文档失败: {e}")
        return get_data_error_result(message="获取任务文档失败")


@manager.route('/tasks/<task_id>', methods=['DELETE'])  # noqa: F821
@login_required
def delete_task(task_id):
    """删除任务"""
    try:
        user_id, tenant_id = get_user_tenant()
        if not tenant_id:
            return get_data_error_result(message="无法获取租户信息")
        
        task = NewsTaskService.get_by_id(task_id)
        if not task or task.user_id != user_id or task.tenant_id != tenant_id:
            return get_data_error_result(message="任务不存在")
        
        success = NewsTaskService.delete(task_id)
        if not success:
            return get_data_error_result(message="删除失败")
        
        return get_json_result(data={"message": "删除成功"})
        
    except Exception as e:
        logger.error(f"删除任务失败: {e}")
        return get_data_error_result(message="删除任务失败")


@manager.route('/news', methods=['GET'])  # noqa: F821
@login_required
def get_news():
    """获取新闻内容列表"""
    try:
        user_id, tenant_id = get_user_tenant()
        if not tenant_id:
            return get_data_error_result(message="无法获取租户信息")
        
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 10))
        source_id = request.args.get('source_id')
        parse_status = request.args.get('parse_status')
        
        news_list, total = NewsContentService.get_by_user(
            user_id, tenant_id, page, page_size, source_id, parse_status
        )
        
        result = {
            "data": [news.to_dict() for news in news_list],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size
        }
        
        return get_json_result(data=result)
        
    except Exception as e:
        logger.error(f"获取新闻失败: {e}")
        return get_data_error_result(message="获取新闻失败")


@manager.route('/news/<content_id>', methods=['GET'])  # noqa: F821
@login_required
def get_news_content(content_id):
    """获取单个新闻内容"""
    try:
        user_id, tenant_id = get_user_tenant()
        if not tenant_id:
            return get_data_error_result(message="无法获取租户信息")
        
        content = NewsContentService.get_by_id(content_id)
        if not content or content.user_id != user_id or content.tenant_id != tenant_id:
            return get_data_error_result(message="新闻不存在")
        
        return get_json_result(data=content.to_dict())
        
    except Exception as e:
        logger.error(f"获取新闻失败: {e}")
        return get_data_error_result(message="获取新闻失败")


@manager.route('/news/<content_id>', methods=['DELETE'])  # noqa: F821
@login_required
def delete_news_content(content_id):
    """删除新闻内容"""
    try:
        user_id, tenant_id = get_user_tenant()
        if not tenant_id:
            return get_data_error_result(message="无法获取租户信息")
        
        content = NewsContentService.get_by_id(content_id)
        if not content or content.user_id != user_id or content.tenant_id != tenant_id:
            return get_data_error_result(message="新闻不存在")
        
        success = NewsContentService.delete(content_id)
        if not success:
            return get_data_error_result(message="删除失败")
        
        return get_json_result(data={"message": "删除成功"})
        
    except Exception as e:
        logger.error(f"删除新闻失败: {e}")
        return get_data_error_result(message="删除新闻失败")


@manager.route('/statistics', methods=['GET'])  # noqa: F821
@login_required
def get_statistics():
    """获取统计信息"""
    try:
        user_id, tenant_id = get_user_tenant()
        if not tenant_id:
            return get_data_error_result(message="无法获取租户信息")
        
        # 获取新闻源统计
        sources = NewsSourceService.get_by_user(user_id, tenant_id)
        active_sources = NewsSourceService.get_by_user(user_id, tenant_id, status="active")
        
        # 获取任务统计
        tasks = NewsTaskService.get_by_user(user_id, tenant_id)
        completed_tasks = NewsTaskService.get_by_user(user_id, tenant_id, status="completed")
        running_tasks = NewsTaskService.get_by_user(user_id, tenant_id, status="running")
        
        # 获取新闻内容统计
        content_stats = NewsContentService.get_statistics(user_id, tenant_id)
        
        stats = {
            "total_sources": len(sources),
            "active_sources": len(active_sources),
            "total_tasks": len(tasks),
            "completed_tasks": len(completed_tasks),
            "running_tasks": len(running_tasks),
            **content_stats
        }
        
        return get_json_result(data=stats)
        
    except Exception as e:
        logger.error(f"获取统计失败: {e}")
        return get_data_error_result(message="获取统计失败")


@manager.route('/ping', methods=['GET'])  # noqa: F821
def ping():
    """健康检查"""
    return get_json_result(data={"message": "news_collector service is running"})
