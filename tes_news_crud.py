#!/usr/bin/env python3
"""
新闻收集器CRUD功能测试脚本

测试新闻源、任务和内容的完整CRUD操作
"""

import requests
import json
import time
from typing import Dict, Any

class NewsCRUDTester:
    def __init__(self, api_base: str, auth_token: str, kb_id: str):
        self.api_base = api_base
        self.headers = {
            "Authorization": auth_token,
            "Content-Type": "application/json"
        }
        self.kb_id = kb_id
        self.created_resources = {
            "sources": [],
            "tasks": []
        }
    
    def test_source_crud(self):
        """测试新闻源CRUD操作"""
        print("🔧 测试新闻源CRUD操作...")
        
        # 1. 创建新闻源
        print("  📝 创建新闻源...")
        create_data = {
            "name": "测试新闻源",
            "url": "https://test.example.com",
            "remark": "这是一个测试新闻源",
            "status": "active",
            "fetch_config": {
                "category": "测试",
                "crawler_type": "demo",
                "max_articles": 10
            }
        }
        
        response = requests.post(
            f"{self.api_base}/sources",
            headers=self.headers,
            json=create_data
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('code') == 0:
                source_id = result['data']['source']['id']
                self.created_resources['sources'].append(source_id)
                print(f"    ✅ 创建成功，ID: {source_id}")
            else:
                print(f"    ❌ 创建失败: {result.get('message')}")
                return False
        else:
            print(f"    ❌ 请求失败: {response.status_code}")
            return False
        
        # 2. 获取新闻源列表
        print("  📝 获取新闻源列表...")
        response = requests.get(
            f"{self.api_base}/sources?page=1&page_size=10",
            headers=self.headers
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('code') == 0:
                total = result['data']['total']
                print(f"    ✅ 获取成功，共 {total} 个新闻源")
            else:
                print(f"    ❌ 获取失败: {result.get('message')}")
                return False
        else:
            print(f"    ❌ 请求失败: {response.status_code}")
            return False
        
        # 3. 获取单个新闻源
        print("  📝 获取单个新闻源...")
        response = requests.get(
            f"{self.api_base}/sources/{source_id}",
            headers=self.headers
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('code') == 0:
                name = result['data']['source']['name']
                print(f"    ✅ 获取成功，名称: {name}")
            else:
                print(f"    ❌ 获取失败: {result.get('message')}")
                return False
        else:
            print(f"    ❌ 请求失败: {response.status_code}")
            return False
        
        # 4. 更新新闻源
        print("  📝 更新新闻源...")
        update_data = {
            "remark": "更新后的备注信息",
            "fetch_config": {
                "max_articles": 20
            }
        }
        
        response = requests.put(
            f"{self.api_base}/sources/{source_id}",
            headers=self.headers,
            json=update_data
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('code') == 0:
                print("    ✅ 更新成功")
            else:
                print(f"    ❌ 更新失败: {result.get('message')}")
                return False
        else:
            print(f"    ❌ 请求失败: {response.status_code}")
            return False
        
        return True
    
    def test_task_crud(self):
        """测试任务CRUD操作"""
        print("📋 测试任务CRUD操作...")
        
        # 确保有新闻源可用
        if not self.created_resources['sources']:
            print("  ❌ 没有可用的新闻源")
            return False
        
        source_id = self.created_resources['sources'][0]
        
        # 1. 创建任务
        print("  📝 创建任务...")
        create_data = {
            "task_name": "测试新闻任务",
            "kb_id": self.kb_id,
            "source_ids": [source_id],
            "auto_parse": True,
            "max_articles_per_source": 5,

        }
        
        response = requests.post(
            f"{self.api_base}/tasks",
            headers=self.headers,
            json=create_data
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('code') == 0:
                task_id = result['data']['task']['id']
                self.created_resources['tasks'].append(task_id)
                print(f"    ✅ 创建成功，ID: {task_id}")
            else:
                print(f"    ❌ 创建失败: {result.get('message')}")
                return False
        else:
            print(f"    ❌ 请求失败: {response.status_code}")
            return False
        
        # 2. 获取任务列表
        print("  📝 获取任务列表...")
        response = requests.get(
            f"{self.api_base}/tasks?page=1&page_size=10",
            headers=self.headers
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('code') == 0:
                total = result['data']['total']
                print(f"    ✅ 获取成功，共 {total} 个任务")
            else:
                print(f"    ❌ 获取失败: {result.get('message')}")
                return False
        else:
            print(f"    ❌ 请求失败: {response.status_code}")
            return False
        
        # 3. 更新任务
        print("  📝 更新任务...")
        update_data = {
            "task_name": "更新后的任务名称",
            "max_articles_per_source": 10
        }
        
        response = requests.put(
            f"{self.api_base}/tasks/{task_id}",
            headers=self.headers,
            json=update_data
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('code') == 0:
                print("    ✅ 更新成功")
            else:
                print(f"    ❌ 更新失败: {result.get('message')}")
                return False
        else:
            print(f"    ❌ 请求失败: {response.status_code}")
            return False
        
        # 4. 执行任务
        print("  📝 执行任务...")
        response = requests.post(
            f"{self.api_base}/tasks/{task_id}/execute",
            headers=self.headers
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('code') == 0:
                print("    ✅ 任务执行已启动")
            else:
                print(f"    ❌ 执行失败: {result.get('message')}")
                return False
        else:
            print(f"    ❌ 请求失败: {response.status_code}")
            return False
        
        return True
    
    def test_content_and_stats(self):
        """测试内容查询和统计功能"""
        print("📊 测试内容查询和统计...")
        
        # 1. 获取统计信息
        print("  📝 获取统计信息...")
        response = requests.get(
            f"{self.api_base}/statistics?days=7",
            headers=self.headers
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get('code') == 0:
                summary = result['data']['summary']
                print(f"    ✅ 获取成功:")
                print(f"      - 新闻源总数: {summary['total_sources']}")
                print(f"      - 活跃新闻源: {summary['active_sources']}")
                print(f"      - 任务总数: {summary['total_tasks']}")
            else:
                print(f"    ❌ 获取失败: {result.get('message')}")
                return False
        else:
            print(f"    ❌ 请求失败: {response.status_code}")
            return False
        
        # 2. 获取内容列表（如果有任务）
        if self.created_resources['tasks']:
            task_id = self.created_resources['tasks'][0]
            print("  📝 获取新闻内容列表...")
            response = requests.get(
                f"{self.api_base}/contents?task_id={task_id}&page=1&page_size=10",
                headers=self.headers
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('code') == 0:
                    total = result['data']['total']
                    print(f"    ✅ 获取成功，共 {total} 条内容")
                else:
                    print(f"    ❌ 获取失败: {result.get('message')}")
                    return False
            else:
                print(f"    ❌ 请求失败: {response.status_code}")
                return False
        
        return True
    
    def cleanup(self):
        """清理测试数据"""
        print("🧹 清理测试数据...")
        
        # 删除任务
        for task_id in self.created_resources['tasks']:
            try:
                response = requests.delete(
                    f"{self.api_base}/tasks/{task_id}",
                    headers=self.headers
                )
                if response.status_code == 200:
                    print(f"    ✅ 删除任务 {task_id}")
                else:
                    print(f"    ❌ 删除任务失败: {task_id}")
            except Exception as e:
                print(f"    ❌ 删除任务异常: {e}")
        
        # 删除新闻源
        for source_id in self.created_resources['sources']:
            try:
                response = requests.delete(
                    f"{self.api_base}/sources/{source_id}",
                    headers=self.headers
                )
                if response.status_code == 200:
                    print(f"    ✅ 删除新闻源 {source_id}")
                else:
                    print(f"    ❌ 删除新闻源失败: {source_id}")
            except Exception as e:
                print(f"    ❌ 删除新闻源异常: {e}")
    
    def run_all_tests(self):
        """运行所有测试"""
        print("🎯 新闻收集器CRUD功能测试开始")
        print("=" * 60)
        
        try:
            # 测试新闻源CRUD
            if not self.test_source_crud():
                print("❌ 新闻源CRUD测试失败")
                return False
            
            # 测试任务CRUD
            if not self.test_task_crud():
                print("❌ 任务CRUD测试失败")
                return False
            
            # 测试内容和统计
            if not self.test_content_and_stats():
                print("❌ 内容和统计测试失败")
                return False
            
            print("\n🎉 所有CRUD测试通过！")
            return True
            
        except Exception as e:
            print(f"\n💥 测试过程中发生异常: {e}")
            return False
        finally:
            # 清理资源
            self.cleanup()


if __name__ == "__main__":
    # 配置
    API_BASE = "http://localhost:9222/api/v1/news_collector"
    AUTH_TOKEN = "Bearer ragflow-M3NDJjZmEyNjYwZDExZjBhMTAwYjlkOD"  # 请替换为实际的token
    KB_ID = "dc1b46f86ac111f090d847774016f42b"   # 请替换为实际的知识库ID
    
    # 运行测试
    tester = NewsCRUDTester(API_BASE, AUTH_TOKEN, KB_ID)
    success = tester.run_all_tests()
    
    if success:
        print("\n✅ 所有CRUD功能测试完成")
    else:
        print("\n❌ 部分测试失败，请检查系统状态")
