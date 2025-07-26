#!/usr/bin/env python3
"""
新闻收集器功能测试脚本

用于测试新闻收集器的各项功能
"""

import sys
import os
import json
import requests

# 测试配置
API_BASE_URL = "http://localhost:9380/api/v1"
TEST_TOKEN = "your_test_token_here"

def test_crawlers():
    """测试获取支持的爬虫列表"""
    print("测试获取支持的爬虫...")
    
    url = f"{API_BASE_URL}/crawlers"
    headers = {"Authorization": TEST_TOKEN}
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            print(f"✓ 获取爬虫列表成功: {data}")
            return True
        else:
            print(f"✗ 获取爬虫列表失败: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"✗ 请求失败: {str(e)}")
        return False

def test_create_source():
    """测试创建新闻源"""
    print("测试创建新闻源...")
    
    url = f"{API_BASE_URL}/sources"
    headers = {
        "Authorization": TEST_TOKEN,
        "Content-Type": "application/json"
    }
    
    data = {
        "name": "测试新闻源",
        "url": "https://news.example.com",
        "remark": "这是一个测试新闻源",
        "fetch_config": {
            "timeout": 30,
            "encoding": "utf-8"
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            result = response.json()
            print(f"✓ 创建新闻源成功: {result}")
            return result.get("data", {}).get("id")
        else:
            print(f"✗ 创建新闻源失败: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"✗ 请求失败: {str(e)}")
        return None

def test_list_sources():
    """测试获取新闻源列表"""
    print("测试获取新闻源列表...")
    
    url = f"{API_BASE_URL}/sources"
    headers = {"Authorization": TEST_TOKEN}
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            print(f"✓ 获取新闻源列表成功: {data}")
            return True
        else:
            print(f"✗ 获取新闻源列表失败: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"✗ 请求失败: {str(e)}")
        return False

def test_create_task(source_id):
    """测试创建抓取任务"""
    print("测试创建抓取任务...")
    
    url = f"{API_BASE_URL}/tasks"
    headers = {
        "Authorization": TEST_TOKEN,
        "Content-Type": "application/json"
    }
    
    data = {
        "task_name": "测试抓取任务",
        "kb_id": "test_kb_id",  # 需要替换为实际的知识库ID
        "source_ids": [source_id] if source_id else [],
        "auto_parse": True,
        "max_articles_per_source": 5,
        "crawler_config": {
            "type": "demo",
            "timeout": 300,
            "output_format": "markdown"
        }
    }
    
    try:
        response = requests.post(url, headers=headers, json=data)
        if response.status_code == 200:
            result = response.json()
            print(f"✓ 创建抓取任务成功: {result}")
            return result.get("data", {}).get("id")
        else:
            print(f"✗ 创建抓取任务失败: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"✗ 请求失败: {str(e)}")
        return None

def test_execute_task(task_id):
    """测试执行抓取任务"""
    print("测试执行抓取任务...")
    
    url = f"{API_BASE_URL}/tasks/{task_id}/execute"
    headers = {
        "Authorization": TEST_TOKEN,
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(url, headers=headers)
        if response.status_code == 200:
            result = response.json()
            print(f"✓ 执行抓取任务成功: {result}")
            return True
        else:
            print(f"✗ 执行抓取任务失败: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"✗ 请求失败: {str(e)}")
        return False

def test_get_statistics():
    """测试获取统计数据"""
    print("测试获取统计数据...")
    
    url = f"{API_BASE_URL}/statistics"
    headers = {"Authorization": TEST_TOKEN}
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            print(f"✓ 获取统计数据成功: {data}")
            return True
        else:
            print(f"✗ 获取统计数据失败: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"✗ 请求失败: {str(e)}")
        return False

def test_ping():
    """测试连通性"""
    print("测试API连通性...")
    
    url = f"{API_BASE_URL}/ping"
    headers = {"Authorization": TEST_TOKEN}
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            print(f"✓ API连通性测试成功: {data}")
            return True
        else:
            print(f"✗ API连通性测试失败: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"✗ 请求失败: {str(e)}")
        return False

def main():
    """主测试函数"""
    print("=" * 50)
    print("新闻收集器功能测试")
    print("=" * 50)
    
    if len(sys.argv) > 1:
        global TEST_TOKEN
        TEST_TOKEN = sys.argv[1]
        print(f"使用提供的token: {TEST_TOKEN[:20]}...")
    else:
        print("未提供token，使用默认测试token")
        print("用法: python test_news_collector.py <your_token>")
    
    print()
    
    # 运行测试
    tests_passed = 0
    total_tests = 0
    
    # 测试1: API连通性
    total_tests += 1
    if test_ping():
        tests_passed += 1
    print()
    
    # 测试2: 获取爬虫列表
    total_tests += 1
    if test_crawlers():
        tests_passed += 1
    print()
    
    # 测试3: 创建新闻源
    total_tests += 1
    source_id = test_create_source()
    if source_id:
        tests_passed += 1
    print()
    
    # 测试4: 获取新闻源列表
    total_tests += 1
    if test_list_sources():
        tests_passed += 1
    print()
    
    # 测试5: 创建抓取任务
    total_tests += 1
    task_id = test_create_task(source_id)
    if task_id:
        tests_passed += 1
    print()
    
    # 测试6: 执行抓取任务
    if task_id:
        total_tests += 1
        if test_execute_task(task_id):
            tests_passed += 1
        print()
    
    # 测试7: 获取统计数据
    total_tests += 1
    if test_get_statistics():
        tests_passed += 1
    print()
    
    # 总结
    print("=" * 50)
    print(f"测试完成: {tests_passed}/{total_tests} 个测试通过")
    print("=" * 50)
    
    if tests_passed == total_tests:
        print("🎉 所有测试通过！新闻收集器功能正常。")
        sys.exit(0)
    else:
        print("⚠️  部分测试失败，请检查配置和服务状态。")
        sys.exit(1)

if __name__ == "__main__":
    main()
