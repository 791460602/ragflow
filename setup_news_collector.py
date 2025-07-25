#!/usr/bin/env python3
"""
新闻抓取系统初始化和集成脚本

将新闻抓取系统集成到现有的RAGFlow项目中
"""

import os
import sys
import logging
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def setup_news_collector():
    """设置新闻抓取系统"""
    try:
        # 首先初始化数据库表
        try:
            from news_collector.init_db import create_news_tables
            if create_news_tables():
                logger.info("News database tables initialized successfully")
            else:
                logger.error("Failed to initialize news database tables")
                return None
        except Exception as e:
            logger.error(f"Database initialization error: {e}")
            return None
        
        # 导入SDK路径
        sdk_path = project_root / 'sdk' / 'python'
        if sdk_path.exists():
            sys.path.insert(0, str(sdk_path))
            logger.info(f"Added SDK path: {sdk_path}")
        
        # 导入RAGFlow SDK
        try:
            from ragflow_sdk import RAGFlow
            logger.info("RAGFlow SDK imported successfully")
        except ImportError as e:
            logger.error(f"Failed to import RAGFlow SDK: {e}")
            logger.info("Please ensure RAGFlow SDK is properly installed")
            # 使用模拟客户端用于测试
            class MockRAGFlowClient:
                def __init__(self):
                    self.base_url = "http://localhost:9380"
                    self.api_key = "test_key"
                
                def create_knowledge_base(self, **kwargs):
                    return {"id": f"kb_{kwargs.get('name', 'test')}", "name": kwargs.get("name")}
                
                def list_knowledge_bases(self):
                    return [{"id": "test_kb_001", "name": "测试知识库"}]
            
            ragflow_client = MockRAGFlowClient()
            logger.info("Using mock RAGFlow client for testing")
        
        # 导入新闻抓取模块
        try:
            from news_collector import services
            
            # 如果有真实的RAGFlow SDK，使用配置初始化
            if 'RAGFlow' in locals():
                try:
                    from news_collector.config import get_config
                    config = get_config("ragflow")
                    ragflow_client = RAGFlow(
                        api_key=config["api_key"],
                        base_url=config["base_url"]
                    )
                except Exception as e:
                    logger.warning(f"Failed to load RAGFlow config, using mock client: {e}")
            
            # 初始化新闻管理器
            services.initialize_news_manager(ragflow_client)
            logger.info("News collector initialized successfully")
            
            return ragflow_client
            
        except Exception as e:
            logger.error(f"Failed to initialize news collector: {e}")
            return None
            
    except Exception as e:
        logger.error(f"Setup failed: {e}")
        return None


def register_api_routes(app):
    """注册API路由到Flask应用"""
    try:
        from api.apps.news_collector.routes import news_collector_bp
        
        # 注册蓝图
        app.register_blueprint(news_collector_bp)
        logger.info("News collector API routes registered")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to register API routes: {e}")
        return False


def create_demo_data():
    """创建演示数据"""
    try:
        from news_collector import services
        
        # 创建示例新闻源
        demo_sources = [
            {
                "name": "新浪科技",
                "url": "https://tech.sina.com.cn/",
                "remark": "新浪科技频道",
                "status": "active",
                "selector_config": {
                    "title_selector": "h1",
                    "content_selector": ".article-content",
                    "time_selector": ".time-source .time",
                    "author_selector": ".author",
                    "link_selector": "a[href*='/tech/']"
                }
            },
            {
                "name": "网易科技",
                "url": "https://tech.163.com/",
                "remark": "网易科技频道",
                "status": "active",
                "selector_config": {
                    "title_selector": "h1",
                    "content_selector": ".post-body",
                    "time_selector": ".post-info .time",
                    "author_selector": ".source",
                    "link_selector": "a[href*='/tech/']"
                }
            }
        ]
        
        for source_data in demo_sources:
            result = services.create_news_source(source_data)
            if result:
                logger.info(f"Created demo news source: {source_data['name']}")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to create demo data: {e}")
        return False


def main():
    """主函数"""
    print("🚀 初始化新闻抓取与管理系统...")
    
    # 设置新闻抓取系统
    ragflow_client = setup_news_collector()
    if not ragflow_client:
        print("❌ 新闻抓取系统初始化失败")
        return False
    
    print("✅ 新闻抓取系统初始化成功")
    
    # 创建演示数据
    if create_demo_data():
        print("✅ 演示数据创建成功")
    else:
        print("⚠️  演示数据创建失败")
    
    print("\n📋 系统功能:")
    print("1. 新闻源管理 - 添加、编辑、删除新闻源")
    print("2. 抓取任务管理 - 创建和执行抓取任务")
    print("3. 内容管理 - 查看和管理抓取的新闻内容")
    print("4. 知识库集成 - 自动解析新闻到RAGFlow知识库")
    print("5. 统计报表 - 查看抓取和解析统计数据")
    
    print("\n🌐 API接口:")
    print("- 知识库管理: /api/v1/news_collector/knowledge_bases")
    print("- 新闻源管理: /api/v1/news_collector/sources")
    print("- 抓取任务管理: /api/v1/news_collector/tasks")
    print("- 新闻内容管理: /api/v1/news_collector/news")
    print("- 统计报表: /api/v1/news_collector/stats")
    
    print("\n📚 使用示例:")
    print("请参考项目根目录下的 test_news_collector.py 文件")
    
    return True


if __name__ == "__main__":
    success = main()
    if success:
        print("\n🎉 新闻抓取与管理系统准备就绪！")
        print("💡 提示：您可以通过API接口或集成到现有的RAGFlow界面中使用")
    else:
        print("\n❌ 系统初始化失败，请检查配置和依赖")
        sys.exit(1)
