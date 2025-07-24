#!/usr/bin/env python3
"""
新闻抓取系统演示脚本

展示如何使用新闻抓取系统的各种功能
"""

import os
import sys
import asyncio
import json
from pathlib import Path
from datetime import datetime

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def print_banner():
    """打印欢迎横幅"""
    print("=" * 70)
    print("🗞️  新闻抓取与管理平台演示")
    print("=" * 70)
    print("这个演示将展示系统的主要功能:")
    print("1. 创建和管理新闻源")
    print("2. 创建和执行抓取任务")
    print("3. 管理新闻内容")
    print("4. 查看统计报表")
    print("=" * 70)


def demo_models():
    """演示数据模型"""
    print("\n📊 演示数据模型...")
    
    try:
        from news_collector.models import NewsSource, NewsTask, NewsContent, SelectorConfig
        
        # 创建选择器配置
        selector = SelectorConfig(
            title_selector="h1.headline",
            content_selector=".article-body",
            time_selector=".publish-time",
            author_selector=".author-name"
        )
        
        print("✅ 选择器配置:")
        print(f"   标题: {selector.title_selector}")
        print(f"   内容: {selector.content_selector}")
        
        # 创建新闻源
        source = NewsSource(
            id=1,
            name="演示新闻源",
            url="https://example.com/news",
            remark="这是一个演示用的新闻源",
            selector_config=selector,
            created_at=datetime.now()
        )
        
        print(f"✅ 新闻源: {source.name}")
        print(f"   URL: {source.url}")
        
        # 序列化测试
        source_dict = source.to_dict()
        restored_source = NewsSource.from_dict(source_dict)
        
        print(f"✅ 序列化测试: {restored_source.name == source.name}")
        
    except ImportError as e:
        print(f"⚠️  无法导入模块: {e}")
        print("请确保已正确安装系统模块")


def demo_configuration():
    """演示配置系统"""
    print("\n⚙️  演示配置系统...")
    
    try:
        from news_collector.config import get_config, get_selector_config_for_domain
        
        # 获取配置
        ragflow_config = get_config("ragflow")
        scraper_config = get_config("scraper")
        
        print("✅ RAGFlow配置:")
        print(f"   API URL: {ragflow_config.get('base_url')}")
        print(f"   超时设置: {scraper_config.get('timeout')}秒")
        
        # 获取域名预设配置
        sina_config = get_selector_config_for_domain("sina.com.cn")
        print("✅ 新浪网预设配置:")
        print(f"   标题选择器: {sina_config.get('title_selector')}")
        
    except ImportError as e:
        print(f"⚠️  无法导入配置模块: {e}")


async def demo_scraper():
    """演示新闻抓取器"""
    print("\n🕷️  演示新闻抓取器...")
    
    try:
        from news_collector.scraper import NewsScraper
        from news_collector.models import SelectorConfig
        
        # 模拟HTML内容
        sample_html = """
        <html>
            <head><title>测试新闻网站</title></head>
            <body>
                <h1>这是新闻标题</h1>
                <div class="content">
                    <p>这是新闻内容的第一段。</p>
                    <p>这是新闻内容的第二段。</p>
                </div>
                <div class="time">2025-07-24 10:00:00</div>
                <div class="author">测试作者</div>
                <a href="/news/1">新闻链接1</a>
                <a href="/news/2">新闻链接2</a>
            </body>
        </html>
        """
        
        scraper = NewsScraper()
        
        # 测试内容提取
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(sample_html, 'html.parser')
        
        selector_config = SelectorConfig(
            title_selector="h1",
            content_selector=".content"
        )
        
        # 模拟提取标题
        title_element = soup.select_one(selector_config.title_selector)
        if title_element:
            title = title_element.get_text(strip=True)
            print(f"✅ 提取标题: {title}")
        
        # 模拟提取内容
        content_elements = soup.select(selector_config.content_selector)
        if content_elements:
            content = content_elements[0].get_text(strip=True)
            print(f"✅ 提取内容: {content[:50]}...")
        
        print("✅ 抓取器功能演示完成")
        
    except ImportError as e:
        print(f"⚠️  无法导入抓取器模块: {e}")
    except Exception as e:
        print(f"⚠️  抓取器演示错误: {e}")


def demo_services():
    """演示服务层"""
    print("\n🔧 演示服务层...")
    
    try:
        from news_collector import services
        
        # 演示创建新闻源
        source_data = {
            "name": "演示新闻源",
            "url": "https://example.com/news",
            "remark": "用于演示的新闻源",
            "status": "active",
            "selector_config": {
                "title_selector": "h1",
                "content_selector": ".content",
                "time_selector": ".time"
            }
        }
        
        result = services.create_news_source(source_data)
        if result:
            source_id = result["id"]
            print(f"✅ 创建新闻源成功: ID {source_id}")
            
            # 获取新闻源
            source = services.get_news_source(source_id)
            print(f"✅ 获取新闻源: {source['name']}")
            
            # 获取新闻源列表
            sources_list = services.get_news_sources(page=1, size=5)
            print(f"✅ 新闻源列表: 共 {sources_list['total']} 个")
            
            # 演示创建任务
            task_data = {
                "task_name": "演示抓取任务",
                "kb_id": "demo_kb_001",
                "source_ids": [source_id],
                "auto_parse": True,
                "max_articles_per_source": 10
            }
            
            task_result = services.create_news_task(task_data)
            if task_result:
                print(f"✅ 创建抓取任务成功: ID {task_result['id']}")
        
        # 演示统计功能
        stats = services.get_statistics_overview()
        print(f"✅ 统计数据:")
        print(f"   新闻源数量: {stats.get('total_sources', 0)}")
        print(f"   任务数量: {stats.get('total_tasks', 0)}")
        print(f"   新闻数量: {stats.get('total_news', 0)}")
        
    except ImportError as e:
        print(f"⚠️  无法导入服务模块: {e}")
    except Exception as e:
        print(f"⚠️  服务层演示错误: {e}")


def demo_api_examples():
    """演示API调用示例"""
    print("\n🌐 API调用示例...")
    
    api_examples = [
        {
            "title": "获取新闻源列表",
            "method": "GET",
            "url": "/api/v1/news_collector/sources",
            "description": "获取所有新闻源的列表"
        },
        {
            "title": "创建新闻源",
            "method": "POST",
            "url": "/api/v1/news_collector/sources",
            "description": "创建新的新闻源",
            "body": {
                "name": "新闻源名称",
                "url": "https://example.com",
                "selector_config": {
                    "title_selector": "h1"
                }
            }
        },
        {
            "title": "创建抓取任务",
            "method": "POST",
            "url": "/api/v1/news_collector/tasks",
            "description": "创建新的抓取任务",
            "body": {
                "task_name": "任务名称",
                "kb_id": "知识库ID",
                "source_ids": [1, 2]
            }
        },
        {
            "title": "执行任务",
            "method": "POST",
            "url": "/api/v1/news_collector/tasks/1/execute",
            "description": "执行指定的抓取任务"
        },
        {
            "title": "获取统计数据",
            "method": "GET",
            "url": "/api/v1/news_collector/stats/overview",
            "description": "获取系统统计概览"
        }
    ]
    
    for example in api_examples:
        print(f"\n📡 {example['title']}")
        print(f"   方法: {example['method']}")
        print(f"   URL: {example['url']}")
        print(f"   描述: {example['description']}")
        
        if 'body' in example:
            print(f"   请求体: {json.dumps(example['body'], indent=2, ensure_ascii=False)}")


def demo_workflow():
    """演示完整工作流程"""
    print("\n🔄 完整工作流程演示...")
    
    workflow_steps = [
        "1. 创建知识库 → 用于存储抓取的新闻内容",
        "2. 添加新闻源 → 配置要抓取的新闻网站",
        "3. 验证新闻源 → 测试抓取规则是否正确",
        "4. 创建抓取任务 → 设置抓取参数和调度",
        "5. 执行任务 → 开始抓取新闻内容",
        "6. 监控进度 → 查看抓取和解析状态",
        "7. 管理内容 → 查看、编辑抓取的新闻",
        "8. 查看统计 → 分析抓取效果和性能"
    ]
    
    for step in workflow_steps:
        print(f"   {step}")
    
    print("\n💡 最佳实践:")
    best_practices = [
        "• 先验证新闻源配置再创建正式任务",
        "• 设置合理的抓取频率避免对目标网站造成压力",
        "• 定期清理无用的新闻内容和失效的新闻源",
        "• 监控系统性能和错误日志",
        "• 备份重要的配置和数据"
    ]
    
    for practice in best_practices:
        print(f"   {practice}")


def show_next_steps():
    """显示后续步骤"""
    print("\n🚀 后续步骤:")
    print("-" * 50)
    
    steps = [
        "1. 运行完整测试: python test_news_collector.py",
        "2. 初始化系统: python setup_news_collector.py",
        "3. 查看API文档: docs/news_collector_api_v1.1.md",
        "4. 配置环境变量: 编辑 .env 文件",
        "5. 启动服务: 集成到现有Flask应用或独立运行",
        "6. 访问API: http://localhost:5000/api/v1/news_collector/",
        "7. 创建第一个新闻源和抓取任务"
    ]
    
    for step in steps:
        print(f"   {step}")
    
    print("\n📚 更多资源:")
    resources = [
        "• README: NEWS_COLLECTOR_README.md",
        "• API文档: docs/news_collector_api_v1.1.md",
        "• 依赖包: news_collector_requirements.txt",
        "• 安装脚本: install_news_collector.bat (Windows)"
    ]
    
    for resource in resources:
        print(f"   {resource}")


async def main():
    """主演示函数"""
    print_banner()
    
    # 运行各个演示
    demo_models()
    demo_configuration()
    await demo_scraper()
    demo_services()
    demo_api_examples()
    demo_workflow()
    show_next_steps()
    
    print("\n" + "=" * 70)
    print("🎉 演示完成！")
    print("=" * 70)
    print("这个系统提供了完整的新闻抓取和管理功能。")
    print("您可以根据需要进行配置和扩展。")
    print("如有问题，请查看文档或联系开发团队。")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n👋 演示被用户中断")
    except Exception as e:
        print(f"\n❌ 演示过程中出现错误: {e}")
        print("请检查系统配置和依赖包安装情况")
