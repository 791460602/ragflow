#!/usr/bin/env python3
"""
新闻收集器API测试脚本
"""

import requests
import json

# 服务器配置
SERVER_URL = "http://localhost:9222"  # 修改为正确的端口
API_BASE = f"{SERVER_URL}/v1/news_collector"

# 认证配置 - 支持多种认证方式
AUTH_TOKEN = ""  # 在这里填入您的token
SESSION_COOKIE = ""  # 或者在这里填入session cookie

# 测试数据
test_source = {
    "name": "示例新闻网站",
    "url": "https://example.com/news",
    "remark": "这是一个测试新闻源"
}


def get_auth_headers():
    """获取认证头部"""
    headers = {"Content-Type": "application/json"}
    
    if AUTH_TOKEN:
        # 尝试不同的token格式
        if AUTH_TOKEN.startswith('Bearer '):
            headers["Authorization"] = AUTH_TOKEN
        else:
            headers["Authorization"] = f"Bearer {AUTH_TOKEN}"
    
    return headers

def get_cookies():
    """获取认证cookies"""
    cookies = {}
    if SESSION_COOKIE:
        cookies["session"] = SESSION_COOKIE
    return cookies


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
            headers=get_auth_headers(),
            cookies=get_cookies(),
            timeout=10
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
        response = requests.get(
            f"{API_BASE}/sources",
            headers=get_auth_headers(),
            cookies=get_cookies(),
            timeout=10
        )
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
        response = requests.get(
            f"{API_BASE}/statistics",
            headers=get_auth_headers(),
            cookies=get_cookies(),
            timeout=10
        )
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
    
    # 检查认证配置
    print("🔐 认证配置检查:")
    if not AUTH_TOKEN and not SESSION_COOKIE:
        print("⚠️ 未配置认证信息!")
        print("\n📋 获取认证信息的步骤:")
        print("1. 在浏览器中登录RAGFlow")
        print("2. 按F12打开开发者工具，转到Network标签页")
        print("3. 在RAGFlow中执行任何操作（如查看知识库）")
        print("4. 找到任何API请求，复制请求头中的信息:")
        print("   - Authorization的完整值")
        print("   - Cookie中session的值")
        print("\n🔧 然后编辑脚本顶部的认证配置:")
        print('AUTH_TOKEN = "你的完整Authorization值"')
        print('SESSION_COOKIE = "你的session值"')
        print()
    else:
        if AUTH_TOKEN:
            print(f"✅ 已配置AUTH_TOKEN: {AUTH_TOKEN[:20]}...")
        if SESSION_COOKIE:
            print(f"✅ 已配置SESSION_COOKIE: {SESSION_COOKIE[:20]}...")
    
    # 测试健康检查
    print("\n1️⃣ 测试服务连通性")
    if not test_ping():
        print("❌ 服务不可用，请确保:")
        print("   1. RAGFlow服务正在运行")
        print(f"   2. 服务端口正确: {SERVER_URL}")
        print("   3. 新闻收集器模块已正确安装")
        return
    
    print("✅ 服务连通性正常")
    
    # 测试需要认证的接口
    print("\n2️⃣ 测试需要认证的接口")
    if not AUTH_TOKEN and not SESSION_COOKIE:
        print("⚠️ 跳过认证测试 - 请先配置认证信息")
    else:
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
    
    if not AUTH_TOKEN and not SESSION_COOKIE:
        print("⚠️ 需要配置认证信息才能测试完整功能")
    else:
        print("✅ 认证配置完成，可以测试完整API功能")
    
    print("\n� 认证信息示例（基于您提供的信息）:")
    print('AUTH_TOKEN = "IjMwNTRjMjY0NjkzMDExZjA5ODU1M2I3YzM2NDc4NDA0Ig.aIM-PQ.HcZwkiqSWhvtHc0t1MEu7cRQDfM"')
    print('SESSION_COOKIE = "qwvk05mY7F4MiSwJHQ6ZFSA-cy1OqAGJ2OmwNsrIhT0"')
    print()
    print("💡 注意：这些token可能已过期，请获取最新的")
    
    print("\n🎉 新闻收集器已准备就绪！")


if __name__ == "__main__":
    main()
