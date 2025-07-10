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
import logging
from flask import request
from flask_login import login_required, current_user
from api.utils.api_utils import server_error_response, get_json_result, validate_request


@manager.route('/news_scheduler/config', methods=['POST'])  # noqa: F821
@login_required
@validate_request("config")
def set_news_scheduler_config():
    """设置新闻调度配置"""
    try:
        req = request.json
        config = req.get("config", {})
        
        # 验证配置
        if not isinstance(config, dict):
            return get_json_result(data=False, message="配置格式错误", code=400)
        
        # 设置配置
        tenant_id = current_user.id
        news_scheduler.add_tenant_config(tenant_id, config)
        
        return get_json_result(data=True, message="配置设置成功")
            
        except Exception as e:
        logging.error(f"设置新闻调度配置失败: {str(e)}")
        return server_error_response(e)


@manager.route('/news_scheduler/config', methods=['GET'])  # noqa: F821
@login_required
def get_news_scheduler_config():
    """获取新闻调度配置"""
    try:
        tenant_id = current_user.id
        status = news_scheduler.get_job_status(tenant_id)
        
        return get_json_result(data=status)
            
        except Exception as e:
        logging.error(f"获取新闻调度配置失败: {str(e)}")
        return server_error_response(e)


@manager.route('/news_scheduler/config', methods=['DELETE'])  # noqa: F821
@login_required
def remove_news_scheduler_config():
    """移除新闻调度配置"""
    try:
        tenant_id = current_user.id
        news_scheduler.remove_tenant_config(tenant_id)
        
        return get_json_result(data=True, message="配置移除成功")
            
        except Exception as e:
        logging.error(f"移除新闻调度配置失败: {str(e)}")
        return server_error_response(e)


@manager.route('/news_scheduler/status', methods=['GET'])  # noqa: F821
@login_required
def get_news_scheduler_status():
    """获取新闻调度状态"""
    try:
        tenant_id = current_user.id
        status = news_scheduler.get_job_status(tenant_id)
        
        return get_json_result(data=status)
        
    except Exception as e:
        logging.error(f"获取新闻调度状态失败: {str(e)}")
        return server_error_response(e)


@manager.route('/news_scheduler/start', methods=['POST'])  # noqa: F821
@login_required
def start_news_scheduler():
    """启动新闻调度服务"""
    try:
        news_scheduler.start()
        
        return get_json_result(data=True, message="新闻调度服务已启动")
            
        except Exception as e:
        logging.error(f"启动新闻调度服务失败: {str(e)}")
        return server_error_response(e)


@manager.route('/news_scheduler/stop', methods=['POST'])  # noqa: F821
@login_required
def stop_news_scheduler():
    """停止新闻调度服务"""
    try:
        news_scheduler.stop()
        
        return get_json_result(data=True, message="新闻调度服务已停止")
            
        except Exception as e:
        logging.error(f"停止新闻调度服务失败: {str(e)}")
        return server_error_response(e)


@manager.route('/news_scheduler/test_crawl', methods=['POST'])  # noqa: F821
@login_required
@validate_request("news_sources")
def test_news_crawl():
    """测试新闻抓取"""
    try:
        req = request.json
        news_sources = req.get("news_sources", [])
        
        if not news_sources:
            return get_json_result(data=False, message="请提供新闻源", code=400)
        
        # 创建测试配置
        test_config = {
            "news_sources": news_sources,
            "max_news_per_source": req.get("max_news_per_source", 5),
            "date_filter": req.get("date_filter", "today"),
            "keywords": req.get("keywords", []),
            "timeout": req.get("timeout", 30)
        }
        
        # 执行测试抓取
        import asyncio
        from agent.component.news_crawler import NewsCrawler, NewsCrawlerParam
        
            crawler = NewsCrawler()
            crawler._param = NewsCrawlerParam()
        crawler._param.news_sources = test_config["news_sources"]
        crawler._param.max_news_per_source = test_config["max_news_per_source"]
        crawler._param.date_filter = test_config["date_filter"]
        crawler._param.keywords = test_config["keywords"]
        crawler._param.timeout = test_config["timeout"]
        
        crawler._input = {"content": news_sources}
            result = crawler._run([])
            
            if isinstance(result, pd.DataFrame) and not result.empty:
            return get_json_result(data=result.to_dict('records'), message="测试抓取成功")
            else:
            return get_json_result(data=False, message="测试抓取失败，未获取到新闻")
            
        except Exception as e:
        logging.error(f"测试新闻抓取失败: {str(e)}")
        return server_error_response(e)


@manager.route('/news_scheduler/test_report', methods=['POST'])  # noqa: F821
@login_required
@validate_request("kb_ids")
def test_report_generation():
    """测试简报生成"""
    try:
        req = request.json
        kb_ids = req.get("kb_ids", [])
        
        if not kb_ids:
            return get_json_result(data=False, message="请提供知识库ID", code=400)
        
        # 创建测试配置
        test_config = {
            "kb_ids": kb_ids,
            "report_title": req.get("report_title", "测试简报"),
            "report_template": req.get("report_template", "standard"),
            "max_news_count": req.get("max_news_count", 10),
            "categorize_news": req.get("categorize_news", True),
            "language": req.get("language", "zh-CN")
        }
        
        # 执行测试生成
        from agent.component.daily_report_generator import DailyReportGenerator, DailyReportGeneratorParam
        
            generator = DailyReportGenerator()
            generator._param = DailyReportGeneratorParam()
        generator._param.kb_ids = test_config["kb_ids"]
        generator._param.report_title = test_config["report_title"]
        generator._param.report_template = test_config["report_template"]
        generator._param.max_news_count = test_config["max_news_count"]
        generator._param.categorize_news = test_config["categorize_news"]
        generator._param.language = test_config["language"]
        
        generator._input = {"content": kb_ids}
            result = generator._run([])
            
            if isinstance(result, pd.DataFrame) and not result.empty:
                report_content = result.iloc[0]["content"]
            return get_json_result(data={"report": report_content}, message="测试简报生成成功")
            else:
            return get_json_result(data=False, message="测试简报生成失败")
            
        except Exception as e:
        logging.error(f"测试简报生成失败: {str(e)}")
        return server_error_response(e)


@manager.route('/news_scheduler/admin/status', methods=['GET'])  # noqa: F821
@login_required
def get_all_scheduler_status():
    """获取所有调度器状态（管理员接口）"""
    try:
        # 检查管理员权限
        if not current_user.is_admin:
            return get_json_result(data=False, message="权限不足", code=403)
        
        all_status = news_scheduler.get_all_job_status()
        
        return get_json_result(data=all_status)
        
    except Exception as e:
        logging.error(f"获取所有调度器状态失败: {str(e)}")
        return server_error_response(e) 