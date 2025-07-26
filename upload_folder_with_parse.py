#!/usr/bin/env python3
"""
RAGFlow 文件夹上传并自动解析示例 + 新闻抓取系统集成
上传本地文件夹到知识库，保持目录结构，并自动开始解析

更新说明：
- 修复了文件路径解析问题，避免 FileNotFoundError
- 改进了 binary 数据处理，确保解析器正确使用文件内容
- 增强了错误处理和日志记录
- 新增：集成新闻抓取系统功能
"""

import os
import sys

# 添加SDK路径
sdk_path = os.path.join(os.path.dirname(__file__), 'sdk', 'python')
sys.path.insert(0, sdk_path)

# 添加新闻抓取系统路径
sys.path.insert(0, os.path.dirname(__file__))

from ragflow_sdk import RAGFlow

# 配置参数
API_KEY = "ragflow-M3NDJjZmEyNjYwZDExZjBhMTAwYjlkOD"  # 你的API密钥
BASE_URL = "http://localhost:9380"  # RAGFlow服务地址
LOCAL_FOLDER_PATH = r"/mnt/e/下载/test"  # 要上传的本地文件夹路径
DATASET_NAME = "讲义知识库"  # 目标知识库名称
PARENT_ID = ""  # 上传到的父目录ID，空字符串表示根目录


def main():
    try:
        # 初始化RAGFlow客户端
        rag = RAGFlow(api_key=API_KEY, base_url=BASE_URL)
        print("✅ RAGFlow客户端初始化成功")
        
        # 获取或创建数据集
        try:
            dataset = rag.get_dataset(DATASET_NAME)
            print(f"✅ 找到已存在的数据集: {DATASET_NAME}")
        except Exception:
            print(f"📝 数据集 '{DATASET_NAME}' 不存在，正在创建...")
            dataset = rag.create_dataset(
                name=DATASET_NAME,
                description="通过文件夹上传创建的知识库",
                chunk_method="naive"
            )
            print(f"✅ 数据集创建成功: {DATASET_NAME}")
        
        # 检查本地文件夹是否存在
        if not os.path.exists(LOCAL_FOLDER_PATH):
            print(f"❌ 本地文件夹不存在: {LOCAL_FOLDER_PATH}")
            return
        
        print(f"📂 开始上传文件夹: {LOCAL_FOLDER_PATH}")
        print(f"🎯 目标数据集: {DATASET_NAME} (ID: {dataset.id})")
        
        # 上传文件夹并自动开始解析
        print("🔄 上传并自动解析...")
        result = dataset.upload_folder(LOCAL_FOLDER_PATH, PARENT_ID, auto_parse=True)
        
        print("🎉 上传完成!")
        print(f"📊 上传结果: {result.get('message', '成功')}")
        
        # 显示上传的文件信息
        upload_data = result.get('upload_result', {}).get('data', [])
        if upload_data:
            print(f"📁 成功上传 {len(upload_data)} 个文件:")
            for file_info in upload_data[:5]:  # 只显示前5个
                print(f"  - {file_info.get('name', 'Unknown')} (ID: {file_info.get('id', 'Unknown')})")
            if len(upload_data) > 5:
                print(f"  ... 还有 {len(upload_data) - 5} 个文件")
        
        # 显示转换结果
        convert_data = result.get('convert_result', {}).get('data', [])
        if convert_data:
            print(f"📚 成功转换 {len(convert_data)} 个文档到知识库")
        
        # 显示解析结果
        parse_result = result.get('parse_result')
        if parse_result:
            if parse_result.get('status') == 'started':
                print(f"✅ 文档解析已开始！")
                print(f"📊 解析文档数量: {parse_result.get('document_count', 0)}")
                print("💡 解析是异步进行的，您可以在 RAGFlow 界面中查看解析进度")
                print("📋 解析完成后，文档将可用于检索和问答")
            else:
                print(f"⚠️  解析启动失败: {parse_result.get('error', '未知错误')}")
                print("💡 您可以稍后在 RAGFlow 界面中手动启动解析")
        
        print("\n🔗 文件已成功上传并关联到知识库，保持了原有的目录结构！")
        print("🚀 文档解析正在后台进行中...")
        
        # 新增：演示新闻抓取系统集成
        demo_news_collector_integration(rag, dataset)
        
    except Exception as e:
        print(f"❌ 上传失败: {str(e)}")
        import traceback
        traceback.print_exc()


def demo_news_collector_integration(rag_client, dataset):
    """演示新闻抓取系统集成"""
    print("\n" + "="*60)
    print("🗞️  新闻抓取系统集成演示")
    print("="*60)
    
    try:
        # 尝试导入新闻抓取系统
        from news_collector import services
        from news_collector.config import get_config
        
        # 初始化新闻管理器
        services.initialize_news_manager(rag_client)
        print("✅ 新闻抓取系统初始化成功")
        
        # 创建示例新闻源
        demo_source_data = {
            "name": "新浪科技",
            "url": "https://tech.sina.com.cn/",
            "remark": "新浪科技频道 - 演示用",
            "status": "active",
            "selector_config": {
                "title_selector": "h1",
                "content_selector": ".article-content",
                "time_selector": ".time-source .time",
                "author_selector": ".author",
                "link_selector": "a[href*='/tech/']"
            }
        }
        
        source_result = services.create_news_source(demo_source_data)
        if source_result:
            source_id = source_result["id"]
            print(f"✅ 创建演示新闻源成功: ID {source_id}")
            
            # 创建示例抓取任务
            task_data = {
                "task_name": "演示新闻抓取任务",
                "kb_id": dataset.id,
                "source_ids": [source_id],
                "auto_parse": True,
                "max_articles_per_source": 10
            }
            
            task_result = services.create_news_task(task_data)
            if task_result:
                task_id = task_result["id"]
                print(f"✅ 创建演示抓取任务成功: ID {task_id}")
                print("💡 任务已创建，您可以通过API手动执行:")
                print(f"   POST /api/v1/news_collector/tasks/{task_id}/execute")
        
        # 显示统计信息
        stats = services.get_statistics_overview()
        print(f"\n📊 当前系统统计:")
        print(f"   新闻源数量: {stats.get('total_sources', 0)}")
        print(f"   抓取任务数量: {stats.get('total_tasks', 0)}")
        print(f"   新闻数量: {stats.get('total_news', 0)}")
        
        print(f"\n🌐 新闻抓取系统API地址:")
        print(f"   知识库管理: {BASE_URL}/api/v1/news_collector/knowledge_bases")
        print(f"   新闻源管理: {BASE_URL}/api/v1/news_collector/sources")
        print(f"   抓取任务管理: {BASE_URL}/api/v1/news_collector/tasks")
        print(f"   新闻内容管理: {BASE_URL}/api/v1/news_collector/news")
        
    except ImportError:
        print("⚠️  新闻抓取系统模块未找到")
        print("💡 请先运行 setup_news_collector.py 初始化系统")
        print("💡 或者查看 NEWS_COLLECTOR_README.md 了解安装步骤")
    except Exception as e:
        print(f"⚠️  新闻抓取系统集成失败: {str(e)}")
        print("💡 请检查系统配置和依赖")


def demo_methods():
    """
    演示不同的上传和解析方法
    """
    print("\n" + "="*60)
    print("📖 上传和解析方法说明:")
    print("="*60)
    
    print("""
    方法1: 保持目录结构 + 自动解析
    result = dataset.upload_folder(folder_path, parent_id, auto_parse=True)
    - ✅ 保持完整的文件夹层级结构
    - ✅ 自动开始文档解析
    - ✅ 完整的权限控制
    - 🎯 适合: 需要完整文档管理和自动化处理的场景
    
    方法2: 简单上传 + 自动解析
    documents = dataset.upload_folder_direct(folder_path, auto_parse=True)
    - ✅ 简单快速
    - ✅ 自动开始文档解析
    - ✅ 文件名中保留路径信息
    - 🎯 适合: 快速导入和处理文档的场景
    
    方法3: 手动控制解析
    result = dataset.upload_folder(folder_path)  # auto_parse=False (默认)
    # 稍后手动开始解析
    dataset.async_parse_documents(document_ids)
    - ✅ 完全控制解析时机
    - ✅ 可以批量处理多个上传后再解析
    - 🎯 适合: 需要精确控制解析流程的场景
    
    💡 解析说明:
    - 解析是异步进行的，不会阻塞程序执行
    - 解析进度可以在 RAGFlow Web 界面中查看
    - 解析完成后，文档才能用于检索和问答
    - 大文件解析可能需要较长时间
    
    🗞️  新增功能: 新闻抓取系统
    - 自动从新闻网站抓取最新内容
    - 智能解析新闻标题、正文、发布时间等
    - 自动上传到指定知识库并解析
    - 支持定时任务和批量处理
    - 提供完整的管理界面和API
    """)


def show_news_collector_usage():
    """显示新闻抓取系统使用方法"""
    print("\n" + "="*60)
    print("🗞️  新闻抓取系统使用指南:")
    print("="*60)
    
    print("""
    1. 初始化系统:
       python setup_news_collector.py
    
    2. 创建新闻源:
       POST /api/v1/news_collector/sources
       {
           "name": "新闻源名称",
           "url": "https://example.com/news",
           "selector_config": {
               "title_selector": "h1",
               "content_selector": ".content"
           }
       }
    
    3. 创建抓取任务:
       POST /api/v1/news_collector/tasks
       {
           "task_name": "任务名称",
           "kb_id": "知识库ID",
           "source_ids": [1, 2],
           "auto_parse": true
       }
    
    4. 执行任务:
       POST /api/v1/news_collector/tasks/{task_id}/execute
    
    5. 查看结果:
       GET /api/v1/news_collector/news
    
    💡 更多信息请查看:
    - NEWS_COLLECTOR_README.md
    - docs/news_collector_api_v1.1.md
    - demo_news_collector.py
    """)


if __name__ == "__main__":
    main()
    demo_methods()
    show_news_collector_usage()
