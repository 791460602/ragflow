#!/usr/bin/env python3
"""
新闻收集器API测试脚本
使用curl命令测试API端点，包含token获取方法
"""

import os
import json

def generate_api_tests():
    """生成API测试命令"""
    
    base_url = "http://localhost:9380"
    
    print("🌐 新闻收集器API测试指南")
    print("="*60)
    
    print("\n📋 第一步：获取访问令牌")
    print("-" * 30)
    print("1. 启动RAGFlow服务:")
    print("   python api/ragflow_server.py")
    print()
    print("2. 访问前端界面:")
    print("   http://localhost:9380")
    print()
    print("3. 登录后，在浏览器开发者工具中找到Authorization头部")
    print("   或在设置页面查看API Key")
    print()
    
    print("📋 第二步：测试API端点")
    print("-" * 30)
    
    # API测试命令
    api_tests = [
        {
            "name": "健康检查",
            "method": "GET",
            "endpoint": "/v1/news_collector/ping",
            "description": "检查新闻收集器服务状态"
        },
        {
            "name": "获取新闻源列表",
            "method": "GET", 
            "endpoint": "/v1/news_collector/sources",
            "description": "获取所有新闻源"
        },
        {
            "name": "创建新闻源",
            "method": "POST",
            "endpoint": "/v1/news_collector/sources",
            "description": "创建新的新闻源",
            "data": {
                "name": "测试新闻源",
                "url": "https://tech.sina.com.cn/",
                "remark": "API测试用新闻源"
            }
        },
        {
            "name": "获取任务列表",
            "method": "GET",
            "endpoint": "/v1/news_collector/tasks",
            "description": "获取所有抓取任务"
        },
        {
            "name": "创建抓取任务",
            "method": "POST",
            "endpoint": "/v1/news_collector/tasks",
            "description": "创建新的抓取任务",
            "data": {
                "name": "测试抓取任务",
                "source_id": "替换为实际的新闻源ID",
                "remark": "API测试用抓取任务"
            }
        },
        {
            "name": "获取新闻内容",
            "method": "GET",
            "endpoint": "/v1/news_collector/news",
            "description": "获取抓取的新闻内容"
        },
        {
            "name": "获取统计信息",
            "method": "GET",
            "endpoint": "/v1/news_collector/statistics",
            "description": "获取系统统计信息"
        }
    ]
    
    for i, test in enumerate(api_tests, 1):
        print(f"\n{i}. {test['name']}")
        print(f"   {test['description']}")
        
        if test['method'] == 'GET':
            print(f"   curl -H 'Authorization: Bearer <YOUR_TOKEN>' \\")
            print(f"        '{base_url}{test['endpoint']}'")
        else:
            data_str = json.dumps(test.get('data', {}), ensure_ascii=False, indent=2)
            print(f"   curl -X {test['method']} \\")
            print(f"        -H 'Authorization: Bearer <YOUR_TOKEN>' \\")
            print(f"        -H 'Content-Type: application/json' \\")
            print(f"        -d '{data_str}' \\")
            print(f"        '{base_url}{test['endpoint']}'")
    
    print("\n" + "="*60)
    print("💡 使用提示:")
    print("="*60)
    print("1. 将 <YOUR_TOKEN> 替换为实际的访问令牌")
    print("2. 新闻源创建成功后，记录返回的ID用于创建任务")
    print("3. 可以通过前端文件管理页面查看抓取结果")
    print("4. 如果遇到认证问题，请检查token是否正确")
    print("="*60)

def generate_postman_collection():
    """生成Postman集合配置"""
    collection = {
        "info": {
            "name": "RAGFlow 新闻收集器 API",
            "description": "新闻收集器系统的API测试集合",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
        },
        "auth": {
            "type": "bearer",
            "bearer": [
                {
                    "key": "token",
                    "value": "{{auth_token}}",
                    "type": "string"
                }
            ]
        },
        "variable": [
            {
                "key": "base_url",
                "value": "http://localhost:9380",
                "type": "string"
            },
            {
                "key": "auth_token", 
                "value": "",
                "type": "string"
            }
        ],
        "item": [
            {
                "name": "健康检查",
                "request": {
                    "method": "GET",
                    "header": [],
                    "url": {
                        "raw": "{{base_url}}/v1/news_collector/ping",
                        "host": ["{{base_url}}"],
                        "path": ["v1", "news_collector", "ping"]
                    }
                }
            },
            {
                "name": "获取新闻源",
                "request": {
                    "method": "GET",
                    "header": [],
                    "url": {
                        "raw": "{{base_url}}/v1/news_collector/sources",
                        "host": ["{{base_url}}"],
                        "path": ["v1", "news_collector", "sources"]
                    }
                }
            },
            {
                "name": "创建新闻源",
                "request": {
                    "method": "POST",
                    "header": [
                        {
                            "key": "Content-Type",
                            "value": "application/json"
                        }
                    ],
                    "body": {
                        "mode": "raw",
                        "raw": json.dumps({
                            "name": "测试新闻源",
                            "url": "https://tech.sina.com.cn/",
                            "remark": "Postman测试用"
                        }, ensure_ascii=False, indent=2)
                    },
                    "url": {
                        "raw": "{{base_url}}/v1/news_collector/sources",
                        "host": ["{{base_url}}"],
                        "path": ["v1", "news_collector", "sources"]
                    }
                }
            }
        ]
    }
    
    # 保存Postman集合
    with open("news_collector_api.postman_collection.json", "w", encoding="utf-8") as f:
        json.dump(collection, f, ensure_ascii=False, indent=2)
    
    print(f"📦 Postman集合已保存到: news_collector_api.postman_collection.json")
    print("💡 导入到Postman后，记得在环境变量中设置 auth_token")

if __name__ == "__main__":
    generate_api_tests()
    print("\n" + "="*60)
    generate_postman_collection()
