#!/usr/bin/env python3
"""
RAGFlow API 路径测试脚本
用于验证正确的 API 端点
"""

import requests

# 配置参数
API_KEY = "ragflow-M3NDJjZmEyNjYwZDExZjBhMTAwYjlkOD"  # 你的API密钥
BASE_URL = "http://localhost:9380"  # RAGFlow服务地址

def test_api_endpoints():
    """
    测试不同的 API 端点路径
    """
    headers = {
        'Authorization': f'Bearer {API_KEY}',
        'Content-Type': 'application/json'
    }
    
    # 测试的端点列表
    endpoints_to_test = [
        "/api/v1/file2document/convert",
        "/api/file2document/convert", 
        "/v1/file2document/convert",
        "/file2document/convert"
    ]
    
    # 测试数据（无效数据用于测试路径）
    test_payload = {
        "file_ids": ["test_id"],
        "kb_ids": ["test_kb_id"]
    }
    
    print("🔍 测试 RAGFlow API 端点...")
    print("=" * 60)
    
    for endpoint in endpoints_to_test:
        full_url = f"{BASE_URL}{endpoint}"
        print(f"\n📡 测试: {full_url}")
        
        try:
            response = requests.post(
                full_url,
                json=test_payload,
                headers=headers,
                timeout=5
            )
            
            print(f"   状态码: {response.status_code}")
            
            if response.status_code == 404:
                print("   ❌ 端点不存在")
            elif response.status_code == 400:
                print("   ✅ 端点存在，但参数错误（这是预期的）")
            elif response.status_code == 401:
                print("   ✅ 端点存在，但认证失败")
            elif response.status_code == 200:
                print("   ✅ 端点存在且可访问")
                try:
                    result = response.json()
                    print(f"   响应: {result}")
                except:
                    print(f"   响应: {response.text[:100]}...")
            else:
                print(f"   📝 其他状态码: {response.status_code}")
                print(f"   响应: {response.text[:100]}...")
                
        except requests.exceptions.ConnectionError:
            print("   ❌ 连接失败 - 检查服务是否运行")
        except requests.exceptions.Timeout:
            print("   ❌ 请求超时")
        except Exception as e:
            print(f"   ❌ 错误: {str(e)}")
    
    print("\n" + "=" * 60)
    print("💡 建议:")
    print("- 如果状态码是 400/401，说明端点存在")
    print("- 如果状态码是 404，说明端点不存在")
    print("- 选择状态码不是 404 的端点使用")

if __name__ == "__main__":
    test_api_endpoints()
