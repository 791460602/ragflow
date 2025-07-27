#!/usr/bin/env python3
"""
新闻收集器简单测试脚本

测试分离架构的基本功能
"""

import requests
import json

# 配置
API_BASE = "http://localhost:9222/api/v1/news_collector"
AUTH_TOKEN = "Bearer ragflow-M3NDJjZmEyNjYwZDExZjBhMTAwYjlkOD"
KB_ID = "dc1b46f86ac111f090d847774016f42b"

def test_crawl_only():
    """测试爬取功能"""
    print("🕷️  测试爬取功能...")
    
    data = {
        "sources": [
            {
                "name": "测试新闻源",
                "url": "https://example.com/news",
                "config": {"category": "测试"}
            }
        ],
        "crawler_type": "demo",
        "max_articles": 2,
        "save_to_disk": True
    }
    
    headers = {"Authorization": AUTH_TOKEN, "Content-Type": "application/json"}
    
    try:
        response = requests.post(f"{API_BASE}/crawl", json=data, headers=headers)
        result = response.json()
        
        if result.get("code") == 0:
            data = result["data"]
            print(f"✅ 爬取成功")
            print(f"   文章数: {data['total_articles']}")
            print(f"   爬取ID: {data['crawl_id']}")
            return data["articles"]
        else:
            print(f"❌ 爬取失败: {result}")
            return None
            
    except Exception as e:
        print(f"❌ 请求异常: {e}")
        return None

def test_upload_only(articles):
    """测试上传功能"""
    print("\n📤 测试上传功能...")
    
    data = {
        "kb_id": KB_ID,
        "articles": articles,
        "auto_parse": True
    }
    
    headers = {"Authorization": AUTH_TOKEN, "Content-Type": "application/json"}
    
    try:
        response = requests.post(f"{API_BASE}/upload", json=data, headers=headers)
        result = response.json()
        
        if result.get("code") == 0:
            data = result["data"]
            print(f"✅ 上传成功")
            print(f"   上传文件数: {data['uploaded_files']}")
            print(f"   解析已启动: {data.get('parse_started', False)}")
            return True
        else:
            print(f"❌ 上传失败: {result}")
            return False
            
    except Exception as e:
        print(f"❌ 请求异常: {e}")
        return False

def test_integrated():
    """测试一体化功能"""
    print("\n🔄 测试一体化功能...")
    
    data = {
        "kb_id": KB_ID,
        "sources": [
            {
                "name": "一体化测试源",
                "url": "https://example.com/integrated",
                "config": {}
            }
        ],
        "crawler_type": "demo",
        "max_articles": 2,
        "auto_parse": True
    }
    
    headers = {"Authorization": AUTH_TOKEN, "Content-Type": "application/json"}
    
    try:
        response = requests.post(f"{API_BASE}/crawl_and_upload", json=data, headers=headers)
        result = response.json()
        
        if result.get("code") == 0:
            data = result["data"]
            crawl_result = data["crawl_result"]
            upload_result = data["upload_result"]
            
            print(f"✅ 一体化操作成功")
            print(f"   爬取文章数: {crawl_result['total_articles']}")
            print(f"   上传文件数: {upload_result['uploaded_files']}")
            print(f"   最终状态: {data['status']}")
            return True
        else:
            print(f"❌ 一体化操作失败: {result}")
            return False
            
    except Exception as e:
        print(f"❌ 请求异常: {e}")
        return False

def test_framework_directly():
    """测试框架直接调用"""
    print("\n🔧 测试框架直接调用...")
    
    try:
        from api.news_crawler_framework import create_news_source, crawl_news
        
        # 创建新闻源
        sources = [create_news_source("直接调用测试", "https://test.com")]
        
        # 爬取新闻
        result = crawl_news(sources, "demo", 2)
        
        print(f"✅ 直接调用成功")
        print(f"   成功: {result.success}")
        print(f"   文章数: {len(result.articles)}")
        print(f"   错误数: {len(result.errors)}")
        
        return result.articles
        
    except Exception as e:
        print(f"❌ 直接调用失败: {e}")
        return None

def main():
    """主测试流程"""
    print("🎯 新闻收集器分离架构测试")
    print("=" * 50)
    
    # 测试1：分步操作
    print("\n📋 测试1: 分步操作")
    articles = test_crawl_only()
    if articles:
        upload_success = test_upload_only(articles)
        print(f"   分步操作结果: {'✅ 成功' if upload_success else '❌ 失败'}")
    
    # 测试2：一体化操作
    print("\n📋 测试2: 一体化操作")
    integrated_success = test_integrated()
    print(f"   一体化操作结果: {'✅ 成功' if integrated_success else '❌ 失败'}")
    
    # 测试3：直接调用框架
    print("\n📋 测试3: 直接调用框架")
    framework_articles = test_framework_directly()
    framework_success = framework_articles is not None
    print(f"   框架调用结果: {'✅ 成功' if framework_success else '❌ 失败'}")
    
    # 总结
    print("\n" + "=" * 50)
    print("📊 测试总结:")
    print(f"   分步操作: {'✅' if articles and upload_success else '❌'}")
    print(f"   一体化操作: {'✅' if integrated_success else '❌'}")
    print(f"   框架调用: {'✅' if framework_success else '❌'}")
    
    overall_success = all([
        articles and upload_success,
        integrated_success,
        framework_success
    ])
    
    print(f"\n🏆 总体结果: {'✅ 全部成功' if overall_success else '❌ 部分失败'}")
    
    if overall_success:
        print("\n🎉 新闻收集器分离架构工作正常！")
        print("💡 您可以开始开发自定义爬虫了")
    else:
        print("\n⚠️  存在问题，请检查日志和配置")

if __name__ == "__main__":
    main()
