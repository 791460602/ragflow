"""
新闻收集器Python抽象接口

定义了标准的新闻爬虫接口，确保所有爬虫工具遵循统一规范
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class CrawlerStatus(Enum):
    """爬虫状态枚举"""
    PENDING = "pending"
    RUNNING = "running" 
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class NewsSource:
    """新闻源数据结构"""
    id: str
    name: str
    url: str
    crawler_config: Dict[str, Any]
    status: str = "active"


@dataclass 
class NewsArticle:
    """新闻文章数据结构"""
    title: str
    content: str
    url: str
    author: Optional[str] = None
    publish_time: Optional[datetime] = None
    category: Optional[str] = None
    tags: List[str] = None
    summary: Optional[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []


@dataclass
class CrawlTask:
    """爬虫任务配置"""
    task_id: str
    sources: List[NewsSource]
    output_directory: str
    max_articles_per_source: int = 10
    output_format: str = "markdown"  # markdown|json|text
    include_images: bool = False
    content_min_length: int = 100
    timeout: int = 300


@dataclass
class CrawlResult:
    """爬虫执行结果"""
    task_id: str
    status: CrawlerStatus
    total_articles: int = 0
    success_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    output_directory: str = ""
    error_message: Optional[str] = None
    execution_time: Optional[float] = None
    articles: List[NewsArticle] = None
    
    def __post_init__(self):
        if self.articles is None:
            self.articles = []


class INewsCrawler(ABC):
    """新闻爬虫抽象接口"""
    
    @abstractmethod
    def validate_source(self, source: NewsSource) -> bool:
        """
        验证新闻源是否有效
        
        Args:
            source: 新闻源配置
            
        Returns:
            bool: 是否有效
        """
        pass
    
    @abstractmethod
    def crawl_articles(self, task: CrawlTask) -> CrawlResult:
        """
        执行新闻抓取任务
        
        Args:
            task: 爬虫任务配置
            
        Returns:
            CrawlResult: 抓取结果
        """
        pass
    
    @abstractmethod 
    def get_supported_domains(self) -> List[str]:
        """
        获取支持的域名列表
        
        Returns:
            List[str]: 支持的域名
        """
        pass
    
    def save_articles_to_directory(self, articles: List[NewsArticle], 
                                  output_dir: str, source_name: str) -> bool:
        """
        保存文章到指定目录（提供默认实现）
        
        Args:
            articles: 文章列表
            output_dir: 输出目录
            source_name: 新闻源名称
            
        Returns:
            bool: 是否成功
        """
        import os
        import json
        from datetime import datetime
        
        # 写入调试日志文件
        debug_log_path = f"/tmp/news_crawler_debug_{datetime.now().strftime('%H%M%S')}.log"
        
        def log_debug(message):
            try:
                with open(debug_log_path, 'a', encoding='utf-8') as f:
                    f.write(f"{datetime.now().isoformat()} - {message}\n")
            except:
                pass
        
        log_debug(f"开始保存文章: {len(articles)} 篇到 {output_dir}")
        
        try:
            # 创建新闻源目录
            source_dir = os.path.join(output_dir, "sources", source_name)
            log_debug(f"创建目录: {source_dir}")
            os.makedirs(source_dir, exist_ok=True)
            
            # 检查目录权限
            if not os.access(source_dir, os.W_OK):
                log_debug(f"❌ 没有写入权限: {source_dir}")
                return False
            
            log_debug(f"目录创建成功，开始保存文章")
            
            # 保存每篇文章
            for i, article in enumerate(articles):
                filename = self._sanitize_filename(f"{article.title}.md")
                filepath = os.path.join(source_dir, filename)
                log_debug(f"保存文章 {i+1}: {filepath}")
                
                # 生成Markdown内容
                try:
                    content = self._format_article_markdown(article)
                    log_debug(f"内容生成成功，长度: {len(content)}")
                except Exception as format_error:
                    log_debug(f"❌ 内容格式化失败: {format_error}")
                    return False
                
                try:
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(content)
                    log_debug(f"✅ 文章保存成功: {filename}")
                except Exception as file_error:
                    log_debug(f"❌ 文件写入失败: {filename} - {file_error}")
                    return False
            
            # 保存新闻源信息
            source_info = {
                "name": source_name,
                "crawled_at": datetime.now().isoformat(),
                "articles_count": len(articles),
                "success_count": len(articles),
                "failed_count": 0
            }
            
            info_path = os.path.join(source_dir, "source_info.json")
            try:
                with open(info_path, 'w', encoding='utf-8') as f:
                    json.dump(source_info, f, ensure_ascii=False, indent=2)
                log_debug(f"✅ 源信息保存成功: {info_path}")
            except Exception as info_error:
                log_debug(f"⚠️  源信息保存失败: {info_error}")
                # 这个不是致命错误，继续执行
            
            log_debug(f"✅ 所有文章保存完成: {len(articles)} 篇")
            return True
            
        except Exception as e:
            log_debug(f"❌ 保存文章失败: {e}")
            import traceback
            log_debug(f"堆栈跟踪: {traceback.format_exc()}")
            return False
    
    def _sanitize_filename(self, filename: str) -> str:
        """清理文件名"""
        import re
        sanitized = re.sub(r'[<>:"/\\|?*]', '_', filename)
        return sanitized[:100] if len(sanitized) > 100 else sanitized
    
    def _format_article_markdown(self, article: NewsArticle) -> str:
        """格式化文章为Markdown"""
        import json
        from datetime import datetime
        
        frontmatter = f"""---
title: "{article.title}"
url: "{article.url}"
author: "{article.author or '未知'}"
publish_time: "{article.publish_time.isoformat() if article.publish_time else ''}"
category: "{article.category or ''}"
tags: {json.dumps(article.tags, ensure_ascii=False)}
summary: "{article.summary or ''}"
crawled_at: "{datetime.now().isoformat()}"
---

"""
        return frontmatter + f"# {article.title}\n\n" + article.content


class INewsTaskExecutor(ABC):
    """新闻任务执行器抽象接口"""
    
    @abstractmethod
    def register_crawler(self, crawler: INewsCrawler, domains: List[str] = None):
        """
        注册爬虫实现
        
        Args:
            crawler: 爬虫实例  
            domains: 支持的域名（可选，默认使用爬虫的get_supported_domains）
        """
        pass
    
    @abstractmethod
    def execute_task(self, task: CrawlTask) -> CrawlResult:
        """
        执行爬虫任务
        
        Args:
            task: 任务配置
            
        Returns:
            CrawlResult: 执行结果
        """
        pass
    
    @abstractmethod
    def get_task_status(self, task_id: str) -> Optional[CrawlResult]:
        """
        获取任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            Optional[CrawlResult]: 任务结果，不存在则返回None
        """
        pass


# 用于RAGFlow集成的回调接口
class IRAGFlowIntegration(ABC):
    """RAGFlow集成接口"""
    
    @abstractmethod
    def upload_crawled_directory(self, output_dir: str, kb_id: str, 
                               auto_parse: bool = True) -> Dict[str, Any]:
        """
        将爬取的目录上传到RAGFlow
        
        Args:
            output_dir: 爬虫输出目录
            kb_id: 知识库ID
            auto_parse: 是否自动解析
            
        Returns:
            Dict[str, Any]: 上传结果
        """
        pass
    
    @abstractmethod
    def create_news_source(self, name: str, url: str, 
                          crawler_config: Dict[str, Any]) -> str:
        """
        创建新闻源
        
        Args:
            name: 新闻源名称
            url: 新闻源URL
            crawler_config: 爬虫配置
            
        Returns:
            str: 新闻源ID
        """
        pass
    
    @abstractmethod
    def create_crawl_task(self, task_name: str, kb_id: str, 
                         source_ids: List[str], **kwargs) -> str:
        """
        创建爬虫任务
        
        Args:
            task_name: 任务名称
            kb_id: 知识库ID
            source_ids: 新闻源ID列表
            **kwargs: 其他任务配置
            
        Returns:
            str: 任务ID
        """
        pass
