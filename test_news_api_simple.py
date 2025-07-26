#!/usr/bin/env python3
"""
新闻收集器API简单测试
使用演示爬虫快速验证功能
"""

import requests
import json
import time
from datetime import datetime

# 配置信息
SERVER_URL = "http://localhost:9222"
API_BASE = f"{SERVER_URL}/api/v1/sdk/news"

# 请在这里填入您的认证信息
AUTH_TOKEN = "ImQ1MmVlOTM4NjljOTExZjBiZDc1ZjUwMjA2N2YzOTZjIg.aIRAAw.FxtamUfpaPCzyiz9uIv5r1r30Ng"
KNOWLEDGE_BASE_ID = "4ad3c16669c211f0818e254379a07586"

def get_headers():
    """获取请求头"""
    return {
        "Authorization": AUTH_TOKEN,
        "Content-Type": "application/json"
    }

def test_ping():
    """测试服务状态"""
    print("🔍 测试服务状态...")
    try:
        response = requests.get(f"{API_BASE}/ping", headers=get_headers(), timeout=10)
        print(f"状态码: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 服务状态: {json.dumps(result, indent=2, ensure_ascii=False)}")
            return True
        else:
            print(f"❌ 请求失败: {response.text}")
            return False
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return False

def test_get_crawlers():
    """测试获取爬虫类型"""
    print("\n🔍 测试获取爬虫类型...")
    try:
        response = requests.get(f"{API_BASE}/crawlers", headers=get_headers(), timeout=10)
        print(f"状态码: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 爬虫类型: {json.dumps(result, indent=2, ensure_ascii=False)}")
            return True
        else:
            print(f"❌ 请求失败: {response.text}")
            return False
    except Exception as e:
        print(f"❌ 请求异常: {e}")
        return False

def test_create_demo_task():
    """测试创建演示任务"""
    print("\n🔍 测试创建演示任务...")
    
    # 使用演示爬虫的任务配置
    task_data = {
        "task_name": f"演示任务_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "kb_id": KNOWLEDGE_BASE_ID,
        "crawler_type": "demo",
        "max_articles": 3,
        "sources": [
            {
                "name": "新浪科技演示",
                "url": "https://tech.sina.com.cn/"
            },
            {
                "name": "网易科技演示", 
                "url": "https://tech.163.com/"
            }
        ]
    }
    
    try:
        response = requests.post(
            f"{API_BASE}/tasks", 
            headers=get_headers(), 
            json=task_data,
            timeout=30
        )
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 任务创建成功: {json.dumps(result, indent=2, ensure_ascii=False)}")
            return result.get('data', {}).get('task_id')
        else:
            print(f"❌ 任务创建失败: {response.text}")
            return None
    except Exception as e:
        print(f"❌ 请求异常: {e}")
        return None

def test_execute_task(task_id):
    """测试执行任务"""
    print(f"\n🔍 测试执行任务: {task_id}")
    
    try:
        response = requests.post(
            f"{API_BASE}/tasks/{task_id}/execute",
            headers=get_headers(),
            timeout=60
        )
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 任务执行结果: {json.dumps(result, indent=2, ensure_ascii=False)}")
            return True
        else:
            print(f"❌ 任务执行失败: {response.text}")
            return False
    except Exception as e:
        print(f"❌ 请求异常: {e}")
        return False

def test_get_task_status(task_id):
    """测试获取任务状态"""
    print(f"\n🔍 测试获取任务状态: {task_id}")
    
    try:
        response = requests.get(
            f"{API_BASE}/tasks/{task_id}",
            headers=get_headers(),
            timeout=30
        )
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 任务状态: {json.dumps(result, indent=2, ensure_ascii=False)}")
            return True
        else:
            print(f"❌ 获取状态失败: {response.text}")
            return False
    except Exception as e:
        print(f"❌ 请求异常: {e}")
        return False

def main():
    """主测试流程"""
    print("🚀 新闻收集器API简单测试")
    print("=" * 50)
    print(f"服务器: {SERVER_URL}")
    print(f"知识库ID: {KNOWLEDGE_BASE_ID}")
    print("=" * 50)
    
    # 检查配置
    if not AUTH_TOKEN or not KNOWLEDGE_BASE_ID:
        print("❌ 请先配置AUTH_TOKEN和KNOWLEDGE_BASE_ID")
        return False
    
    success_count = 0
    total_tests = 5
    
    # 1. 测试服务状态
    if test_ping():
        success_count += 1
    
    # 2. 测试获取爬虫类型
    if test_get_crawlers():
        success_count += 1
    
    # 3. 测试创建任务
    task_id = test_create_demo_task()
    if task_id:
        success_count += 1
        
        # 4. 测试执行任务
        if test_execute_task(task_id):
            success_count += 1
        
        # 5. 测试获取任务状态
        if test_get_task_status(task_id):
            success_count += 1
    
    print("\n" + "=" * 50)
    print(f"📊 测试结果: {success_count}/{total_tests} 通过")
    
    if success_count == total_tests:
        print("🎉 所有测试通过！")
        print("\n💡 接下来可以:")
        print("1. 在RAGFlow前端查看生成的文档")
        print("2. 测试更多爬虫类型")
        print("3. 集成真实的爬虫工具")
        return True
    else:
        print("❌ 部分测试失败，请检查错误信息")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
