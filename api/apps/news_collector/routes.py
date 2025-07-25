"""
新闻抓取API路由

实现完整的新闻抓取与管理API接口，使用数据库存储
"""

from flask import Blueprint, request, jsonify
from typing import Dict, Any
import asyncio
import logging
import sys
import os

# 添加项目根路径以导入news_collector模块
current_dir = os.path.dirname(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_dir)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# 使用数据库服务层
from news_collector.db_services import (
    initialize_news_manager,
    get_news_manager,
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

# 导入API服务层用于兼容性
from . import services
from .schemas import NewsSourceCreate

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


def handle_error(error: Exception, default_message: str = "操作失败") -> Dict[str, Any]:
    """统一错误处理"""
    logger.error(f"API Error: {str(error)}")
    return create_response(500, str(error) or default_message, None)


# ===== 知识库管理 =====

@news_collector_bp.route('/knowledge_bases', methods=['GET'])
def get_knowledge_bases_route():
    """获取知识库列表"""
    try:
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 20))
        keyword = request.args.get('keyword', '')
        
        knowledge_bases = get_knowledge_bases()
        
        # 简单的分页和过滤
        if keyword:
            knowledge_bases = [kb for kb in knowledge_bases 
                             if keyword.lower() in kb.get('name', '').lower()]
        
        total = len(knowledge_bases)
        start = (page - 1) * size
        end = start + size
        page_kbs = knowledge_bases[start:end]
        
        data = {
            "total": total,
            "page": page,
            "size": size,
            "list": page_kbs
        }
        
        return jsonify(create_response(data=data))
    except Exception as e:
        return jsonify(handle_error(e)), 500


@news_collector_bp.route('/knowledge_bases', methods=['POST'])
def create_knowledge_base_route():
    """创建知识库"""
    try:
        data = request.get_json()
        
        # 参数验证
        if not data.get('name'):
            return jsonify(create_response(400, "知识库名称不能为空")), 400
        
        result = create_knowledge_base(data)
        
        if result:
            return jsonify(create_response(message="创建成功", data={"id": result["id"]}))
        else:
            return jsonify(create_response(500, "创建失败")), 500
            
    except Exception as e:
        return jsonify(handle_error(e)), 500


# ===== 新闻源管理 =====

@news_collector_bp.route('/sources', methods=['GET'])
def get_news_sources_route():
    """获取新闻源列表"""
    try:
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 20))
        keyword = request.args.get('keyword', '')
        status = request.args.get('status', '')
        sort_by = request.args.get('sort_by', 'created_at')
        order = request.args.get('order', 'desc')
        
        data = services.get_news_sources_paginated(page, size, keyword, status, sort_by, order)
        return jsonify(create_response(data=data))
    except Exception as e:
        return jsonify(handle_error(e)), 500


@news_collector_bp.route('/sources/<int:source_id>', methods=['GET'])
def get_news_source_route(source_id: int):
    """获取单个新闻源详情"""
    try:
        source = get_news_source(source_id)
        if source:
            return jsonify(create_response(data=source))
        else:
            return jsonify(create_response(404, "新闻源不存在")), 404
    except Exception as e:
        return jsonify(handle_error(e)), 500


@news_collector_bp.route('/sources', methods=['POST'])
def create_news_source_route():
    """创建新闻源"""
    try:
        data = request.get_json()
        
        # 参数验证
        required_fields = ['name', 'url']
        for field in required_fields:
            if not data.get(field):
                return jsonify(create_response(400, f"{field}不能为空")), 400
        
        result = create_news_source(data)
        if result:
            return jsonify(create_response(message="创建成功", data=result))
        else:
            return jsonify(create_response(500, "创建失败")), 500
            
    except Exception as e:
        return jsonify(handle_error(e)), 500


@news_collector_bp.route('/sources/<int:source_id>', methods=['PUT'])
def update_news_source_route(source_id: int):
    """更新新闻源"""
    try:
        data = request.get_json()
        
        result = update_news_source(source_id, data)
        if result:
            return jsonify(create_response(message="更新成功", data=result))
        else:
            return jsonify(create_response(404, "新闻源不存在")), 404
            
    except Exception as e:
        return jsonify(handle_error(e)), 500


@news_collector_bp.route('/sources/<int:source_id>', methods=['DELETE'])
def delete_news_source_route(source_id: int):
    """删除新闻源"""
    try:
        success = delete_news_source(source_id)
        if success:
            return jsonify(create_response(message="删除成功"))
        else:
            return jsonify(create_response(404, "新闻源不存在")), 404
            
    except Exception as e:
        return jsonify(handle_error(e)), 500


@news_collector_bp.route('/sources/validate', methods=['POST'])
def validate_news_source():
    """验证新闻源可用性"""
    try:
        data = request.get_json()
        
        # 参数验证
        if not data.get('url'):
            return jsonify(create_response(400, "URL不能为空")), 400
        
        selector_config = data.get('selector_config', {})
        
        # 这是一个异步操作，需要特殊处理
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                services.validate_news_source(data['url'], selector_config)
            )
            
            if result.get('valid'):
                return jsonify(create_response(message="验证通过，可抓取", data=result))
            else:
                return jsonify(create_response(422, result.get('error', '验证失败'), result))
                
        finally:
            loop.close()
            
    except Exception as e:
        return jsonify(handle_error(e)), 500


# ===== 抓取任务管理 =====

@news_collector_bp.route('/tasks', methods=['GET'])
def get_news_tasks():
    """获取抓取任务列表"""
    try:
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 20))
        status = request.args.get('status', '')
        start_date = request.args.get('start_date', '')
        end_date = request.args.get('end_date', '')
        
        data = services.get_news_tasks(page, size, status, start_date, end_date)
        return jsonify(create_response(data=data))
    except Exception as e:
        return jsonify(handle_error(e)), 500


@news_collector_bp.route('/tasks/<int:task_id>', methods=['GET'])
def get_news_task(task_id: int):
    """获取单个任务详情"""
    try:
        task = services.get_news_task(task_id)
        if task:
            return jsonify(create_response(data=task))
        else:
            return jsonify(create_response(404, "任务不存在")), 404
    except Exception as e:
        return jsonify(handle_error(e)), 500


@news_collector_bp.route('/tasks', methods=['POST'])
def create_news_task():
    """创建抓取任务"""
    try:
        data = request.get_json()
        
        # 参数验证
        required_fields = ['task_name', 'kb_id', 'source_ids']
        for field in required_fields:
            if not data.get(field):
                return jsonify(create_response(400, f"{field}不能为空")), 400
        
        if not isinstance(data['source_ids'], list) or not data['source_ids']:
            return jsonify(create_response(400, "至少选择一个新闻源")), 400
        
        result = services.create_news_task(data)
        if result:
            return jsonify(create_response(message="任务创建成功", data=result))
        else:
            return jsonify(create_response(500, "创建失败")), 500
            
    except Exception as e:
        return jsonify(handle_error(e)), 500


@news_collector_bp.route('/tasks/<int:task_id>/execute', methods=['POST'])
def execute_news_task(task_id: int):
    """手动执行任务"""
    try:
        # 这是一个异步操作，需要特殊处理
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(services.execute_news_task(task_id))
            
            if result.get('status') == 'success':
                return jsonify(create_response(message="任务已开始执行", data=result))
            else:
                return jsonify(create_response(500, result.get('message', '执行失败'), result))
                
        finally:
            loop.close()
            
    except Exception as e:
        return jsonify(handle_error(e)), 500


@news_collector_bp.route('/tasks/<int:task_id>/stop', methods=['POST'])
def stop_news_task(task_id: int):
    """停止执行任务"""
    try:
        result = services.stop_news_task(task_id)
        
        if 'error' in result:
            return jsonify(create_response(500, result['error'])), 500
        else:
            return jsonify(create_response(message=result['message'], data={"task_id": task_id}))
            
    except Exception as e:
        return jsonify(handle_error(e)), 500


@news_collector_bp.route('/tasks/<int:task_id>', methods=['DELETE'])
def delete_news_task(task_id: int):
    """删除抓取任务"""
    try:
        success = services.delete_news_task(task_id)
        if success:
            return jsonify(create_response(message="删除成功"))
        else:
            return jsonify(create_response(404, "任务不存在")), 404
            
    except Exception as e:
        return jsonify(handle_error(e)), 500


# ===== 新闻内容管理 =====

@news_collector_bp.route('/news', methods=['GET'])
def get_news_contents():
    """获取新闻列表"""
    try:
        page = int(request.args.get('page', 1))
        size = int(request.args.get('size', 20))
        source_id = request.args.get('source_id')
        kb_id = request.args.get('kb_id', '')
        parse_status = request.args.get('parse_status', '')
        
        source_id = int(source_id) if source_id else None
        
        data = services.get_news_contents(page, size, source_id, kb_id, parse_status)
        return jsonify(create_response(data=data))
    except Exception as e:
        return jsonify(handle_error(e)), 500


@news_collector_bp.route('/news/<int:news_id>', methods=['GET'])
def get_news_content(news_id: int):
    """获取新闻详情"""
    try:
        news = services.get_news_content(news_id)
        if news:
            return jsonify(create_response(data=news))
        else:
            return jsonify(create_response(404, "新闻不存在")), 404
    except Exception as e:
        return jsonify(handle_error(e)), 500


@news_collector_bp.route('/news/<int:news_id>', methods=['PATCH'])
def update_news_content(news_id: int):
    """更新新闻内容（局部更新）"""
    try:
        data = request.get_json()
        
        result = services.update_news_content(news_id, data)
        if result:
            return jsonify(create_response(message="更新成功", data=result))
        else:
            return jsonify(create_response(404, "新闻不存在")), 404
            
    except Exception as e:
        return jsonify(handle_error(e)), 500


@news_collector_bp.route('/news/<int:news_id>/reparse', methods=['POST'])
def reparse_news_content(news_id: int):
    """重新解析新闻到知识库"""
    try:
        # 这是一个异步操作，需要特殊处理
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(services.reparse_news_content(news_id))
            
            if result.get('status') == 'success':
                return jsonify(create_response(message="重新解析已开始", data={"id": news_id, "status": "parsing"}))
            else:
                return jsonify(create_response(500, result.get('message', '解析失败')))
                
        finally:
            loop.close()
            
    except Exception as e:
        return jsonify(handle_error(e)), 500


@news_collector_bp.route('/news/<int:news_id>', methods=['DELETE'])
def delete_news_content(news_id: int):
    """删除新闻"""
    try:
        success = services.delete_news_content(news_id)
        if success:
            return jsonify(create_response(message="删除成功"))
        else:
            return jsonify(create_response(404, "新闻不存在")), 404
            
    except Exception as e:
        return jsonify(handle_error(e)), 500


# ===== 统计报表 =====

@news_collector_bp.route('/stats/overview', methods=['GET'])
def get_stats_overview():
    """获取统计概览"""
    try:
        data = services.get_statistics_overview()
        return jsonify(create_response(data=data))
    except Exception as e:
        return jsonify(handle_error(e)), 500


@news_collector_bp.route('/stats/timeseries', methods=['GET'])
def get_stats_timeseries():
    """获取时序统计数据"""
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        interval = request.args.get('interval', 'daily')
        
        if not start_date or not end_date:
            return jsonify(create_response(400, "开始日期和结束日期不能为空")), 400
        
        data = services.get_timeseries_statistics(start_date, end_date, interval)
        return jsonify(create_response(data=data))
    except Exception as e:
        return jsonify(handle_error(e)), 500


# ===== 兼容现有API =====

@news_collector_bp.route('/news-sources', methods=['GET'])
def get_news_sources_simple():
    """获取新闻源列表（兼容现有前端）"""
    try:
        sources = services.get_news_sources_simple()
        return jsonify([source.dict() for source in sources])
    except Exception as e:
        logger.error(f"Error getting news sources: {str(e)}")
        return jsonify([]), 500


@news_collector_bp.route('/news-sources', methods=['POST'])
def create_news_source_simple():
    """创建新闻源（兼容现有前端）"""
    try:
        data = request.get_json()
        source_data = NewsSourceCreate(**data)
        source = services.add_news_source_simple(source_data)
        
        if source:
            return jsonify(source.dict())
        else:
            return jsonify({"error": "创建失败"}), 500
            
    except Exception as e:
        logger.error(f"Error creating news source: {str(e)}")
        return jsonify({"error": str(e)}), 500


@news_collector_bp.route('/news-sources/<int:source_id>', methods=['DELETE'])
def delete_news_source_simple(source_id: int):
    """删除新闻源（兼容现有前端）"""
    try:
        success = services.delete_news_source_simple(source_id)
        if success:
            return jsonify({"message": "删除成功"})
        else:
            return jsonify({"error": "新闻源不存在"}), 404
    except Exception as e:
        logger.error(f"Error deleting news source: {str(e)}")
        return jsonify({"error": str(e)}), 500


@news_collector_bp.route('/news-history', methods=['GET'])
def get_news_history():
    """获取新闻历史记录（兼容现有前端）"""
    try:
        history = services.get_news_history_simple()
        return jsonify([item.dict() for item in history])
    except Exception as e:
        logger.error(f"Error getting news history: {str(e)}")
        return jsonify([]), 500


# ===== 健康检查 =====

@news_collector_bp.route('/health', methods=['GET'])
def health_check():
    """健康检查接口"""
    return jsonify(create_response(message="News collector service is running"))


# 错误处理
@news_collector_bp.errorhandler(404)
def not_found(error):
    return jsonify(create_response(404, "接口不存在")), 404


@news_collector_bp.errorhandler(500)
def internal_error(error):
    return jsonify(create_response(500, "服务器内部错误")), 500
