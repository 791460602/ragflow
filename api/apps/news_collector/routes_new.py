"""
新闻抓取API路由 - 简化版

使用数据库服务层实现完整的API接口
"""

from flask import Blueprint, request, jsonify
from typing import Dict, Any
import logging
import sys
import os

# 添加项目根路径以导入news_collector模块
current_dir = os.path.dirname(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 导入数据库服务层
from news_collector.db_services import (
    get_knowledge_bases,
    create_knowledge_base,
    get_news_sources,
    get_news_source,
    create_news_source,
    update_news_source,
    delete_news_source,
    get_news_tasks,
    get_news_task,
    create_news_task,
    update_news_task,
    delete_news_task,
    execute_news_task,
    get_news_contents,
    get_news_content,
    delete_news_content,
    get_statistics_overview,
    get_source_statistics
)

logger = logging.getLogger(__name__)

# 创建蓝图
news_collector_bp = Blueprint('news_collector', __name__, url_prefix='/api/v1/news_collector')


def create_response(code: int = 0, message: str = "success", data: Any = None) -> Dict[str, Any]:
    """创建统一的响应格式"""
    return {
        "code": code,
        "message": message,
        "data": data
    }


def handle_error(e: Exception) -> tuple:
    """统一错误处理"""
    logger.error(f"API error: {e}")
    return jsonify(create_response(code=1, message=str(e))), 500


# === 健康检查 ===

@news_collector_bp.route('/ping', methods=['GET'])
def ping():
    """健康检查"""
    return jsonify(create_response(data={"status": "healthy", "service": "news_collector"}))


# === 知识库管理 ===

@news_collector_bp.route('/knowledge_bases', methods=['GET'])
def get_knowledge_bases_list():
    """获取知识库列表"""
    try:
        knowledge_bases = get_knowledge_bases()
        return jsonify(create_response(data=knowledge_bases))
    except Exception as e:
        return handle_error(e)


@news_collector_bp.route('/knowledge_bases', methods=['POST'])
def create_knowledge_base_entry():
    """创建知识库"""
    try:
        data = request.get_json()
        if not data:
            return jsonify(create_response(code=1, message="请提供有效的JSON数据")), 400
        
        result = create_knowledge_base(data)
        return jsonify(create_response(data=result)), 201
    except Exception as e:
        return handle_error(e)


# === 新闻源管理 ===

@news_collector_bp.route('/sources', methods=['GET'])
def get_sources_list():
    """获取新闻源列表"""
    try:
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 10, type=int)
        
        data = get_news_sources(page=page, page_size=page_size)
        return jsonify(create_response(data=data))
    except Exception as e:
        return handle_error(e)


@news_collector_bp.route('/sources/<int:source_id>', methods=['GET'])
def get_source_detail(source_id):
    """获取新闻源详情"""
    try:
        source = get_news_source(source_id)
        if not source:
            return jsonify(create_response(code=1, message="新闻源不存在")), 404
        
        return jsonify(create_response(data=source))
    except Exception as e:
        return handle_error(e)


@news_collector_bp.route('/sources', methods=['POST'])
def create_source():
    """创建新闻源"""
    try:
        data = request.get_json()
        if not data:
            return jsonify(create_response(code=1, message="请提供有效的JSON数据")), 400
        
        result = create_news_source(data)
        return jsonify(create_response(data=result)), 201
    except Exception as e:
        return handle_error(e)


@news_collector_bp.route('/sources/<int:source_id>', methods=['PUT'])
def update_source(source_id):
    """更新新闻源"""
    try:
        data = request.get_json()
        if not data:
            return jsonify(create_response(code=1, message="请提供有效的JSON数据")), 400
        
        result = update_news_source(source_id, data)
        if not result:
            return jsonify(create_response(code=1, message="新闻源不存在")), 404
        
        return jsonify(create_response(data=result))
    except Exception as e:
        return handle_error(e)


@news_collector_bp.route('/sources/<int:source_id>', methods=['DELETE'])
def delete_source(source_id):
    """删除新闻源"""
    try:
        success = delete_news_source(source_id)
        if not success:
            return jsonify(create_response(code=1, message="新闻源不存在")), 404
        
        return jsonify(create_response(message="删除成功"))
    except Exception as e:
        return handle_error(e)


# === 抓取任务管理 ===

@news_collector_bp.route('/tasks', methods=['GET'])
def get_tasks_list():
    """获取抓取任务列表"""
    try:
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 10, type=int)
        
        data = get_news_tasks(page=page, page_size=page_size)
        return jsonify(create_response(data=data))
    except Exception as e:
        return handle_error(e)


@news_collector_bp.route('/tasks/<int:task_id>', methods=['GET'])
def get_task_detail(task_id):
    """获取抓取任务详情"""
    try:
        task = get_news_task(task_id)
        if not task:
            return jsonify(create_response(code=1, message="任务不存在")), 404
        
        return jsonify(create_response(data=task))
    except Exception as e:
        return handle_error(e)


@news_collector_bp.route('/tasks', methods=['POST'])
def create_task():
    """创建抓取任务"""
    try:
        data = request.get_json()
        if not data:
            return jsonify(create_response(code=1, message="请提供有效的JSON数据")), 400
        
        result = create_news_task(data)
        return jsonify(create_response(data=result)), 201
    except Exception as e:
        return handle_error(e)


@news_collector_bp.route('/tasks/<int:task_id>', methods=['PUT'])
def update_task(task_id):
    """更新抓取任务"""
    try:
        data = request.get_json()
        if not data:
            return jsonify(create_response(code=1, message="请提供有效的JSON数据")), 400
        
        result = update_news_task(task_id, data)
        if not result:
            return jsonify(create_response(code=1, message="任务不存在")), 404
        
        return jsonify(create_response(data=result))
    except Exception as e:
        return handle_error(e)


@news_collector_bp.route('/tasks/<int:task_id>/execute', methods=['POST'])
def execute_task_endpoint(task_id):
    """执行抓取任务"""
    try:
        result = execute_news_task(task_id)
        return jsonify(create_response(data=result))
    except Exception as e:
        return handle_error(e)


@news_collector_bp.route('/tasks/<int:task_id>', methods=['DELETE'])
def delete_task(task_id):
    """删除抓取任务"""
    try:
        success = delete_news_task(task_id)
        if not success:
            return jsonify(create_response(code=1, message="任务不存在")), 404
        
        return jsonify(create_response(message="删除成功"))
    except Exception as e:
        return handle_error(e)


# === 新闻内容管理 ===

@news_collector_bp.route('/news', methods=['GET'])
def get_news_list():
    """获取新闻内容列表"""
    try:
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 10, type=int)
        source_id = request.args.get('source_id', type=int)
        task_id = request.args.get('task_id', type=int)
        
        data = get_news_contents(
            page=page,
            page_size=page_size,
            source_id=source_id,
            task_id=task_id
        )
        return jsonify(create_response(data=data))
    except Exception as e:
        return handle_error(e)


@news_collector_bp.route('/news/<int:content_id>', methods=['GET'])
def get_news_detail(content_id):
    """获取新闻内容详情"""
    try:
        news = get_news_content(content_id)
        if not news:
            return jsonify(create_response(code=1, message="新闻内容不存在")), 404
        
        return jsonify(create_response(data=news))
    except Exception as e:
        return handle_error(e)


@news_collector_bp.route('/news/<int:content_id>', methods=['DELETE'])
def delete_news(content_id):
    """删除新闻内容"""
    try:
        success = delete_news_content(content_id)
        if not success:
            return jsonify(create_response(code=1, message="新闻内容不存在")), 404
        
        return jsonify(create_response(message="删除成功"))
    except Exception as e:
        return handle_error(e)


# === 统计信息 ===

@news_collector_bp.route('/statistics', methods=['GET'])
def get_statistics():
    """获取统计概览"""
    try:
        data = get_statistics_overview()
        return jsonify(create_response(data=data))
    except Exception as e:
        return handle_error(e)


@news_collector_bp.route('/statistics/sources/<int:source_id>', methods=['GET'])
def get_source_stats(source_id):
    """获取特定新闻源的统计信息"""
    try:
        data = get_source_statistics(source_id)
        if not data:
            return jsonify(create_response(code=1, message="新闻源不存在")), 404
        
        return jsonify(create_response(data=data))
    except Exception as e:
        return handle_error(e)
