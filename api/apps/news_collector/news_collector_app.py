from flask import Blueprint, request, jsonify
from .schemas import NewsSource, NewsSourceCreate, NewsFetchRequest, NewsHistoryItem
from . import services, crawler
from typing import List
from api.db.db_models import APIToken

page_name = "news_collector"
manager = Blueprint(page_name, __name__)

@manager.route('/ping', methods=['GET'])
def ping():
    """健康检查"""
    return {"msg": "news_collector ok", "status": "healthy"}

# === 新闻源管理 ===

@manager.route('/sources', methods=['GET'])
def get_sources():
    """获取新闻源列表"""
    try:
        sources = services.get_news_sources()
        return jsonify([s.dict() for s in sources])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@manager.route('/sources', methods=['POST'])
def add_source():
    """添加新闻源"""
    try:
        data = request.json
        source = services.add_news_source(NewsSourceCreate(**data))
        return jsonify(source.dict()), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@manager.route('/sources/<int:source_id>', methods=['GET'])
def get_source(source_id):
    """获取单个新闻源"""
    try:
        source = services.get_news_source_by_id(source_id)
        if not source:
            return jsonify({"msg": "新闻源不存在"}), 404
        return jsonify(source.dict())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@manager.route('/sources/<int:source_id>', methods=['DELETE'])
def delete_source(source_id):
    """删除新闻源"""
    try:
        ok = services.delete_news_source(source_id)
        if not ok:
            return jsonify({"msg": "新闻源不存在"}), 404
        return jsonify({"msg": "删除成功"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# === 抓取任务管理 ===

@manager.route('/tasks', methods=['GET'])
def get_tasks():
    """获取抓取任务列表"""
    try:
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 10, type=int)
        result = services.get_tasks_list(page=page, page_size=page_size)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@manager.route('/tasks', methods=['POST'])
def create_task():
    """创建抓取任务"""
    try:
        data = request.json
        task = services.create_task_entry(data)
        return jsonify(task), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@manager.route('/tasks/<int:task_id>/execute', methods=['POST'])
def execute_task(task_id):
    """执行抓取任务"""
    try:
        result = services.execute_task_by_id(task_id)
        if result.get("success"):
            return jsonify(result)
        else:
            return jsonify(result), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# === 知识库管理 ===

@manager.route('/knowledge_bases', methods=['GET'])
def get_knowledge_bases():
    """获取知识库列表"""
    try:
        kbs = services.get_knowledge_bases_list()
        return jsonify(kbs)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@manager.route('/knowledge_bases', methods=['POST'])
def create_knowledge_base():
    """创建知识库"""
    try:
        data = request.json
        kb = services.create_knowledge_base_entry(data)
        return jsonify(kb), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# === 新闻内容管理 ===

@manager.route('/news', methods=['GET'])
def get_news():
    """获取新闻内容列表"""
    try:
        from news_collector.db_services import get_news_contents
        
        page = request.args.get('page', 1, type=int)
        page_size = request.args.get('page_size', 10, type=int)
        source_id = request.args.get('source_id', type=int)
        task_id = request.args.get('task_id', type=int)
        
        result = get_news_contents(
            page=page, 
            page_size=page_size,
            source_id=source_id,
            task_id=task_id
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@manager.route('/news/<int:content_id>', methods=['GET'])
def get_news_content(content_id):
    """获取单个新闻内容"""
    try:
        from news_collector.db_services import get_news_content
        
        content = get_news_content(content_id)
        if not content:
            return jsonify({"msg": "新闻内容不存在"}), 404
        return jsonify(content)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@manager.route('/news/<int:content_id>', methods=['DELETE'])
def delete_news_content(content_id):
    """删除新闻内容"""
    try:
        from news_collector.db_services import delete_news_content
        
        ok = delete_news_content(content_id)
        if not ok:
            return jsonify({"msg": "新闻内容不存在"}), 404
        return jsonify({"msg": "删除成功"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# === 统计信息 ===

@manager.route('/stats', methods=['GET'])
def get_statistics():
    """获取统计信息"""
    try:
        stats = services.get_system_statistics()
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@manager.route('/stats/sources/<int:source_id>', methods=['GET'])
def get_source_statistics(source_id):
    """获取特定新闻源的统计信息"""
    try:
        from news_collector.db_services import get_source_statistics
        
        stats = get_source_statistics(source_id)
        if not stats:
            return jsonify({"msg": "新闻源不存在"}), 404
        return jsonify(stats)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# === 原有的抓取功能（保持兼容性）===

@manager.route('/fetch', methods=['POST'])
def fetch_news():
    """立即抓取新闻（原有功能，保持兼容性）"""
    try:
        req = request.json
        kb_id = req.get('kb_id')
        source_ids = req.get('source_ids', [])
        
        # 1. 从header获取token
        auth_header = request.headers.get("Authorization", "")
        if not auth_header or len(auth_header.split()) < 2:
            return jsonify({"msg": "缺少API Key"}), 401
        token = auth_header.split()[1]
        
        # 2. 查表校验token
        objs = APIToken.query(token=token)
        if not objs:
            return jsonify({"msg": "API Key无效"}), 403
            
        # 3. 用token初始化SDK client
        try:
            from ragflow_sdk.client import RagflowClient
            sdk_client = RagflowClient(api_key=token)
        except ImportError:
            return jsonify({"msg": "后端未安装ragflow_sdk"}), 500
            
        # 4. 调用抓取逻辑
        results = crawler.fetch_news(source_ids, kb_id=kb_id, sdk_client=sdk_client)
        return jsonify([item.dict() for item in results])
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@manager.route('/history', methods=['GET'])
def get_history():
    """获取抓取历史"""
    try:
        history = services.get_news_history()
        return jsonify([h.dict() for h in history])
    except Exception as e:
        return jsonify({"error": str(e)}), 500 