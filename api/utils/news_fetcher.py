"""
新闻收集器 - 基于抽象接口的两阶段架构

重构后的版本，使用标准Python接口和API Key认证
"""

import os
import json
import tempfile
import shutil
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import asdict

# 导入抽象接口
from ..interfaces.news_crawler_interface import (
    INewsCrawler, INewsTaskExecutor, IRAGFlowIntegration,
    NewsSource, NewsArticle, CrawlTask, CrawlResult, CrawlerStatus
)

# 导入认证装饰器
from ..auth.api_key_auth import require_news_read, require_news_write


class NewsTaskExecutor:
    """新闻抓取任务执行器 - 集成外部爬虫工具"""
    
    def __init__(self, crawler_config: Dict[str, Any] = None):
        """
        初始化任务执行器
        
        Args:
            crawler_config: 爬虫工具配置
        """
        self.crawler_config = crawler_config or {
            "type": "demo",  # demo|scrapy|selenium|custom
            "command": None,
            "timeout": 300
        }
    
    def execute_task(self, task_config: Dict[str, Any], 
                    sources_config: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        执行新闻抓取任务
        
        Args:
            task_config: 任务配置
            sources_config: 新闻源配置列表
            
        Returns:
            执行结果统计
        """
        output_dir = task_config.get("output_directory", "/tmp/news_crawl")
        
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(os.path.join(output_dir, "sources"), exist_ok=True)
        os.makedirs(os.path.join(output_dir, "logs"), exist_ok=True)
        
        # 根据爬虫类型执行不同的策略
        crawler_type = self.crawler_config.get("type", "demo")
        
        if crawler_type == "demo":
            return self._execute_demo_crawler(task_config, sources_config, output_dir)
        elif crawler_type == "external":
            return self._execute_external_crawler(task_config, sources_config, output_dir)
        else:
            raise ValueError(f"不支持的爬虫类型: {crawler_type}")
    
    def _execute_demo_crawler(self, task_config: Dict[str, Any], 
                            sources_config: List[Dict[str, Any]], 
                            output_dir: str) -> Dict[str, Any]:
        """执行演示爬虫 - 生成示例文件"""
        
        results = {
            "total_articles": 0,
            "success_count": 0,
            "failed_count": 0,
            "output_directory": output_dir,
            "articles": []
        }
        
        max_articles_per_source = task_config.get("max_articles_per_source", 5)
        
        for source_config in sources_config:
            source_name = source_config.get("name", "未知来源")
            source_url = source_config.get("url", "")
            
            # 为每个新闻源创建目录
            source_dir = os.path.join(output_dir, "sources", source_name)
            os.makedirs(source_dir, exist_ok=True)
            
            # 生成示例文章
            articles = self._generate_demo_articles(source_name, source_url, max_articles_per_source)
            
            # 保存文章到文件
            for i, article in enumerate(articles):
                filename = f"{self._sanitize_filename(article['title'])}.md"
                filepath = os.path.join(source_dir, filename)
                
                try:
                    content = self._format_article_markdown(article)
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(content)
                    
                    results["articles"].append({
                        "title": article["title"],
                        "file_path": filepath,
                        "source": source_name
                    })
                    results["success_count"] += 1
                    
                except Exception as e:
                    logger.error(f"保存文章失败: {e}")
                    results["failed_count"] += 1
            
            # 保存新闻源信息
            source_info = {
                "source_id": source_config.get("id", "demo"),
                "name": source_name,
                "url": source_url,
                "crawled_at": datetime.now().isoformat(),
                "articles_count": len(articles),
                "success_count": len(articles),
                "failed_count": 0
            }
            
            with open(os.path.join(source_dir, "source_info.json"), 'w', encoding='utf-8') as f:
                json.dump(source_info, f, ensure_ascii=False, indent=2)
            
            results["total_articles"] += len(articles)
        
        # 保存任务元数据
        metadata = {
            "task_id": task_config.get("task_id", "demo"),
            "created_at": datetime.now().isoformat(),
            "crawler_version": "demo-1.0.0",
            "total_sources": len(sources_config),
            "total_articles": results["total_articles"],
            "status": "completed"
        }
        
        with open(os.path.join(output_dir, "metadata.json"), 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
        
        logger.info(f"演示爬虫完成: 生成 {results['total_articles']} 篇文章到 {output_dir}")
        return results
    
    def _execute_external_crawler(self, task_config: Dict[str, Any], 
                                 sources_config: List[Dict[str, Any]], 
                                 output_dir: str) -> Dict[str, Any]:
        """执行外部爬虫工具"""
        
        command = self.crawler_config.get("command")
        if not command:
            raise ValueError("外部爬虫命令未配置")
        
        # 准备爬虫配置文件
        crawler_config_file = os.path.join(output_dir, "crawler_config.json")
        with open(crawler_config_file, 'w', encoding='utf-8') as f:
            json.dump({
                "task_config": task_config,
                "sources": sources_config,
                "output_directory": output_dir
            }, f, ensure_ascii=False, indent=2)
        
        try:
            # 执行外部爬虫命令
            cmd = command.format(
                config_file=crawler_config_file,
                output_dir=output_dir
            )
            
            logger.info(f"执行外部爬虫: {cmd}")
            result = subprocess.run(
                cmd, 
                shell=True, 
                timeout=self.crawler_config.get("timeout", 300),
                capture_output=True,
                text=True
            )
            
            if result.returncode != 0:
                raise RuntimeError(f"爬虫执行失败: {result.stderr}")
            
            # 读取爬虫结果
            metadata_file = os.path.join(output_dir, "metadata.json")
            if os.path.exists(metadata_file):
                with open(metadata_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                return {
                    "total_articles": metadata.get("total_articles", 0),
                    "success_count": metadata.get("total_articles", 0),
                    "failed_count": 0,
                    "output_directory": output_dir
                }
            else:
                raise RuntimeError("爬虫未生成元数据文件")
                
        except subprocess.TimeoutExpired:
            raise RuntimeError("爬虫执行超时")
        except Exception as e:
            logger.error(f"外部爬虫执行失败: {e}")
            raise
    
    def _generate_demo_articles(self, source_name: str, source_url: str, count: int) -> List[Dict[str, Any]]:
        """生成演示文章"""
        base_titles = [
            "人工智能技术突破新进展",
            "5G网络建设加速推进", 
            "云计算市场竞争激烈",
            "区块链技术应用广泛",
            "物联网设备快速增长",
            "大数据分析能力提升",
            "网络安全威胁增加",
            "虚拟现实技术成熟",
            "自动驾驶汽车测试",
            "量子计算研究进展"
        ]
        
        articles = []
        for i in range(min(count, len(base_titles))):
            title = f"{base_titles[i]} - {source_name}报道"
            content = f"""
近日，{base_titles[i]}成为行业关注的焦点。据{source_name}报道，相关技术发展迅速，市场前景广阔。

## 技术背景

{base_titles[i]}作为当前科技发展的重要方向，正在各个领域展现出巨大的应用潜力。专家表示，这一技术的发展将对整个行业产生深远影响。

## 市场前景

业内分析师认为，随着技术的不断成熟，{base_titles[i]}的市场规模将在未来几年内迎来快速增长期。

## 未来展望

专家预测，{base_titles[i]}将在以下几个方面实现重大突破：
1. 技术性能的显著提升
2. 应用场景的不断扩展  
3. 成本的进一步降低
4. 产业生态的日趋完善

这些发展将为相关行业带来新的机遇和挑战。
            """.strip()
            
            articles.append({
                "title": title,
                "content": content,
                "url": f"{source_url}#demo-{i+1}",
                "author": f"{source_name}编辑部",
                "publish_time": datetime.now().isoformat(),
                "source": source_name,
                "category": "科技",
                "tags": ["科技", "发展", "趋势"]
            })
        
        return articles
    
    def _format_article_markdown(self, article: Dict[str, Any]) -> str:
        """格式化文章为Markdown格式"""
        frontmatter = f"""---
title: "{article['title']}"
url: "{article['url']}"
author: "{article.get('author', '未知')}"
publish_time: "{article.get('publish_time', '')}"
source: "{article.get('source', '')}"
category: "{article.get('category', '')}"
tags: {json.dumps(article.get('tags', []), ensure_ascii=False)}
crawled_at: "{datetime.now().isoformat()}"
---

"""
        
        return frontmatter + f"# {article['title']}\n\n" + article['content']
    
    def _sanitize_filename(self, title: str) -> str:
        """清理文件名，移除非法字符"""
        import re
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', title)
        if len(sanitized) > 100:
            sanitized = sanitized[:100]
        return sanitized
