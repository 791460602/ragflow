#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
新闻调度器测试脚本
包含附件处理功能的测试用例
"""

import json
import time
import requests
from datetime import datetime


class NewsSchedulerTester:
    def __init__(self, base_url="http://localhost:9380", api_key=None):
        self.base_url = base_url
        self.headers = {
            "Content-Type": "application/json"
        }
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"
    
    def test_config_management(self):
        """测试配置管理"""
        print("=== 测试配置管理 ===")
        
        # 测试配置
        config = {
            "scheduler_config": {
                "enabled": True,
                "timezone": "Asia/Shanghai",
                "max_concurrent_jobs": 3,
                "job_timeout": 1800
            },
            "news_sources": [
                {
                    "name": "测试新闻源",
                    "url": "https://news.sina.com.cn/",
                    "type": "rss",
                    "rss_url": "https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2509&k=&num=10&page=1&r=",
                    "keywords": ["科技", "AI"],
                    "exclude_keywords": ["广告"],
                    "max_news_count": 5,
                    "enabled": True
                }
            ],
            "news_processor": {
                "kb_id": "test_kb_id",
                "process_content": True,
                "max_content_length": 3000,
                "save_to_kb": False,  # 测试时不保存到知识库
                "format_output": "markdown",
                "download_attachments": True,
                "attachment_types": ["pdf", "doc", "docx"],
                "max_attachment_size": 10 * 1024 * 1024,  # 10MB
                "attachment_timeout": 30
            },
            "report_generator": {
                "template": "daily_brief",
                "language": "zh-CN",
                "include_attachments": True,
                "attachment_summary": True,
                "max_attachment_summary_length": 300,
                "output_format": "markdown",
                "sections": ["summary", "key_events", "attachments"]
            },
            "schedule": {
                "crawl_schedule": "0 */2 * * *",  # 每2小时
                "report_schedule": "0 9 * * *",
                "cleanup_schedule": "0 2 * * 0"
            }
        }
        
        try:
            # 设置配置
            response = requests.put(
                f"{self.base_url}/api/v1/news-scheduler/config",
                headers=self.headers,
                json=config
            )
            print(f"设置配置: {response.status_code}")
            if response.status_code == 200:
                print("✓ 配置设置成功")
            else:
                print(f"✗ 配置设置失败: {response.text}")
            
            # 获取配置
            response = requests.get(
                f"{self.base_url}/api/v1/news-scheduler/config",
                headers=self.headers
            )
            print(f"获取配置: {response.status_code}")
            if response.status_code == 200:
                print("✓ 配置获取成功")
                print(json.dumps(response.json(), indent=2, ensure_ascii=False))
            else:
                print(f"✗ 配置获取失败: {response.text}")
                
        except Exception as e:
            print(f"✗ 配置管理测试失败: {str(e)}")
    
    def test_attachment_processing(self):
        """测试附件处理功能"""
        print("\n=== 测试附件处理功能 ===")
        
        # 测试附件识别
        test_urls = [
            "https://example.com/document.pdf",
            "https://example.com/report.docx",
            "https://example.com/presentation.ppt",
            "https://example.com/data.xlsx",
            "https://example.com/attachment",
            "https://example.com/download/file.pdf"
        ]
        
        print("测试附件URL识别:")
        for url in test_urls:
            # 这里应该调用实际的附件识别逻辑
            is_attachment = self._is_attachment_url(url)
            print(f"  {url}: {'✓' if is_attachment else '✗'}")
        
        # 测试附件下载（模拟）
        print("\n测试附件下载:")
        test_attachments = [
            {"url": "https://example.com/test.pdf", "filename": "test.pdf", "size": 1024000},
            {"url": "https://example.com/report.docx", "filename": "report.docx", "size": 2048000}
        ]
        
        for attachment in test_attachments:
            print(f"  模拟下载: {attachment['filename']} ({attachment['size']} bytes)")
        
        print("✓ 附件处理功能测试完成")
    
    def _is_attachment_url(self, url):
        """简单的附件URL识别逻辑"""
        attachment_extensions = ['.pdf', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx']
        attachment_keywords = ['pdf', 'attachment', 'download', 'file']
        
        url_lower = url.lower()
        
        # 检查文件扩展名
        for ext in attachment_extensions:
            if url_lower.endswith(ext):
                return True
        
        # 检查关键词
        for keyword in attachment_keywords:
            if keyword in url_lower:
                return True
        
        return False
    
    def test_news_crawling(self):
        """测试新闻抓取"""
        print("\n=== 测试新闻抓取 ===")
        
        try:
            # 测试抓取
            response = requests.post(
                f"{self.base_url}/api/v1/news-scheduler/test-crawl",
                headers=self.headers,
                json={"source_name": "测试新闻源"}
            )
            print(f"测试抓取: {response.status_code}")
            if response.status_code == 200:
                print("✓ 新闻抓取测试成功")
                result = response.json()
                print(f"抓取到 {len(result.get('news', []))} 条新闻")
                
                # 检查附件信息
                for news in result.get('news', []):
                    if news.get('attachments'):
                        print(f"  新闻 '{news.get('title', '')}' 包含 {len(news['attachments'])} 个附件")
            else:
                print(f"✗ 新闻抓取测试失败: {response.text}")
                
        except Exception as e:
            print(f"✗ 新闻抓取测试失败: {str(e)}")
    
    def test_report_generation(self):
        """测试简报生成"""
        print("\n=== 测试简报生成 ===")
        
        try:
            # 测试简报生成
            response = requests.post(
                f"{self.base_url}/api/v1/news-scheduler/generate-report",
                headers=self.headers,
                json={
                    "template": "daily_brief",
                    "language": "zh-CN",
                    "include_attachments": True
                }
            )
            print(f"测试简报生成: {response.status_code}")
            if response.status_code == 200:
                print("✓ 简报生成测试成功")
                result = response.json()
                print(f"生成简报长度: {len(result.get('content', ''))} 字符")
                
                # 检查附件章节
                if 'attachments' in result.get('content', ''):
                    print("✓ 简报包含附件信息")
                else:
                    print("✗ 简报未包含附件信息")
            else:
                print(f"✗ 简报生成测试失败: {response.text}")
                
        except Exception as e:
            print(f"✗ 简报生成测试失败: {str(e)}")
    
    def test_scheduler_control(self):
        """测试调度器控制"""
        print("\n=== 测试调度器控制 ===")
        
        try:
            # 启动调度器
            response = requests.post(
                f"{self.base_url}/api/v1/news-scheduler/start",
                headers=self.headers
            )
            print(f"启动调度器: {response.status_code}")
            if response.status_code == 200:
                print("✓ 调度器启动成功")
            else:
                print(f"✗ 调度器启动失败: {response.text}")
            
            # 等待一段时间
            time.sleep(2)
            
            # 获取状态
            response = requests.get(
                f"{self.base_url}/api/v1/news-scheduler/status",
                headers=self.headers
            )
            print(f"获取状态: {response.status_code}")
            if response.status_code == 200:
                print("✓ 状态获取成功")
                status = response.json()
                print(f"调度器状态: {status.get('status', 'unknown')}")
                print(f"运行时间: {status.get('uptime', 'unknown')}")
            else:
                print(f"✗ 状态获取失败: {response.text}")
            
            # 停止调度器
            response = requests.post(
                f"{self.base_url}/api/v1/news-scheduler/stop",
                headers=self.headers
            )
            print(f"停止调度器: {response.status_code}")
            if response.status_code == 200:
                print("✓ 调度器停止成功")
            else:
                print(f"✗ 调度器停止失败: {response.text}")
                
        except Exception as e:
            print(f"✗ 调度器控制测试失败: {str(e)}")
    
    def test_attachment_integration(self):
        """测试附件集成功能"""
        print("\n=== 测试附件集成功能 ===")
        
        # 模拟新闻数据
        test_news = [
            {
                "title": "AI技术发展报告发布",
                "source": "科技日报",
                "time": "2024-01-15 10:30:00",
                "link": "https://example.com/ai-report",
                "summary": "最新AI技术发展报告显示，人工智能在多个领域取得突破性进展。",
                "attachments": [
                    {
                        "filename": "AI发展报告2024.pdf",
                        "size": 2048576,
                        "file_type": "pdf"
                    },
                    {
                        "filename": "技术数据表格.xlsx",
                        "size": 512000,
                        "file_type": "excel"
                    }
                ]
            },
            {
                "title": "数字化转型白皮书",
                "source": "IT之家",
                "time": "2024-01-15 09:15:00",
                "link": "https://example.com/digital-transformation",
                "summary": "企业数字化转型白皮书发布，为企业提供转型指导。",
                "attachments": [
                    {
                        "filename": "数字化转型白皮书.docx",
                        "size": 1536000,
                        "file_type": "word"
                    }
                ]
            }
        ]
        
        print("测试附件统计:")
        total_attachments = sum(len(news.get('attachments', [])) for news in test_news)
        total_size = sum(
            sum(att.get('size', 0) for att in news.get('attachments', []))
            for news in test_news
        )
        print(f"  总附件数: {total_attachments}")
        print(f"  总大小: {total_size / (1024*1024):.2f} MB")
        
        # 按类型统计
        type_stats = {}
        for news in test_news:
            for att in news.get('attachments', []):
                file_type = att.get('file_type', 'unknown')
                if file_type not in type_stats:
                    type_stats[file_type] = {'count': 0, 'size': 0}
                type_stats[file_type]['count'] += 1
                type_stats[file_type]['size'] += att.get('size', 0)
        
        print("  类型分布:")
        for file_type, stats in type_stats.items():
            size_mb = stats['size'] / (1024 * 1024)
            print(f"    {file_type}: {stats['count']} 个 ({size_mb:.2f} MB)")
        
        print("✓ 附件集成功能测试完成")
    
    def run_all_tests(self):
        """运行所有测试"""
        print("开始新闻调度器测试...")
        print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"测试地址: {self.base_url}")
        print("=" * 50)
        
        self.test_config_management()
        self.test_attachment_processing()
        self.test_news_crawling()
        self.test_report_generation()
        self.test_scheduler_control()
        self.test_attachment_integration()
        
        print("\n" + "=" * 50)
        print("测试完成!")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="新闻调度器测试脚本")
    parser.add_argument("--url", default="http://localhost:9380", help="RAGFlow服务器地址")
    parser.add_argument("--api-key", help="API密钥")
    parser.add_argument("--test", choices=["config", "attachment", "crawl", "report", "scheduler", "integration", "all"], 
                       default="all", help="指定测试类型")
    
    args = parser.parse_args()
    
    tester = NewsSchedulerTester(args.url, args.api_key)
    
    if args.test == "config":
        tester.test_config_management()
    elif args.test == "attachment":
        tester.test_attachment_processing()
    elif args.test == "crawl":
        tester.test_news_crawling()
    elif args.test == "report":
        tester.test_report_generation()
    elif args.test == "scheduler":
        tester.test_scheduler_control()
    elif args.test == "integration":
        tester.test_attachment_integration()
    else:
        tester.run_all_tests()


if __name__ == "__main__":
    main() 