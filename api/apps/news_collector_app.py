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
新闻收集器Web版API

用于Web前端的登录态访问，与sdk版本保持相同的业务逻辑
"""

from flask import request
from flask_login import login_required, current_user
from api.utils.api_utils import get_json_result, server_error_response, validate_request
from api.db.services.news_service import NewsSourceService, NewsTaskService, NewsContentService
from api.db.services.knowledgebase_service import KnowledgebaseService
from api.utils import get_uuid
from datetime import datetime, timedelta

# ========== 新闻源管理 CRUD ==========

@manager.route('/sources', methods=['GET'])  # noqa: F821
@login_required
def list_news_sources():
    """获取新闻源列表"""
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))
        name = request.args.get('name')
        status = request.args.get('status')

        sources, total = NewsSourceService.get_by_tenant_id(
            tenant_id=current_user.id, 
            page=page, 
            page_size=page_size, 
            name=name, 
            status=status
        )
        
        return get_json_result(data={
            'sources': sources,
            'total': total,
            'page': page,
            'page_size': page_size
        })

    except Exception as e:
        return server_error_response(e)


@manager.route('/sources', methods=['POST'])  # noqa: F821
@login_required
@validate_request('name', 'url')
def create_news_source():
    """创建新闻源"""
    try:
        req = request.json

        source = NewsSourceService.create_source(
            tenant_id=current_user.id,
            user_id=current_user.id,
            **req
        )
        
        return get_json_result(data={'source': source})

    except Exception as e:
        return server_error_response(e)


@manager.route('/sources/<source_id>', methods=['GET'])  # noqa: F821
@login_required
def get_news_source(source_id):
    """获取单个新闻源详情"""
    try:
        _, source_model = NewsSourceService.get_by_id(source_id)
        
        if not source_model:
            return get_json_result(code=404, message='新闻源不存在')
        
        source_dict = NewsSourceService.to_dict(source_model)

        if source_dict.get('tenant_id') != current_user.id:
            return get_json_result(code=404, message='新闻源不存在或无权限访问')
        
        return get_json_result(data={'source': source_dict})
    
    except Exception as e:
        return server_error_response(e)


@manager.route('/sources/<source_id>', methods=['PUT'])  # noqa: F821
@login_required
def update_news_source(source_id):
    """更新新闻源"""
    try:
        req = request.json
        source = NewsSourceService.update_source(
            source_id=source_id, 
            tenant_id=current_user.id, 
            **req
        )
        
        return get_json_result(data={'source': source})

    except ValueError as e:
        return get_json_result(code=404, message=str(e))
    except Exception as e:
        return server_error_response(e)


@manager.route('/sources/<source_id>', methods=['DELETE'])  # noqa: F821
@login_required
def delete_news_source(source_id):
    """删除新闻源"""
    try:
        NewsSourceService.update_source(
            source_id=source_id, 
            tenant_id=current_user.id, 
            status='deleted'
        )
        
        return get_json_result(message='删除成功')

    except ValueError as e:
        return get_json_result(code=404, message=str(e))
    except Exception as e:
        return server_error_response(e)


# ========== 任务管理 CRUD ==========

@manager.route('/tasks', methods=['GET'])  # noqa: F821
@login_required
def list_news_tasks():
    """获取新闻任务列表"""
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))
        task_name = request.args.get('task_name')
        status = request.args.get('status')

        tasks, total = NewsTaskService.get_by_tenant_id(
            tenant_id=current_user.id, 
            page=page, 
            page_size=page_size, 
            task_name=task_name, 
            status=status
        )

        return get_json_result(data={
            'tasks': tasks,
            'total': total,
            'page': page,
            'page_size': page_size
        })

    except Exception as e:
        return server_error_response(e)


@manager.route('/tasks', methods=['POST'])  # noqa: F821
@login_required
@validate_request('task_name', 'kb_id')
def create_news_task():
    """创建新闻任务"""
    try:
        req = request.json

        task = NewsTaskService.create_task(
            tenant_id=current_user.id,
            user_id=current_user.id,
            **req
        )

        return get_json_result(data={'task': task})

    except ValueError as e:
        return get_json_result(code=400, message=str(e))
    except Exception as e:
        return server_error_response(e)


@manager.route('/tasks/<task_id>', methods=['GET'])  # noqa: F821
@login_required
def get_news_task(task_id):
    """获取单个新闻任务详情"""
    try:
        _, task_model = NewsTaskService.get_by_id(task_id)

        if not task_model:
            return get_json_result(code=404, message='任务不存在')
        
        task_dict = NewsTaskService.to_dict(task_model)

        if task_dict.get('tenant_id') != current_user.id:
            return get_json_result(code=404, message='任务不存在或无权限访问')

        return get_json_result(data={'task': task_dict})

    except Exception as e:
        return server_error_response(e)


@manager.route('/tasks/<task_id>', methods=['PUT'])  # noqa: F821
@login_required
def update_news_task(task_id):
    """更新新闻任务"""
    try:
        req = request.json

        task = NewsTaskService.update_task(
            task_id=task_id, 
            tenant_id=current_user.id, 
            **req
        )

        return get_json_result(data={'task': task})

    except ValueError as e:
        return get_json_result(code=404, message=str(e))
    except Exception as e:
        return server_error_response(e)


@manager.route('/tasks/<task_id>', methods=['DELETE'])  # noqa: F821
@login_required
def delete_news_task(task_id):
    """删除新闻任务"""
    try:
        _, task_model = NewsTaskService.get_by_id(task_id)
        
        if not task_model:
            return get_json_result(code=404, message='任务不存在')
        
        task_dict = NewsTaskService.to_dict(task_model)

        if task_dict.get('tenant_id') != current_user.id:
            return get_json_result(code=404, message='任务不存在或无权限访问')

        NewsTaskService.update_task_status(task_id=task_id, status='deleted')

        return get_json_result(message='删除成功')

    except Exception as e:
        return server_error_response(e)


@manager.route('/tasks/<task_id>/execute', methods=['POST'])  # noqa: F821
@login_required
def execute_news_task(task_id):
    """执行新闻任务"""
    try:
        _, task_model = NewsTaskService.get_by_id(task_id)
        
        if not task_model:
            return get_json_result(code=404, message='任务不存在')
        
        task_dict = NewsTaskService.to_dict(task_model)

        if task_dict.get('tenant_id') != current_user.id:
            return get_json_result(code=404, message='任务不存在或无权限访问')

        execution_id = get_uuid()

        NewsTaskService.update_task_status(
            task_id=task_id, 
            status='running', 
            last_run_time=int(datetime.now().timestamp() * 1000)
        )

        return get_json_result(data={
            'execution_id': execution_id, 
            'status': 'running', 
            'message': '任务已开始执行'
        })

    except Exception as e:
        return server_error_response(e)


@manager.route('/tasks/<task_id>/stop', methods=['POST'])  # noqa: F821
@login_required
def stop_news_task(task_id):
    """停止新闻任务"""
    try:
        _, task_model = NewsTaskService.get_by_id(task_id)
        
        if not task_model:
            return get_json_result(code=404, message='任务不存在')
        
        task_dict = NewsTaskService.to_dict(task_model)

        if task_dict.get('tenant_id') != current_user.id:
            return get_json_result(code=404, message='任务不存在或无权限访问')

        NewsTaskService.update_task_status(task_id=task_id, status='stopped')

        return get_json_result(message='任务已停止')

    except Exception as e:
        return server_error_response(e)


# ========== 内容管理 ==========

@manager.route('/contents', methods=['GET'])  # noqa: F821
@login_required
def list_news_contents():
    """获取新闻内容列表"""
    try:
        page = int(request.args.get('page', 1))
        page_size = int(request.args.get('page_size', 20))
        task_id = request.args.get('task_id')
        source_id = request.args.get('source_id')

        if task_id:
            contents, total = NewsContentService.get_by_task_id(
                task_id=task_id, 
                page=page, 
                page_size=page_size
            )
        elif source_id:
            contents, total = NewsContentService.get_by_source_id(
                source_id=source_id, 
                page=page, 
                page_size=page_size
            )
        else:
            contents, total = [], 0

        return get_json_result(data={
            'contents': contents,
            'total': total,
            'page': page,
            'page_size': page_size
        })

    except Exception as e:
        return server_error_response(e)


@manager.route('/contents/<content_id>', methods=['GET'])  # noqa: F821
@login_required
def get_news_content(content_id):
    """获取单个新闻内容详情"""
    try:
        _, content_model = NewsContentService.get_by_id(content_id)

        if not content_model:
            return get_json_result(code=404, message='新闻内容不存在')
        
        content_dict = NewsContentService.to_dict(content_model)

        if content_dict.get('tenant_id') != current_user.id:
            return get_json_result(code=404, message='新闻内容不存在或无权限访问')

        return get_json_result(data={'content': content_dict})

    except Exception as e:
        return server_error_response(e)


@manager.route('/contents/<content_id>', methods=['DELETE'])  # noqa: F821
@login_required
def delete_news_content(content_id):
    """删除新闻内容"""
    try:
        _, content_model = NewsContentService.get_by_id(content_id)
        
        if not content_model:
            return get_json_result(code=404, message='新闻内容不存在')
        
        content_dict = NewsContentService.to_dict(content_model)

        if content_dict.get('tenant_id') != current_user.id:
            return get_json_result(code=404, message='新闻内容不存在或无权限访问')

        NewsContentService.delete_by_id(content_id)

        return get_json_result(message='删除成功')

    except Exception as e:
        return server_error_response(e)


# ========== 统计分析 ==========

@manager.route('/statistics', methods=['GET'])  # noqa: F821
@login_required
def get_news_statistics():
    """获取新闻收集统计信息"""
    try:
        days = int(request.args.get('days', 7))

        # 计算时间范围
        end_time = int(datetime.now().timestamp() * 1000)
        start_time = int((datetime.now() - timedelta(days=days)).timestamp() * 1000)

        # 获取基础统计
        sources, _ = NewsSourceService.get_by_tenant_id(current_user.id, page_size=1000)
        tasks, _ = NewsTaskService.get_by_tenant_id(current_user.id, page_size=1000)

        # 统计活跃状态
        active_sources = len([s for s in sources if s.get('status') == 'active'])
        running_tasks = len([t for t in tasks if t.get('status') == 'running'])

        # 获取时间范围内的内容统计
        content_stats = NewsContentService.get_statistics_by_time_range(
            current_user.id, start_time, end_time
        )

        return get_json_result(data={
            'summary': {
                'total_sources': len(sources),
                'active_sources': active_sources,
                'total_tasks': len(tasks),
                'running_tasks': running_tasks,
                'total_articles': content_stats.get('total_articles', 0),
            },
            'time_range_stats': content_stats,
            'analysis_period_days': days,
        })

    except Exception as e:
        return server_error_response(e)


# ========== 系统功能 ==========

@manager.route('/ping', methods=['GET'])  # noqa: F821
@login_required
def ping():
    """服务状态检查"""
    try:
        return get_json_result(data={
            'status': 'ok',
            'timestamp': datetime.now().isoformat(),
            'user_id': current_user.id,
            'version': '1.0.0'
        })

    except Exception as e:
        return server_error_response(e)


@manager.route('/crawlers', methods=['GET'])  # noqa: F821
@login_required
def get_available_crawlers():
    """获取可用爬虫列表"""
    try:
        crawlers = [
            {
                'type': 'demo',
                'name': 'Demo爬虫',
                'description': '演示爬虫 - 生成示例新闻数据'
            }
        ]

        return get_json_result(data={
            'crawlers': crawlers,
            'total': len(crawlers)
        })

    except Exception as e:
        return server_error_response(e)