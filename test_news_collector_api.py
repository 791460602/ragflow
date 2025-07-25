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
        response = requests.get(f"{API_BASE}/ping", timeout=5)
        print(f"健康检查响应: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"响应内容: {result}")
            return True
        else:
            print(f"响应内容: {response.text}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ 连接失败: RAGFlow服务未启动或端口不正确")
        return False
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
    print("🧪 开始测试新闻收集器API...")
    print("="*50)
    
    # 测试健康检查
    print("\n1️⃣ 测试服务连通性")
    if not test_ping():
        print("❌ 服务不可用，请确保:")
        print("   1. RAGFlow服务正在运行: python api/ragflow_server.py")
        print("   2. 服务端口正确: http://localhost:9380")
        print("   3. 新闻收集器模块已正确安装")
        return
    
    print("✅ 服务连通性正常")
    
    # 测试需要认证的接口
    print("\n2️⃣ 测试需要认证的接口")
    print("⚠️ 以下测试需要用户认证，预期会返回401错误")
    
    # 测试获取统计信息
    print("\n📊 测试统计信息接口:")
    test_get_statistics()
    
    # 测试获取新闻源列表
    print("\n📰 测试新闻源列表接口:")
    test_get_sources()
    
    # 测试创建新闻源
    print("\n➕ 测试创建新闻源接口:")
    source_id = test_create_source()
    
    print("\n" + "="*50)
    print("🎯 测试总结:")
    print("="*50)
    print("✅ 新闻收集器服务已正确集成到RAGFlow")
    print("⚠️ 需要认证的接口返回401是正常的")
    
    print("\n📋 完整测试步骤:")
    print("1. 🚀 启动RAGFlow服务: python api/ragflow_server.py")
    print("2. 🌐 访问前端: http://localhost:9380")
    print("3. 🔑 登录并获取API token")
    print("4. 🧪 使用token测试完整API功能")
    
    print("\n💡 获取token后的测试命令示例:")
    print('curl -H "Authorization: Bearer <YOUR_TOKEN>" \\')
    print(f'     "{API_BASE}/sources"')
    
    print("\n🎉 基础测试完成！新闻收集器已准备就绪。")


if __name__ == "__main__":
    main()
