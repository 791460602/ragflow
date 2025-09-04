#!/usr/bin/env python3
"""
简单测试上传函数

绕过完整的模块导入，直接测试核心上传逻辑
"""

import requests
import json

# 配置信息
SERVER_URL = "http://localhost:9222"
API_BASE = f"{SERVER_URL}/api/v1"
AUTH_TOKEN = "Bearer ragflow-M3NDJjZmEyNjYwZDExZjBhMTAwYjlkOD"
KNOWLEDGE_BASE_ID = "dc1b46f86ac111f090d847774016f42b"

def get_headers():
    """获取请求头"""
    return {
        "Authorization": AUTH_TOKEN,
        "Content-Type": "application/json"
    }

def simple_upload_test():
    """简单的上传测试"""
    print("📋 简化上传测试")
    print("=" * 40)
    
    # 1. 创建任务并执行
    task_data = {
        "task_name": "简化测试",
        "kb_id": KNOWLEDGE_BASE_ID,
        "sources": [
            {
                "name": "简化测试源",
                "url": "https://example.com/simple",
                "config": {}
            }
        ],
        "crawler_type": "demo",
        "max_articles": 1  # 只要1篇文章，简化测试
    }
    
    print("1️⃣ 创建任务...")
    try:
        response = requests.post(
            f"{API_BASE}/tasks",
            headers=get_headers(),
            json=task_data,
            timeout=30
        )
        
        if response.status_code != 200:
            print(f"❌ 任务创建失败: {response.status_code}")
            return False
        
        result = response.json()
        task_id = result.get('data', {}).get('task_id')
        print(f"✅ 任务ID: {task_id}")
        
    except Exception as e:
        print(f"❌ 任务创建异常: {e}")
        return False
    
    # 2. 执行任务
    print("\n2️⃣ 执行任务...")
    try:
        response = requests.post(
            f"{API_BASE}/tasks/{task_id}/execute",
            headers=get_headers(),
            timeout=60
        )
        
        if response.status_code != 200:
            print(f"❌ 任务执行失败: {response.status_code}")
            print(f"   错误信息: {response.text}")
            return False
        
        result = response.json()
        print(f"✅ 任务执行完成")
        
        # 打印完整的执行结果
        print(f"\n📋 完整执行结果:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
        # 检查上传结果
        task_data = result.get("data", {})
        crawl_result = task_data.get("crawl_result", {})
        upload_result = task_data.get("upload_result", {})
        
        print(f"\n🔍 详细分析:")
        print(f"   任务状态: {task_data.get('status')}")
        print(f"   爬取结果成功: {crawl_result.get('success')}")
        print(f"   爬取文章数: {crawl_result.get('total_articles')}")
        print(f"   上传结果成功: {upload_result.get('success')}")
        print(f"   上传文件数: {upload_result.get('uploaded_files')}")
        
        if upload_result.get("error"):
            print(f"   ❌ 上传错误: {upload_result.get('error')}")
        
        # 检查文件详情
        files = upload_result.get("files", [])
        if files:
            print(f"\n📄 上传的文件:")
            for file_info in files:
                print(f"   - {file_info.get('name')}")
                print(f"     大小: {file_info.get('size')} bytes")
                print(f"     位置: {file_info.get('location')}")
                
                # 验证修复
                location = file_info.get('location', '')
                if location.startswith('/tmp/') or location.startswith('/'):
                    print(f"     ❌ 仍然使用本地路径！修复失败")
                elif location.startswith('news_'):
                    print(f"     ✅ 使用正确的存储标识符")
                else:
                    print(f"     ⚠️  位置格式异常")
        else:
            print(f"   ❌ 没有上传任何文件")
        
        return upload_result.get("success", False) and len(files) > 0
        
    except Exception as e:
        print(f"❌ 任务执行异常: {e}")
        return False

if __name__ == "__main__":
    print("🔧 新闻收集器简化上传测试")
    success = simple_upload_test()
    
    if success:
        print(f"\n🎉 测试成功！修复已生效。")
    else:
        print(f"\n❌ 测试失败，需要进一步检查。")
