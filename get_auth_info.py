#!/usr/bin/env python3
"""
RAGFlow认证信息获取指南和测试工具
"""

import requests
import json
import sys

def test_ragflow_auth():
    """测试RAGFlow认证方式"""
    print("🔐 RAGFlow认证测试工具")
    print("="*50)
    
    # 测试不同的端口
    ports_to_test = [9222, 9380, 80, 8080]
    
    for port in ports_to_test:
        base_url = f"http://localhost:{port}"
        print(f"\n🔍 测试端口 {port}...")
        
        try:
            # 测试基础连接
            response = requests.get(f"{base_url}/", timeout=5)
            print(f"   ✅ 端口 {port} 可访问 (状态码: {response.status_code})")
            
            # 测试新闻收集器ping
            try:
                ping_response = requests.get(f"{base_url}/v1/news_collector/ping", timeout=5)
                print(f"   📰 新闻收集器ping: {ping_response.status_code}")
                if ping_response.status_code == 200:
                    print(f"   🎉 找到新闻收集器服务在端口 {port}!")
                    return port
            except:
                pass
                
        except requests.exceptions.ConnectionError:
            print(f"   ❌ 端口 {port} 不可访问")
        except Exception as e:
            print(f"   ⚠️ 端口 {port} 测试失败: {e}")
    
    return None

def get_auth_instructions():
    """获取认证说明"""
    print("\n" + "="*50)
    print("🔑 获取认证信息的方法")
    print("="*50)
    
    print("\n方法1: 使用浏览器开发者工具")
    print("-" * 30)
    print("1. 在Chrome/Edge中按F12打开开发者工具")
    print("2. 转到Network(网络)标签页")
    print("3. 在RAGFlow中执行任何操作(如查看知识库)")
    print("4. 在网络请求中找到任何API请求")
    print("5. 复制请求头中的以下信息:")
    print("   - Authorization: xxx")
    print("   - Cookie: session=xxx")
    
    print("\n方法2: 从控制台获取")
    print("-" * 30)
    print("1. 在RAGFlow页面按F12打开控制台")
    print("2. 输入以下JavaScript代码:")
    print("   console.log('Session:', document.cookie)")
    print("   console.log('Storage:', localStorage)")
    
    print("\n方法3: 使用cURL转换")
    print("-" * 30)
    print("1. 在开发者工具中右键任意请求")
    print("2. 选择 Copy -> Copy as cURL")
    print("3. 从cURL命令中提取认证信息")

def create_auth_test_script(port):
    """创建认证测试脚本"""
    script_content = f'''#!/usr/bin/env python3
"""
RAGFlow认证测试脚本 - 端口 {port}
"""

import requests

# 配置信息
SERVER_URL = "http://localhost:{port}"
API_BASE = f"{{SERVER_URL}}/v1/news_collector"

# 请在下面填入您的认证信息
AUTH_TOKEN = "IjMwNTRjMjY0NjkzMDExZjA5ODU1M2I3YzM2NDc4NDA0Ig.aIM-PQ.HcZwkiqSWhvtHc0t1MEu7cRQDfM"  # 从浏览器复制
SESSION_COOKIE = "qwvk05mY7F4MiSwJHQ6ZFSA-cy1OqAGJ2OmwNsrIhT0"  # 从浏览器复制

def test_with_token():
    """使用token测试"""
    headers = {{
        "Authorization": AUTH_TOKEN,  # 不加Bearer前缀，直接使用
        "Content-Type": "application/json"
    }}
    
    try:
        response = requests.get(f"{{API_BASE}}/sources", headers=headers, timeout=10)
        print(f"Token测试结果: {{response.status_code}}")
        if response.status_code == 200:
            print("✅ Token认证成功!")
            return True
        else:
            print(f"❌ Token认证失败: {{response.text}}")
    except Exception as e:
        print(f"❌ Token测试失败: {{e}}")
    return False

def test_with_session():
    """使用session cookie测试"""
    cookies = {{"session": SESSION_COOKIE}}
    headers = {{"Content-Type": "application/json"}}
    
    try:
        response = requests.get(f"{{API_BASE}}/sources", headers=headers, cookies=cookies, timeout=10)
        print(f"Session测试结果: {{response.status_code}}")
        if response.status_code == 200:
            print("✅ Session认证成功!")
            return True
        else:
            print(f"❌ Session认证失败: {{response.text}}")
    except Exception as e:
        print(f"❌ Session测试失败: {{e}}")
    return False

def test_combined():
    """组合认证测试"""
    headers = {{
        "Authorization": AUTH_TOKEN,
        "Content-Type": "application/json"
    }}
    cookies = {{"session": SESSION_COOKIE}}
    
    try:
        response = requests.get(f"{{API_BASE}}/sources", headers=headers, cookies=cookies, timeout=10)
        print(f"组合测试结果: {{response.status_code}}")
        if response.status_code == 200:
            print("✅ 组合认证成功!")
            return True
        else:
            print(f"❌ 组合认证失败: {{response.text}}")
    except Exception as e:
        print(f"❌ 组合测试失败: {{e}}")
    return False

if __name__ == "__main__":
    print("🧪 开始认证测试...")
    
    # 测试ping（无需认证）
    try:
        ping_response = requests.get(f"{{API_BASE}}/ping", timeout=5)
        print(f"Ping测试: {{ping_response.status_code}}")
    except Exception as e:
        print(f"❌ 服务不可用: {{e}}")
        exit(1)
    
    print("\\n测试不同的认证方式:")
    print("-" * 30)
    
    success = False
    success = test_with_token() or success
    success = test_with_session() or success  
    success = test_combined() or success
    
    if success:
        print("\\n🎉 认证测试成功! 可以继续使用API了")
    else:
        print("\\n❌ 所有认证方式都失败了")
        print("💡 请检查:")
        print("1. 认证信息是否正确")
        print("2. 认证信息是否已过期")
        print("3. 服务端口是否正确")
'''

    with open(f"test_auth_port_{port}.py", "w", encoding="utf-8") as f:
        f.write(script_content)
    
    print(f"✅ 已创建认证测试脚本: test_auth_port_{port}.py")

def main():
    print("🚀 开始检测RAGFlow服务...")
    
    # 检测服务端口
    active_port = test_ragflow_auth()
    
    if active_port:
        print(f"\n🎯 检测到RAGFlow运行在端口 {active_port}")
        create_auth_test_script(active_port)
    else:
        print("\n❌ 未检测到RAGFlow服务")
        print("💡 请确保RAGFlow服务正在运行")
    
    # 显示认证说明
    get_auth_instructions()
    
    print("\n" + "="*50)
    print("📋 后续步骤:")
    print("1. 确保RAGFlow服务运行在正确端口")
    print("2. 登录RAGFlow获取认证信息")
    print("3. 编辑生成的test_auth_port_*.py文件")
    print("4. 填入正确的AUTH_TOKEN和SESSION_COOKIE")
    print("5. 运行测试脚本验证认证")
    print("="*50)

if __name__ == "__main__":
    main()
