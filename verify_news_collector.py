#!/usr/bin/env python3
"""
新闻收集器SDK规范验证脚本

验证重构后的API是否正常工作
"""

import requests
import json
import sys

def test_api_endpoints():
    """测试API端点"""
    
    # 配置
    BASE_URL = "http://localhost:9222/api/v1"
    AUTH_TOKEN = "Bearer ragflow-xxx"  # 请替换为实际token
    
    headers = {
        "Authorization": AUTH_TOKEN,
        "Content-Type": "application/json"
    }
    
    print("🔍 新闻收集器SDK规范验证")
    print("=" * 50)
    
    # 测试端点列表
    test_endpoints = [
        ("GET", "/news_collector/crawlers", "获取可用爬虫"),
        ("GET", "/news_collector/sources", "获取新闻源列表"),
        ("GET", "/news_collector/tasks", "获取任务列表"),
        ("GET", "/news_collector/contents", "获取内容列表"),
        ("GET", "/news_collector/statistics", "获取统计信息"),
    ]
    
    for method, endpoint, description in test_endpoints:
        print(f"\n📋 测试: {description}")
        print(f"   {method} {endpoint}")
        
        try:
            url = f"{BASE_URL}{endpoint}"
            
            if method == "GET":
                response = requests.get(url, headers=headers, timeout=10)
            elif method == "POST":
                response = requests.post(url, headers=headers, json={}, timeout=10)
            else:
                print(f"   ⚠️  不支持的方法: {method}")
                continue
            
            print(f"   状态码: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    if data.get('code') == 0:
                        print(f"   ✅ 成功: {data.get('message', 'OK')}")
                    else:
                        print(f"   ❌ 业务错误: {data.get('message', '未知错误')}")
                except json.JSONDecodeError:
                    print(f"   ⚠️  响应不是有效JSON")
            elif response.status_code == 401:
                print(f"   🔒 认证失败: 请检查token")
            elif response.status_code == 404:
                print(f"   ❓ 端点不存在: 可能API未正确加载")
            else:
                print(f"   ❌ HTTP错误: {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            print(f"   💥 连接失败: RAGFlow服务未运行")
            break
        except requests.exceptions.Timeout:
            print(f"   ⏰ 请求超时")
        except Exception as e:
            print(f"   💥 异常: {str(e)}")
    
    print(f"\n{'=' * 50}")
    print("📊 验证完成")
    print("\n💡 提示:")
    print("   - 如果认证失败，请更新AUTH_TOKEN")
    print("   - 如果端点不存在，请确认RAGFlow服务正常运行")
    print("   - 如果连接失败，请检查RAGFlow服务状态")

def test_crawl_api():
    """测试爬虫API"""
    
    BASE_URL = "http://localhost:9222/api/v1"
    AUTH_TOKEN = "Bearer ragflow-xxx"  # 请替换为实际token
    
    headers = {
        "Authorization": AUTH_TOKEN,
        "Content-Type": "application/json"
    }
    
    print(f"\n🔧 测试爬虫功能")
    print("-" * 30)
    
    # 测试数据
    crawl_data = {
        "sources": [
            {
                "name": "测试新闻源",
                "url": "https://example.com",
                "config": {"category": "测试"}
            }
        ],
        "crawler_type": "demo",
        "max_articles": 3
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/news_collector/crawl",
            headers=headers,
            json=crawl_data,
            timeout=30
        )
        
        print(f"爬虫API状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            if data.get('code') == 0:
                result = data.get('data', {})
                print(f"✅ 爬虫测试成功:")
                print(f"   - 爬取ID: {result.get('crawl_id', 'N/A')}")
                print(f"   - 文章数量: {result.get('total_articles', 0)}")
                print(f"   - 成功状态: {result.get('success', False)}")
            else:
                print(f"❌ 爬虫测试失败: {data.get('message')}")
        else:
            print(f"❌ HTTP错误: {response.status_code}")
            
    except Exception as e:
        print(f"💥 爬虫测试异常: {str(e)}")

if __name__ == "__main__":
    # 基础API验证
    test_api_endpoints()
    
    # 爬虫功能测试
    test_crawl_api()
    
    print(f"\n🎯 验证脚本完成")
    print("请根据测试结果检查系统状态")
