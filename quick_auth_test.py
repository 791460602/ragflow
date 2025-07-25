#!/usr/bin/env python3
"""
快速认证测试 - 使用您提供的认证信息
"""

import requests
import json

# 基于您提供的信息配置
SERVER_URL = "http://localhost:9222"  # 您的浏览器显示的端口
API_BASE = f"{SERVER_URL}/v1/news_collector"

# 您从浏览器复制的认证信息
AUTH_TOKEN = "IjMwNTRjMjY0NjkzMDExZjA5ODU1M2I3YzM2NDc4NDA0Ig.aIM-PQ.HcZwkiqSWhvtHc0t1MEu7cRQDfM"
SESSION_COOKIE = "qwvk05mY7F4MiSwJHQ6ZFSA-cy1OqAGJ2OmwNsrIhT0"

def test_different_auth_methods():
    """测试不同的认证方法"""
    
    print("🧪 测试不同的认证方法")
    print("="*50)
    
    # 方法1: 仅使用Authorization header (原始格式)
    print("\n1️⃣ 测试Authorization header (原始格式)")
    headers1 = {
        "Authorization": AUTH_TOKEN,
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(f"{API_BASE}/sources", headers=headers1, timeout=10)
        print(f"   状态码: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ 成功!")
            return True
        else:
            print(f"   ❌ 失败: {response.text[:100]}")
    except Exception as e:
        print(f"   ❌ 异常: {e}")
    
    # 方法2: 仅使用Session cookie
    print("\n2️⃣ 测试Session cookie")
    headers2 = {"Content-Type": "application/json"}
    cookies2 = {"session": SESSION_COOKIE}
    
    try:
        response = requests.get(f"{API_BASE}/sources", headers=headers2, cookies=cookies2, timeout=10)
        print(f"   状态码: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ 成功!")
            return True
        else:
            print(f"   ❌ 失败: {response.text[:100]}")
    except Exception as e:
        print(f"   ❌ 异常: {e}")
    
    # 方法3: 组合使用
    print("\n3️⃣ 测试组合认证")
    headers3 = {
        "Authorization": AUTH_TOKEN,
        "Content-Type": "application/json"
    }
    cookies3 = {"session": SESSION_COOKIE}
    
    try:
        response = requests.get(f"{API_BASE}/sources", headers=headers3, cookies=cookies3, timeout=10)
        print(f"   状态码: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ 成功!")
            return True
        else:
            print(f"   ❌ 失败: {response.text[:100]}")
    except Exception as e:
        print(f"   ❌ 异常: {e}")
    
    # 方法4: 使用Bearer前缀
    print("\n4️⃣ 测试Bearer前缀")
    headers4 = {
        "Authorization": f"Bearer {AUTH_TOKEN}",
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.get(f"{API_BASE}/sources", headers=headers4, timeout=10)
        print(f"   状态码: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ 成功!")
            return True
        else:
            print(f"   ❌ 失败: {response.text[:100]}")
    except Exception as e:
        print(f"   ❌ 异常: {e}")
    
    return False

def test_known_working_endpoint():
    """测试已知工作的端点"""
    print("\n🔍 测试已知的RAGFlow端点")
    
    # 您的浏览器成功访问的端点
    kb_url = f"{SERVER_URL}/v1/kb/list"
    
    headers = {
        "Authorization": AUTH_TOKEN,
        "Content-Type": "application/json"
    }
    cookies = {"session": SESSION_COOKIE}
    
    try:
        response = requests.post(kb_url, json={}, headers=headers, cookies=cookies, timeout=10)
        print(f"知识库列表API状态码: {response.status_code}")
        if response.status_code == 200:
            print("✅ RAGFlow认证正常工作!")
            return True
        else:
            print(f"❌ 知识库API失败: {response.text[:100]}")
    except Exception as e:
        print(f"❌ 知识库API异常: {e}")
    
    return False

def main():
    print("🚀 快速认证测试")
    print("="*50)
    print(f"服务器: {SERVER_URL}")
    print(f"API基础: {API_BASE}")
    
    # 首先测试ping（无需认证）
    try:
        ping_response = requests.get(f"{API_BASE}/ping", timeout=5)
        print(f"\nPing测试: {ping_response.status_code}")
        if ping_response.status_code == 200:
            print("✅ 新闻收集器服务可访问")
        else:
            print("❌ 新闻收集器服务不可访问")
            return
    except Exception as e:
        print(f"❌ Ping失败: {e}")
        print("\n💡 可能的原因:")
        print("1. 端口号不正确")
        print("2. 新闻收集器模块未启动")
        print("3. RAGFlow服务未运行")
        return
    
    # 测试已知工作的端点
    if test_known_working_endpoint():
        print("\n📰 现在测试新闻收集器认证...")
        success = test_different_auth_methods()
        
        if success:
            print("\n🎉 找到工作的认证方法!")
            print("您可以使用成功的方法继续测试其他API")
        else:
            print("\n❌ 所有认证方法都失败了")
            print("💡 可能的原因:")
            print("1. 新闻收集器需要特殊的认证方式")
            print("2. token已过期")
            print("3. 新闻收集器的权限配置不同")
    else:
        print("\n❌ 基础RAGFlow认证失败")
        print("💡 请检查:")
        print("1. token是否从正确的请求中复制")
        print("2. token是否已过期")
        print("3. 重新登录获取新的token")

if __name__ == "__main__":
    main()
