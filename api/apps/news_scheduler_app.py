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
import json
import os
from datetime import datetime
from flask import request
from flask_login import login_required, current_user
from api.utils.api_utils import server_error_response, get_json_result, validate_request


class NewsScheduler:
    """新闻调度服务类"""
    
    def __init__(self):
        self.config_file = "news_scheduler_config.json"
        self.configs = {}
        self.jobs = {}
        self.load_configs()
    
    def load_configs(self):
        """加载配置文件"""
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.configs = json.load(f)
        except Exception as e:
            logging.error(f"加载配置文件失败: {str(e)}")
            self.configs = {}
    
    def save_configs(self):
        """保存配置文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.configs, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"保存配置文件失败: {str(e)}")
    
    def add_tenant_config(self, tenant_id, config):
        """添加租户配置"""
        self.configs[str(tenant_id)] = {
            "config": config,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        self.save_configs()
    
    def remove_tenant_config(self, tenant_id):
        """移除租户配置"""
        tenant_id_str = str(tenant_id)
        if tenant_id_str in self.configs:
            del self.configs[tenant_id_str]
            self.save_configs()
    
    def get_job_status(self, tenant_id):
        """获取任务状态"""
        tenant_id_str = str(tenant_id)
        if tenant_id_str in self.configs:
            return {
                "tenant_id": tenant_id,
                "config": self.configs[tenant_id_str]["config"],
                "status": "active" if tenant_id_str in self.jobs else "inactive",
                "last_run": self.jobs.get(tenant_id_str, {}).get("last_run"),
                "next_run": self.jobs.get(tenant_id_str, {}).get("next_run")
            }
        return None
    
    def get_all_job_status(self):
        """获取所有任务状态"""
        return [self.get_job_status(tenant_id) for tenant_id in self.configs.keys()]
    
    def start(self):
        """启动调度服务"""
        logging.info("新闻调度服务已启动")
        # 这里可以添加实际的调度逻辑，比如使用APScheduler等
    
    def stop(self):
        """停止调度服务"""
        logging.info("新闻调度服务已停止")
        # 这里可以添加停止调度的逻辑


# 创建全局实例
news_scheduler = NewsScheduler()


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
        import pandas as pd
        from agent.component.news_crawler_impl import NewsCrawlerImpl
        
        crawler = NewsCrawlerImpl()
        crawler.news_sources = test_config["news_sources"]
        crawler.max_news_per_source = test_config["max_news_per_source"]
        crawler.date_filter = test_config["date_filter"]
        crawler.keywords = test_config["keywords"]
        crawler.timeout = test_config["timeout"]
        
        result = crawler.crawl_news()
        
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
        from agent.component.daily_report_generator_impl import DailyReportGeneratorImpl
        
        generator = DailyReportGeneratorImpl()
        generator.kb_ids = test_config["kb_ids"]
        generator.report_title = test_config["report_title"]
        generator.report_template = test_config["report_template"]
        generator.max_news_count = test_config["max_news_count"]
        generator.categorize_news = test_config["categorize_news"]
        generator.language = test_config["language"]
        
        result = generator.generate_report()
        
        if result and isinstance(result, str):
            return get_json_result(data={"report": result}, message="测试简报生成成功")
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