from flask import Blueprint, request, jsonify
from .schemas import NewsSource, NewsSourceCreate, NewsFetchRequest, NewsHistoryItem
from . import services, crawler
from typing import List
from api.db.db_models import APIToken
# from ragflow_sdk.client import RagflowClient  # 请确保已安装ragflow_sdk

page_name = "news_collector"
manager = Blueprint(page_name, __name__)

@manager.route('/ping', methods=['GET'])
def ping():
    return {"msg": "news_collector ok"}

@manager.route('/sources', methods=['GET'])
def get_sources():
    return jsonify([s.dict() for s in services.get_news_sources()])

@manager.route('/sources', methods=['POST'])
def add_source():
    data = request.json
    source = services.add_news_source(NewsSourceCreate(**data))
    return jsonify(source.dict())

@manager.route('/sources/<int:source_id>', methods=['DELETE'])
def delete_source(source_id):
    ok = services.delete_news_source(source_id)
    if not ok:
        return jsonify({"msg": "新闻源不存在"}), 404
    return jsonify({"msg": "删除成功"})

@manager.route('/fetch', methods=['POST'])
def fetch_news():
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

@manager.route('/history', methods=['GET'])
def get_history():
    return jsonify([h.dict() for h in services.get_news_history()]) 