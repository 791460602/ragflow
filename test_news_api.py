"""
新闻收集器API测试脚本

测试数据库集成的新闻API功能
"""

import sys
import os
import json
import logging
from datetime import datetime

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_database_services():
    """测试数据库服务层"""
    print("🧪 测试数据库服务层...")
    
    try:
        # 首先初始化数据库
        from news_collector.init_db import create_news_tables
        print("📁 初始化数据库表...")
        if create_news_tables():
            print("✅ 数据库表创建成功")
        else:
            print("❌ 数据库表创建失败")
            return False
            
        # 导入服务层
        from news_collector import db_services
        
        # 1. 测试知识库
        print("\n📚 测试知识库功能...")
        kb_data = {
            "id": "test_kb_api",
            "name": "API测试知识库",
            "description": "用于API测试的知识库"
        }
        kb = db_services.create_knowledge_base(kb_data)
        print(f"✅ 创建知识库: {kb['name']}")
        
        # 获取知识库列表
        kbs = db_services.get_knowledge_bases()
        print(f"✅ 获取知识库列表: {len(kbs)} 个")
        
        # 2. 测试新闻源
        print("\n📰 测试新闻源功能...")
        source_data = {
            "name": "API测试新闻源",
            "url": "https://example.com/news",
            "remark": "用于API测试",
            "selector_config": {
                "title_selector": "h1",
                "content_selector": ".content",
                "link_selector": "a"
            }
        }
        source = db_services.create_news_source(source_data)
        print(f"✅ 创建新闻源: {source['name']} (ID: {source['id']})")
        
        # 获取新闻源列表
        sources = db_services.get_news_sources(page=1, page_size=10)
        print(f"✅ 获取新闻源列表: {sources['total']} 个")
        
        # 3. 测试任务
        print("\n⚙️ 测试任务功能...")
        task_data = {
            "task_name": "API测试任务",
            "kb_id": kb_data["id"],
            "source_ids": [source["id"]],
            "auto_parse": True,
            "max_articles_per_source": 5
        }
        task = db_services.create_news_task(task_data)
        print(f"✅ 创建任务: {task['task_name']} (ID: {task['id']})")
        
        # 获取任务列表
        tasks = db_services.get_news_tasks(page=1, page_size=10)
        print(f"✅ 获取任务列表: {tasks['total']} 个")
        
        # 4. 测试统计信息
        print("\n📊 测试统计功能...")
        stats = db_services.get_statistics_overview()
        print(f"✅ 统计信息: 新闻源 {stats.get('total_sources', 0)} 个, 任务 {stats.get('total_tasks', 0)} 个")
        
        print("\n🎉 数据库服务层测试完成！")
        return True
        
    except Exception as e:
        print(f"❌ 数据库服务测试失败: {e}")
        logger.error(f"Database service test failed: {e}")
        return False

def test_api_compatibility():
    """测试API兼容性"""
    print("\n🔗 测试API兼容性...")
    
    try:
        # 测试API服务层
        from api.apps.news_collector import services
        
        print("✅ API服务层导入成功")
        
        # 测试新闻源获取
        sources = services.get_news_sources()
        print(f"✅ API获取新闻源: {len(sources)} 个")
        
        # 测试历史记录
        history = services.get_news_history()
        print(f"✅ API获取历史记录: {len(history)} 个")
        
        print("🎉 API兼容性测试完成！")
        return True
        
    except Exception as e:
        print(f"❌ API兼容性测试失败: {e}")
        logger.error(f"API compatibility test failed: {e}")
        return False

def test_new_routes():
    """测试新路由"""
    print("\n🛣️ 测试新路由...")
    
    try:
        from api.apps.news_collector.routes_new import news_collector_bp
        
        print("✅ 新路由蓝图导入成功")
        print(f"✅ 路由前缀: {news_collector_bp.url_prefix}")
        
        # 列出所有路由
        routes = []
        for rule in news_collector_bp.url_map.iter_rules():
            routes.append(f"{rule.methods} {rule.rule}")
        
        print(f"✅ 注册路由数量: {len(routes)}")
        for route in routes[:5]:  # 显示前5个路由
            print(f"   - {route}")
        
        print("🎉 新路由测试完成！")
        return True
        
    except Exception as e:
        print(f"❌ 新路由测试失败: {e}")
        logger.error(f"New routes test failed: {e}")
        return False

def main():
    """主测试函数"""
    print("🚀 开始测试新闻收集器API集成...")
    
    success_count = 0
    total_tests = 3
    
    # 1. 测试数据库服务
    if test_database_services():
        success_count += 1
    
    # 2. 测试API兼容性
    if test_api_compatibility():
        success_count += 1
    
    # 3. 测试新路由
    if test_new_routes():
        success_count += 1
    
    print(f"\n📊 测试结果: {success_count}/{total_tests} 通过")
    
    if success_count == total_tests:
        print("🎉 所有测试通过！新闻收集器API已准备就绪")
        print("\n📋 可用的API端点:")
        print("- GET  /api/v1/news_collector/ping                 - 健康检查")
        print("- GET  /api/v1/news_collector/knowledge_bases      - 获取知识库列表")
        print("- POST /api/v1/news_collector/knowledge_bases      - 创建知识库")
        print("- GET  /api/v1/news_collector/sources              - 获取新闻源列表")
        print("- POST /api/v1/news_collector/sources              - 创建新闻源")
        print("- GET  /api/v1/news_collector/sources/{id}         - 获取新闻源详情")
        print("- PUT  /api/v1/news_collector/sources/{id}         - 更新新闻源")
        print("- DELETE /api/v1/news_collector/sources/{id}       - 删除新闻源")
        print("- GET  /api/v1/news_collector/tasks                - 获取任务列表")
        print("- POST /api/v1/news_collector/tasks                - 创建任务")
        print("- GET  /api/v1/news_collector/tasks/{id}           - 获取任务详情")
        print("- PUT  /api/v1/news_collector/tasks/{id}           - 更新任务")
        print("- POST /api/v1/news_collector/tasks/{id}/execute   - 执行任务")
        print("- DELETE /api/v1/news_collector/tasks/{id}         - 删除任务")
        print("- GET  /api/v1/news_collector/news                 - 获取新闻列表")
        print("- GET  /api/v1/news_collector/news/{id}            - 获取新闻详情")
        print("- DELETE /api/v1/news_collector/news/{id}          - 删除新闻")
        print("- GET  /api/v1/news_collector/statistics           - 获取统计信息")
        print("- GET  /api/v1/news_collector/statistics/sources/{id} - 获取源统计")
        return True
    else:
        print("❌ 部分测试失败，请检查错误信息")
        return False

if __name__ == "__main__":
    success = main()
    if not success:
        sys.exit(1)
