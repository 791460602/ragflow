#!/usr/bin/env python3
"""
新闻抓取系统测试脚本

测试和演示新闻抓取系统的各种功能
"""

import os
import sys
import asyncio
import json
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / 'sdk' / 'python'))

# 配置日志
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_news_scraper():
    """测试新闻抓取器"""
    print("\n🔍 测试新闻抓取器...")
    
    try:
        from news_collector.scraper import NewsScraper
        from news_collector.models import NewsSource, SelectorConfig
        
        # 创建测试新闻源
        test_source = NewsSource(
            id=1,
            name="新浪科技测试",
            url="https://tech.sina.com.cn/",
            selector_config=SelectorConfig(
                title_selector="h1",
                content_selector=".article-content",
                time_selector=".time",
                link_selector="a"
            )
        )
        
        # 测试抓取
        async with NewsScraper() as scraper:
            print(f"📡 开始抓取: {test_source.url}")
            
            # 验证新闻源
            validation_result = await scraper.validate_news_source(
                test_source.url, 
                test_source.selector_config
            )
            
            print(f"✅ 验证结果: {validation_result}")
            
            if validation_result.get('valid'):
                # 抓取文章
                articles = await scraper.scrape_news_source(test_source, max_articles=5)
                print(f"📰 抓取到 {len(articles)} 篇文章")
                
                for i, article in enumerate(articles[:3]):  # 只显示前3篇
                    print(f"  {i+1}. {article.title[:50]}...")
                    print(f"     📅 {article.publish_time}")
                    print(f"     🔗 {article.url}")
                    print(f"     📝 {len(article.content_text)} 字符")
                    
            return True
            
    except Exception as e:
        print(f"❌ 抓取器测试失败: {e}")
        return False


async def test_news_manager():
    """测试新闻管理器"""
    print("\n📋 测试新闻管理器...")
    
    try:
        # 模拟RAGFlow客户端
        class MockRAGFlowClient:
            def get_dataset(self, kb_id):
                return MockDataset(kb_id)
            
            def create_dataset(self, name, description="", chunk_method="naive"):
                return MockDataset(f"kb_{name}")
            
            def list_datasets(self):
                return [MockDataset("kb_test_1"), MockDataset("kb_test_2")]
        
        class MockDataset:
            def __init__(self, kb_id):
                self.id = kb_id
                self.name = f"测试知识库_{kb_id}"
                self.description = "测试用知识库"
            
            def upload_folder(self, folder_path, parent_id="", auto_parse=True):
                return {
                    "upload_result": {"data": [{"id": "doc_123", "name": "test.txt"}]},
                    "convert_result": {"data": [{"id": "doc_123"}]},
                    "parse_result": {"status": "started", "document_count": 1}
                }
        
        from news_collector.manager import NewsManager
        from news_collector.models import NewsTask, NewsSource, SelectorConfig
        
        # 创建管理器
        mock_client = MockRAGFlowClient()
        
        async with NewsManager(mock_client) as manager:
            print("✅ 新闻管理器初始化成功")
            
            # 测试获取知识库
            kbs = manager.get_knowledge_bases()
            print(f"📚 找到 {len(kbs)} 个知识库")
            
            # 测试创建知识库
            new_kb = manager.create_knowledge_base("测试新闻库", "用于测试的新闻知识库")
            if new_kb:
                print(f"✅ 创建知识库成功: {new_kb.name}")
            
            return True
            
    except Exception as e:
        print(f"❌ 管理器测试失败: {e}")
        return False


def test_services():
    """测试服务层"""
    print("\n🔧 测试服务层...")
    
    try:
        from news_collector import services
        
        # 测试创建新闻源
        source_data = {
            "name": "测试新闻源",
            "url": "https://example.com/news",
            "remark": "测试用新闻源",
            "status": "active",
            "selector_config": {
                "title_selector": "h1",
                "content_selector": ".content",
                "time_selector": ".time",
                "author_selector": ".author",
                "link_selector": "a"
            }
        }
        
        result = services.create_news_source(source_data)
        if result:
            source_id = result["id"]
            print(f"✅ 创建新闻源成功: ID {source_id}")
            
            # 测试获取新闻源
            source = services.get_news_source(source_id)
            if source:
                print(f"✅ 获取新闻源成功: {source['name']}")
            
            # 测试更新新闻源
            update_result = services.update_news_source(source_id, {"remark": "更新后的备注"})
            if update_result:
                print("✅ 更新新闻源成功")
            
            # 测试获取新闻源列表
            sources_list = services.get_news_sources(page=1, page_size=10)
            print(f"✅ 获取新闻源列表成功: 共 {sources_list['total']} 个")
            
            return True
        else:
            print("❌ 创建新闻源失败")
            return False
            
    except Exception as e:
        print(f"❌ 服务层测试失败: {e}")
        return False


def test_configuration():
    """测试配置系统"""
    print("\n⚙️  测试配置系统...")
    
    try:
        from news_collector.config import get_config, update_config, get_selector_config_for_domain
        
        # 测试获取配置
        ragflow_config = get_config("ragflow")
        print(f"✅ RAGFlow配置: {ragflow_config}")
        
        # 测试更新配置
        update_config("test.value", "测试值")
        test_value = get_config("test.value")
        print(f"✅ 配置更新测试: {test_value}")
        
        # 测试域名选择器配置
        sina_config = get_selector_config_for_domain("sina.com.cn")
        print(f"✅ 新浪选择器配置: {sina_config}")
        
        return True
        
    except Exception as e:
        print(f"❌ 配置系统测试失败: {e}")
        return False


def test_data_models():
    """测试数据模型"""
    print("\n📊 测试数据模型...")
    
    try:
        from news_collector.models import NewsSource, NewsTask, NewsContent, SelectorConfig
        from datetime import datetime
        
        # 测试选择器配置
        selector = SelectorConfig(
            title_selector="h1.title",
            content_selector=".article-content"
        )
        
        # 测试新闻源
        source = NewsSource(
            id=1,
            name="测试新闻源",
            url="https://example.com",
            selector_config=selector,
            created_at=datetime.now()
        )
        
        # 测试序列化
        source_dict = source.to_dict()
        print(f"✅ 新闻源序列化: {source_dict['name']}")
        
        # 测试反序列化
        source_from_dict = NewsSource.from_dict(source_dict)
        print(f"✅ 新闻源反序列化: {source_from_dict.name}")
        
        # 测试新闻内容
        content = NewsContent(
            title="测试新闻标题",
            content_text="这是测试新闻的内容...",
            url="https://example.com/news/1",
            source_id=1
        )
        
        content_dict = content.to_dict()
        print(f"✅ 新闻内容序列化: {content_dict['title']}")
        
        return True
        
    except Exception as e:
        print(f"❌ 数据模型测试失败: {e}")
        return False


async def run_all_tests():
    """运行所有测试"""
    print("🧪 开始运行新闻抓取系统测试套件...")
    
    tests = [
        ("配置系统", test_configuration),
        ("数据模型", test_data_models),
        ("服务层", test_services),
        ("新闻管理器", test_news_manager),
        ("新闻抓取器", test_news_scraper),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n{'='*60}")
        print(f"🔍 测试: {test_name}")
        print('='*60)
        
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            
            results.append((test_name, result))
            
            if result:
                print(f"✅ {test_name} 测试通过")
            else:
                print(f"❌ {test_name} 测试失败")
                
        except Exception as e:
            print(f"❌ {test_name} 测试异常: {e}")
            results.append((test_name, False))
    
    # 打印测试结果汇总
    print(f"\n{'='*60}")
    print("📊 测试结果汇总")
    print('='*60)
    
    passed = 0
    failed = 0
    
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name:<20} {status}")
        
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\n📈 总计: {passed} 个通过, {failed} 个失败")
    
    if failed == 0:
        print("🎉 所有测试都通过了！系统功能正常。")
    else:
        print("⚠️  部分测试失败，请检查相关功能。")
    
    return failed == 0


def show_usage_examples():
    """显示使用示例"""
    print("\n📚 使用示例:")
    print("-" * 60)
    
    examples = [
        {
            "title": "1. 创建新闻源",
            "code": '''
from news_collector import services

source_data = {
    "name": "新浪科技",
    "url": "https://tech.sina.com.cn/",
    "remark": "新浪科技频道",
    "selector_config": {
        "title_selector": "h1",
        "content_selector": ".article-content",
        "time_selector": ".time"
    }
}

result = services.create_news_source(source_data)
print(f"新闻源ID: {result['id']}")
'''
        },
        {
            "title": "2. 创建抓取任务",
            "code": '''
task_data = {
    "task_name": "每日科技新闻抓取",
    "kb_id": "your_knowledge_base_id",
    "source_ids": [1, 2],  # 新闻源ID列表
    "auto_parse": True,
    "max_articles_per_source": 50
}

result = services.create_news_task(task_data)
print(f"任务ID: {result['id']}")
'''
        },
        {
            "title": "3. 执行抓取任务",
            "code": '''
import asyncio

async def run_task():
    result = await services.execute_news_task(task_id=1)
    print(f"任务状态: {result['status']}")
    print(f"抓取文章数: {len(result.get('articles', []))}")

asyncio.run(run_task())
'''
        },
        {
            "title": "4. API调用示例",
            "code": '''
import requests

# 获取新闻源列表
response = requests.get("http://localhost:5000/api/v1/news_collector/sources")
sources = response.json()

# 创建新闻源
new_source = {
    "name": "测试新闻源",
    "url": "https://example.com/news",
    "selector_config": {"title_selector": "h1"}
}
response = requests.post(
    "http://localhost:5000/api/v1/news_collector/sources",
    json=new_source
)
'''
        }
    ]
    
    for example in examples:
        print(f"\n{example['title']}")
        print(example['code'])


async def main():
    """主函数"""
    print("🚀 新闻抓取与管理系统测试")
    print("=" * 60)
    
    # 运行测试
    success = await run_all_tests()
    
    # 显示使用示例
    show_usage_examples()
    
    print("\n💡 提示:")
    print("- 请确保已安装必要的依赖包（aiohttp, beautifulsoup4, flask等）")
    print("- 请确保RAGFlow服务正在运行")
    print("- 查看 setup_news_collector.py 了解如何集成到现有项目")
    print("- 查看 docs/news_collector_api_v1.1.md 了解完整的API文档")
    
    return success


if __name__ == "__main__":
    success = asyncio.run(main())
    
    if success:
        print("\n🎉 测试完成，系统功能正常！")
    else:
        print("\n⚠️  测试发现问题，请检查相关功能。")
        sys.exit(1)
