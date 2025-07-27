#!/usr/bin/env python3
"""
新闻收集器CRUD功能使用示例

演示如何使用新闻源、任务和内容管理功能
"""

import requests
import json
import time
from typing import Dict, List, Any

class NewsCollectorManager:
    """新闻收集器管理类"""
    
    def __init__(self, api_base: str, auth_token: str):
        self.api_base = api_base
        self.headers = {
            "Authorization": auth_token,
            "Content-Type": "application/json"
        }
    
    # ========== 新闻源管理 ==========
    
    def create_news_source(self, name: str, url: str, **kwargs) -> Dict[str, Any]:
        """创建新闻源"""
        data = {
            "name": name,
            "url": url,
            "remark": kwargs.get('remark', ''),
            "status": kwargs.get('status', 'active'),
            "fetch_config": kwargs.get('fetch_config', {})
        }
        
        response = requests.post(
            f"{self.api_base}/sources",
            headers=self.headers,
            json=data
        )
        
        return response.json()
    
    def list_news_sources(self, page: int = 1, page_size: int = 20, **filters) -> Dict[str, Any]:
        """获取新闻源列表"""
        params = {
            "page": page,
            "page_size": page_size
        }
        
        if filters.get('name'):
            params['name'] = filters['name']
        if filters.get('status'):
            params['status'] = filters['status']
        
        response = requests.get(
            f"{self.api_base}/sources",
            headers=self.headers,
            params=params
        )
        
        return response.json()
    
    def update_news_source(self, source_id: str, **kwargs) -> Dict[str, Any]:
        """更新新闻源"""
        response = requests.put(
            f"{self.api_base}/sources/{source_id}",
            headers=self.headers,
            json=kwargs
        )
        
        return response.json()
    
    def delete_news_source(self, source_id: str) -> Dict[str, Any]:
        """删除新闻源"""
        response = requests.delete(
            f"{self.api_base}/sources/{source_id}",
            headers=self.headers
        )
        
        return response.json()
    
    # ========== 任务管理 ==========
    
    def create_news_task(self, task_name: str, kb_id: str, source_ids: List[str], **kwargs) -> Dict[str, Any]:
        """创建新闻任务"""
        data = {
            "task_name": task_name,
            "kb_id": kb_id,
            "source_ids": source_ids,
            "auto_parse": kwargs.get('auto_parse', True),
            "max_articles_per_source": kwargs.get('max_articles_per_source', 10),
            "crawler_config": kwargs.get('crawler_config', {"type": "demo"})
        }
        
        response = requests.post(
            f"{self.api_base}/tasks",
            headers=self.headers,
            json=data
        )
        
        return response.json()
    
    def list_news_tasks(self, page: int = 1, page_size: int = 20, **filters) -> Dict[str, Any]:
        """获取任务列表"""
        params = {
            "page": page,
            "page_size": page_size
        }
        
        if filters.get('task_name'):
            params['task_name'] = filters['task_name']
        if filters.get('status'):
            params['status'] = filters['status']
        
        response = requests.get(
            f"{self.api_base}/tasks",
            headers=self.headers,
            params=params
        )
        
        return response.json()
    
    def execute_task(self, task_id: str) -> Dict[str, Any]:
        """执行任务"""
        response = requests.post(
            f"{self.api_base}/tasks/{task_id}/execute",
            headers=self.headers
        )
        
        return response.json()
    
    def delete_news_task(self, task_id: str) -> Dict[str, Any]:
        """删除任务"""
        response = requests.delete(
            f"{self.api_base}/tasks/{task_id}",
            headers=self.headers
        )
        
        return response.json()
    
    # ========== 内容管理 ==========
    
    def list_news_contents(self, page: int = 1, page_size: int = 20, **filters) -> Dict[str, Any]:
        """获取新闻内容列表"""
        params = {
            "page": page,
            "page_size": page_size
        }
        
        if filters.get('task_id'):
            params['task_id'] = filters['task_id']
        if filters.get('source_id'):
            params['source_id'] = filters['source_id']
        
        response = requests.get(
            f"{self.api_base}/contents",
            headers=self.headers,
            params=params
        )
        
        return response.json()
    
    # ========== 统计分析 ==========
    
    def get_statistics(self, days: int = 7) -> Dict[str, Any]:
        """获取统计信息"""
        response = requests.get(
            f"{self.api_base}/statistics",
            headers=self.headers,
            params={"days": days}
        )
        
        return response.json()


def main():
    """主要示例函数"""
    
    # 配置
    API_BASE = "http://localhost:9222/api/v1/news_collector"
    AUTH_TOKEN = "Bearer ragflow-xxx"  # 请替换为实际的token
    KB_ID = "your-knowledge-base-id"   # 请替换为实际的知识库ID
    
    # 创建管理器
    manager = NewsCollectorManager(API_BASE, AUTH_TOKEN)
    
    print("🎯 新闻收集器CRUD功能演示")
    print("=" * 60)
    
    # ========== 演示1: 新闻源管理 ==========
    print("\n📋 演示1: 新闻源管理")
    
    # 创建新闻源
    print("  创建新闻源...")
    source_result = manager.create_news_source(
        name="科技新闻网",
        url="https://tech.example.com",
        remark="提供最新科技资讯",
        fetch_config={
            "category": "科技",
            "crawler_type": "demo",
            "max_articles": 15
        }
    )
    
    if source_result.get('code') == 0:
        source_id = source_result['data']['source']['id']
        print(f"    ✅ 新闻源创建成功，ID: {source_id}")
    else:
        print(f"    ❌ 创建失败: {source_result.get('message')}")
        return
    
    # 获取新闻源列表
    print("  获取新闻源列表...")
    sources_result = manager.list_news_sources(page=1, page_size=10, status="active")
    
    if sources_result.get('code') == 0:
        total = sources_result['data']['total']
        print(f"    ✅ 获取成功，共 {total} 个活跃新闻源")
        
        # 显示前几个新闻源
        for source in sources_result['data']['sources'][:3]:
            print(f"      - {source['name']}: {source['url']}")
    else:
        print(f"    ❌ 获取失败: {sources_result.get('message')}")
    
    # 更新新闻源
    print("  更新新闻源...")
    update_result = manager.update_news_source(
        source_id,
        remark="更新后的备注信息",
        fetch_config={"max_articles": 20}
    )
    
    if update_result.get('code') == 0:
        print("    ✅ 新闻源更新成功")
    else:
        print(f"    ❌ 更新失败: {update_result.get('message')}")
    
    # ========== 演示2: 任务管理 ==========
    print("\n📋 演示2: 任务管理")
    
    # 创建任务
    print("  创建新闻任务...")
    task_result = manager.create_news_task(
        task_name="每日科技新闻收集",
        kb_id=KB_ID,
        source_ids=[source_id],
        auto_parse=True,
        max_articles_per_source=10,
        crawler_config={
            "type": "demo",
            "timeout": 300
        }
    )
    
    if task_result.get('code') == 0:
        task_id = task_result['data']['task']['id']
        print(f"    ✅ 任务创建成功，ID: {task_id}")
    else:
        print(f"    ❌ 创建失败: {task_result.get('message')}")
        return
    
    # 获取任务列表
    print("  获取任务列表...")
    tasks_result = manager.list_news_tasks(page=1, page_size=10)
    
    if tasks_result.get('code') == 0:
        total = tasks_result['data']['total']
        print(f"    ✅ 获取成功，共 {total} 个任务")
        
        # 显示任务信息
        for task in tasks_result['data']['tasks'][:2]:
            print(f"      - {task['task_name']}: {task['status']}")
    else:
        print(f"    ❌ 获取失败: {tasks_result.get('message')}")
    
    # 执行任务
    print("  执行任务...")
    execute_result = manager.execute_task(task_id)
    
    if execute_result.get('code') == 0:
        print("    ✅ 任务执行已启动")
        print(f"      执行ID: {execute_result['data']['execution_id']}")
    else:
        print(f"    ❌ 执行失败: {execute_result.get('message')}")
    
    # ========== 演示3: 统计分析 ==========
    print("\n📊 演示3: 统计分析")
    
    # 获取统计信息
    print("  获取统计信息...")
    stats_result = manager.get_statistics(days=7)
    
    if stats_result.get('code') == 0:
        summary = stats_result['data']['summary']
        print(f"    ✅ 统计信息获取成功:")
        print(f"      - 新闻源总数: {summary['total_sources']}")
        print(f"      - 活跃新闻源: {summary['active_sources']}")
        print(f"      - 任务总数: {summary['total_tasks']}")
        print(f"      - 运行中任务: {summary['running_tasks']}")
        print(f"      - 总文章数: {summary['total_articles']}")
    else:
        print(f"    ❌ 获取失败: {stats_result.get('message')}")
    
    # ========== 演示4: 内容查询 ==========
    print("\n📰 演示4: 内容查询")
    
    # 按任务查询内容
    print("  查询任务相关内容...")
    contents_result = manager.list_news_contents(
        page=1,
        page_size=5,
        task_id=task_id
    )
    
    if contents_result.get('code') == 0:
        total = contents_result['data']['total']
        print(f"    ✅ 获取成功，该任务共 {total} 条内容")
        
        # 显示内容信息
        for content in contents_result['data']['contents']:
            print(f"      - {content.get('original_url', '未知URL')}")
    else:
        print(f"    ❌ 获取失败: {contents_result.get('message')}")
    
    # ========== 清理资源 ==========
    print("\n🧹 清理演示资源")
    
    # 删除任务
    print("  删除演示任务...")
    delete_task_result = manager.delete_news_task(task_id)
    if delete_task_result.get('code') == 0:
        print("    ✅ 任务删除成功")
    else:
        print(f"    ❌ 任务删除失败: {delete_task_result.get('message')}")
    
    # 删除新闻源
    print("  删除演示新闻源...")
    delete_source_result = manager.delete_news_source(source_id)
    if delete_source_result.get('code') == 0:
        print("    ✅ 新闻源删除成功")
    else:
        print(f"    ❌ 新闻源删除失败: {delete_source_result.get('message')}")
    
    print("\n🎉 CRUD功能演示完成！")


if __name__ == "__main__":
    main()
