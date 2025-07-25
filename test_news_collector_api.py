#!/usr/bin/env python3
"""
新闻收集器API测试脚本
"""

import requests
import json

# 服务器配置
SERVER_URL = "http://localhost:9380"
API_BASE = f"{SERVER_URL}/v1/news_collector"

# 测试数据
test_source = {
    "name": "示例新闻网站",
    "url": "https://example.com/news",
    "remark": "这是一个测试新闻源"
}


def test_ping():
    """测试服务健康检查"""
    print("测试服务健康检查...")
    try:
        response = requests.get(f"{API_BASE}/ping")
        print(f"健康检查响应: {response.status_code}")
        if response.status_code == 200:
            print(f"响应内容: {response.json()}")
        return response.status_code == 200
    except Exception as e:
        print(f"健康检查失败: {e}")
        return False


def test_create_source():
    """测试创建新闻源"""
    print("\n测试创建新闻源...")
    try:
        response = requests.post(
            f"{API_BASE}/sources",
            json=test_source,
            headers={"Content-Type": "application/json"}
        )
        print(f"创建新闻源响应: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"创建成功: {result}")
            return result.get("data", {}).get("id")
        else:
            print(f"创建失败: {response.text}")
        return None
    except Exception as e:
        print(f"创建新闻源失败: {e}")
        return None


def test_get_sources():
    """测试获取新闻源列表"""
    print("\n测试获取新闻源列表...")
    try:
        response = requests.get(f"{API_BASE}/sources")
        print(f"获取新闻源列表响应: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"新闻源列表: {result}")
            return True
        else:
            print(f"获取失败: {response.text}")
        return False
    except Exception as e:
        print(f"获取新闻源列表失败: {e}")
        return False


def test_get_statistics():
    """测试获取统计信息"""
    print("\n测试获取统计信息...")
    try:
        response = requests.get(f"{API_BASE}/statistics")
        print(f"获取统计信息响应: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"统计信息: {result}")
            return True
        else:
            print(f"获取失败: {response.text}")
        return False
    except Exception as e:
        print(f"获取统计信息失败: {e}")
        return False


def main():
    """主测试函数"""
    print("开始测试新闻收集器API...")
    
    # 测试健康检查
    if not test_ping():
        print("服务不可用，请确保RAGFlow服务正在运行")
        return
    
    # 注意：以下测试需要认证，可能会失败
    print("\n注意：以下测试需要用户认证，可能会返回401错误")
    
    # 测试获取统计信息
    test_get_statistics()
    
    # 测试获取新闻源列表
    test_get_sources()
    
    # 测试创建新闻源
    source_id = test_create_source()
    
    print("\n测试完成！")
    print("如需完整测试，请:")
    print("1. 启动RAGFlow服务")
    print("2. 登录并获取访问令牌")
    print("3. 在请求头中添加认证信息")


if __name__ == "__main__":
    main()
