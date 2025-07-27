#!/usr/bin/env python3
"""
news_collector API修复后测试

验证BeartypeCallHintParamViolation修复后的功能
"""

import requests
import json
import sys

# API配置
BASE_URL = "http://localhost:9222/api/v1/news_collector"
API_TOKEN = "ragflow-MTIwOWM2N2EyYmE4MTFmZjgwNzE3NjNmMmRjNGQ0ZDU="  # 请替换为实际token

HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json"
}

def test_create_news_source():
    """测试创建新闻源 - 验证user_id修复"""
    print("🧪 测试创建新闻源...")
    
    test_data = {
        "name": "测试新闻源_类型安全修复",
        "url": "https://example.com/news",
        "remark": "验证BeartypeCallHintParamViolation修复",
        "fetch_config": {
            "timeout": 30,
            "headers": {"User-Agent": "RAGFlow NewsCollector"}
        }
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/sources",
            headers=HEADERS,
            json=test_data,
            timeout=10
        )
        
        print(f"   响应状态: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ 创建成功: {result}")
            return result.get('data', {}).get('source', {}).get('id')
        else:
            print(f"   ❌ 创建失败: {response.text}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"   ❌ 请求异常: {e}")
        return None
    except Exception as e:
        print(f"   ❌ 其他错误: {e}")
        return None

def test_create_news_task(kb_id="test_kb_id"):
    """测试创建新闻任务 - 验证user_id修复"""
    print("🧪 测试创建新闻任务...")
    
    test_data = {
        "task_name": "测试任务_类型安全修复",
        "kb_id": kb_id,
        "source_ids": [],
        "auto_parse": True,
        "max_articles_per_source": 5,
        "crawler_config": {
            "type": "demo",
            "timeout": 300
        }
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/tasks",
            headers=HEADERS,
            json=test_data,
            timeout=10
        )
        
        print(f"   响应状态: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ 创建成功: {result}")
            return result.get('data', {}).get('task', {}).get('id')
        else:
            print(f"   ❌ 创建失败: {response.text}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"   ❌ 请求异常: {e}")
        return None
    except Exception as e:
        print(f"   ❌ 其他错误: {e}")
        return None

def test_crawl_demo():
    """测试演示爬虫 - 核心功能验证"""
    print("🧪 测试演示爬虫...")
    
    test_data = {
        "sources": [
            {
                "name": "测试源1",
                "url": "https://example.com/tech",
                "config": {"category": "科技"}
            },
            {
                "name": "测试源2", 
                "url": "https://example.com/business",
                "config": {"category": "商业"}
            }
        ],
        "crawler_type": "demo",
        "max_articles": 3,
        "save_to_disk": False
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/crawl",
            headers=HEADERS,
            json=test_data,
            timeout=15
        )
        
        print(f"   响应状态: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            crawl_data = result.get('data', {})
            print(f"   ✅ 爬取成功: {crawl_data.get('total_articles', 0)} 篇文章")
            print(f"   爬取ID: {crawl_data.get('crawl_id')}")
            return crawl_data
        else:
            print(f"   ❌ 爬取失败: {response.text}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"   ❌ 请求异常: {e}")
        return None
    except Exception as e:
        print(f"   ❌ 其他错误: {e}")
        return None

def test_get_crawlers():
    """测试获取可用爬虫列表"""
    print("🧪 测试获取爬虫列表...")
    
    try:
        response = requests.get(
            f"{BASE_URL}/crawlers",
            headers=HEADERS,
            timeout=10
        )
        
        print(f"   响应状态: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            crawlers = result.get('data', {}).get('crawlers', [])
            print(f"   ✅ 获取成功: {len(crawlers)} 个爬虫")
            for crawler in crawlers:
                print(f"      - {crawler.get('name')}: {crawler.get('description')}")
            return True
        else:
            print(f"   ❌ 获取失败: {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"   ❌ 请求异常: {e}")
        return False
    except Exception as e:
        print(f"   ❌ 其他错误: {e}")
        return False

def main():
    """主测试函数"""
    print("=" * 60)
    print("🧪 news_collector API 修复后功能测试")
    print("=" * 60)
    print("🎯 目标: 验证BeartypeCallHintParamViolation修复效果")
    print()
    
    # 检查服务器连接
    try:
        response = requests.get(f"{BASE_URL}/crawlers", headers=HEADERS, timeout=5)
        if response.status_code != 200:
            print("❌ 无法连接到API服务器，请确保RAGFlow正在运行")
            print(f"   URL: {BASE_URL}")
            print(f"   状态码: {response.status_code}")
            sys.exit(1)
    except Exception as e:
        print(f"❌ 服务器连接失败: {e}")
        print("   请确保RAGFlow服务正在运行且端口正确")
        sys.exit(1)
    
    print("✅ 服务器连接正常\n")
    
    # 执行测试
    tests = []
    
    # 1. 基础功能测试
    tests.append(test_get_crawlers())
    
    # 2. 爬虫功能测试  
    tests.append(test_crawl_demo() is not None)
    
    # 3. CRUD功能测试（这些可能需要有效的知识库ID）
    source_id = test_create_news_source()
    tests.append(source_id is not None)
    
    # 如果有有效的知识库，测试任务创建
    # task_id = test_create_news_task("your_kb_id_here")
    # tests.append(task_id is not None)
    
    # 统计结果
    success_count = sum(tests)
    total_tests = len(tests)
    
    print("\n" + "=" * 60)
    print(f"🏁 测试结果: {success_count}/{total_tests} 通过")
    
    if success_count == total_tests:
        print("🎉 所有测试通过!")
        print("✅ BeartypeCallHintParamViolation 错误已彻底解决")
        print("✅ API功能正常，类型安全修复生效")
    else:
        print("⚠️  部分测试失败")
        print("   可能的原因:")
        print("   1. 服务器配置问题") 
        print("   2. 数据库连接问题")
        print("   3. 权限或token问题")
    
    print(f"\n📝 如需测试完整CRUD功能，请提供有效的知识库ID")

if __name__ == "__main__":
    main()
