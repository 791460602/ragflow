#!/usr/bin/env python3
"""
快速测试新闻收集器API
"""

import requests
import json

def test_news_collector_api():
    """测试新闻收集器API是否正常工作"""
    
    BASE_URL = "http://localhost:9380"
    API_VERSION = "v1"
    
    # 测试用认证令牌（需要替换为实际值）
    headers = {
        "Authorization": "Bearer ragflow-M3NDJjZmEyNjYwZDExZjBhMTAwYjlkOD",
        # "Authorization": "IjFhYmUxODAwNmFjMTExZjA5MGQ4NDc3NzQwMTZmNDJiIg.aIXe3Q.NqpCPusrvTkokQf68Uz1SC9vh0k",
        "Content-Type": "application/json"
    }
    
    print("🧪 测试新闻收集器API...")
    
    # 1. 测试ping接口
    try:
        response = requests.get(f"{BASE_URL}/api/{API_VERSION}/ping", headers=headers)
        print(f"Ping响应状态: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"服务状态: {data.get('data', {}).get('status', 'unknown')}")
        else:
            print(f"响应内容: {response.text}")
    except Exception as e:
        print(f"Ping测试失败: {e}")
    
    # 2. 测试爬虫类型接口
    try:
        response = requests.get(f"{BASE_URL}/api/{API_VERSION}/crawlers", headers=headers)
        print(f"\n爬虫类型响应状态: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            crawlers = data.get('data', {}).get('crawlers', [])
            print("支持的爬虫类型:")
            for crawler in crawlers:
                print(f"  - {crawler.get('type')}: {crawler.get('description')}")
        else:
            print(f"响应内容: {response.text}")
    except Exception as e:
        print(f"爬虫类型测试失败: {e}")

if __name__ == "__main__":
    test_news_collector_api()
