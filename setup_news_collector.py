#!/usr/bin/env python3
"""
新闻收集器系统初始化和集成脚本

将新闻收集器集成到RAGFlow项目中，创建数据库表并初始化演示数据
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
    """设置新闻收集器系统"""
    try:
        # 初始化数据库表
        logger.info("正在初始化新闻收集器数据库表...")
        
        try:
            # 导入数据库模型（会自动创建表）
            from api.db.db_models import NewsSource, NewsTask, NewsContent, DB
            
            # 检查数据库连接
            with DB.connection_context():
                # 创建表（如果不存在）
                tables = [NewsSource, NewsTask, NewsContent]
                
                for table in tables:
                    table_name = table._meta.table_name
                    try:
                        if table.table_exists():
                            logger.info(f"表 {table_name} 已存在")
                        else:
                            table.create_table()
                            logger.info(f"成功创建表: {table_name}")
                    except Exception as e:
                        logger.error(f"创建表 {table_name} 失败: {e}")
                        return False
                        
            logger.info("✅ 新闻收集器数据库表初始化成功")
            return True
            
        except Exception as e:
            logger.error(f"数据库初始化错误: {e}")
            return False
            
    except Exception as e:
        logger.error(f"设置失败: {e}")
        return False


def check_api_integration():
    """检查API集成状态"""
    try:
        # 检查新闻收集器API是否已集成
        from api.apps import news_collector_app
        logger.info("✅ 新闻收集器API已集成到RAGFlow中")
        
        # 检查API路由
        logger.info("📋 可用的API端点:")
        logger.info("  - GET/POST /v1/news_collector/sources")
        logger.info("  - GET/POST /v1/news_collector/tasks")
        logger.info("  - GET /v1/news_collector/news")
        logger.info("  - GET /v1/news_collector/statistics")
        logger.info("  - GET /v1/news_collector/ping")
        
        return True
        
    except ImportError as e:
        logger.warning(f"新闻收集器API模块未找到: {e}")
        logger.info("💡 请确保 api/apps/news_collector_app.py 文件存在")
        return False
        
    except Exception as e:
        logger.error(f"检查API集成失败: {e}")
        return False


def create_demo_data():
    """创建演示数据"""
    try:
        # 导入新闻收集器服务
        from api.db.services.news_service import NewsSourceService
        from common.misc_utils import get_uuid
        
        logger.info("正在创建演示新闻源...")
        
        # 模拟用户和租户信息（实际使用时需要真实的用户信息）
        demo_user_id = "demo_user"
        demo_tenant_id = "demo_tenant"
        
        # 创建示例新闻源
        demo_sources = [
            {
                "name": "新浪科技",
                "url": "https://tech.sina.com.cn/",
                "remark": "新浪科技频道 - 演示用",
                "fetch_config": {
                    "timeout": 30,
                    "encoding": "utf-8",
                    "headers": {
                        "User-Agent": "Mozilla/5.0 (compatible; NewsCollector/1.0)"
                    }
                }
            },
            {
                "name": "网易科技", 
                "url": "https://tech.163.com/",
                "remark": "网易科技频道 - 演示用",
                "fetch_config": {
                    "timeout": 30,
                    "encoding": "utf-8",
                    "headers": {
                        "User-Agent": "Mozilla/5.0 (compatible; NewsCollector/1.0)"
                    }
                }
            },
            {
                "name": "36氪",
                "url": "https://36kr.com/",
                "remark": "创业投资资讯 - 演示用",
                "fetch_config": {
                    "timeout": 30,
                    "encoding": "utf-8",
                    "headers": {
                        "User-Agent": "Mozilla/5.0 (compatible; NewsCollector/1.0)"
                    }
                }
            }
        ]
        
        created_count = 0
        for source_data in demo_sources:
            try:
                source = NewsSourceService.create_source(
                    name=source_data["name"],
                    url=source_data["url"],
                    user_id=demo_user_id,
                    tenant_id=demo_tenant_id,
                    remark=source_data["remark"],
                    fetch_config=source_data["fetch_config"]
                )
                
                logger.info(f"✅ 创建演示新闻源: {source_data['name']}")
                created_count += 1
                
            except Exception as e:
                logger.warning(f"创建新闻源 {source_data['name']} 失败: {e}")
        
        logger.info(f"✅ 成功创建 {created_count} 个演示新闻源")
        return created_count > 0
        
    except Exception as e:
        logger.error(f"创建演示数据失败: {e}")
        return False


def main():
    """主函数"""
    print("🚀 初始化新闻收集器系统...")
    print("="*60)
    
    # 设置新闻收集器系统
    if setup_news_collector():
        print("✅ 新闻收集器数据库表初始化成功")
    else:
        print("❌ 新闻收集器数据库表初始化失败")
        return False
    
    # 检查API集成
    if check_api_integration():
        print("✅ API集成检查通过")
    else:
        print("⚠️  API集成检查失败，但不影响使用")
    
    # 创建演示数据
    print("\n📝 创建演示数据...")
    if create_demo_data():
        print("✅ 演示数据创建成功")
    else:
        print("⚠️  演示数据创建失败（可能是权限问题）")
    
    print("\n" + "="*60)
    print("🎉 新闻收集器系统初始化完成！")
    print("="*60)
    
    print("\n📋 系统功能:")
    print("1. 📰 新闻源管理 - 添加、编辑、删除新闻源")
    print("2. 🎯 抓取任务管理 - 创建和执行抓取任务")
    print("3. 📄 内容管理 - 查看和管理抓取的新闻内容")
    print("4. 🔗 知识库集成 - 自动解析新闻到RAGFlow知识库")
    print("5. 📊 统计报表 - 查看抓取和解析统计数据")
    print("6. 📁 文件管理 - 在前端文件管理页面查看新闻文件")
    
    print("\n🌐 API接口 (需要用户认证):")
    print("- 新闻源管理: /v1/news_collector/sources")
    print("- 抓取任务管理: /v1/news_collector/tasks")
    print("- 新闻内容管理: /v1/news_collector/news")
    print("- 统计信息: /v1/news_collector/statistics")
    print("- 健康检查: /v1/news_collector/ping")
    print("- 任务文档: /v1/news_collector/tasks/{id}/documents")
    
    print("\n📚 使用说明:")
    print("1. 启动RAGFlow服务: python api/ragflow_server.py")
    print("2. 登录RAGFlow前端获取访问令牌")
    print("3. 使用API创建新闻源和抓取任务")
    print("4. 在前端文件管理页面查看抓取结果")
    print("5. 参考文档: NEWS_COLLECTOR_UNIFIED_DOCUMENT_FLOW.md")
    
    print("\n💡 特色功能:")
    print("- 🔄 统一文档流: 新闻直接转换为RAGFlow文档")
    print("- 📁 自动文件夹: 按新闻源自动组织文件结构")
    print("- 🚫 避免重复: 智能去重，避免重复存储")
    print("- 🔍 全文搜索: 新闻内容可通过RAGFlow搜索")
    print("- ⚡ 自动解析: 新闻自动进入解析pipeline")
    
    return True


if __name__ == "__main__":
    success = main()
    if success:
        print("\n" + "="*60)
        print("🎉 新闻收集器系统准备就绪！")
        print("="*60)
        print("💡 提示：")
        print("  - 启动RAGFlow服务后即可使用新闻收集器功能")
        print("  - 在前端文件管理页面可以看到 '📰 新闻收集' 文件夹")
        print("  - 所有新闻内容会自动转换为可搜索的文档")
        print("="*60)
    else:
        print("\n❌ 系统初始化失败，请检查配置和依赖")
        sys.exit(1)
