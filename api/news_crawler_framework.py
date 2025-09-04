#!/usr/bin/env python3
"""
新闻爬虫框架 - 爬虫和上传分离架构

这个框架将新闻抓取和文件上传完全分离，便于独立开发和测试。
采用工厂模式设计，方便扩展新的爬虫类型。
"""

import os
import json
import time
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime


class CrawlerResult:
    """爬虫结果数据结构"""
    
    def __init__(self):
        self.success = False
        self.articles = []
        self.errors = []
        self.metadata = {}
        self.crawl_time = datetime.now().isoformat()
    
    def add_article(self, article: Dict[str, Any]):
        """添加文章"""
        self.articles.append(article)
    
    def add_error(self, error: str):
        """添加错误信息"""
        self.errors.append(error)
    
    def set_metadata(self, key: str, value: Any):
        """设置元数据"""
        self.metadata[key] = value
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "success": self.success,
            "articles": self.articles,
            "errors": self.errors,
            "metadata": self.metadata,
            "crawl_time": self.crawl_time,
            "total_articles": len(self.articles),
            "error_count": len(self.errors)
        }


class NewsSource:
    """新闻源配置"""
    
    def __init__(self, name: str, url: str, config: Dict[str, Any] = None):
        self.name = name
        self.url = url
        self.config = config or {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "url": self.url,
            "config": self.config
        }


class BaseCrawler(ABC):
    """爬虫基类"""
    
    def __init__(self, crawler_config: Dict[str, Any] = None):
        self.config = crawler_config or {}
        self.name = self.__class__.__name__
    
    @abstractmethod
    def crawl_source(self, source: NewsSource, max_articles: int = 10) -> CrawlerResult:
        """
        抓取单个新闻源
        
        Args:
            source: 新闻源配置
            max_articles: 最大文章数
            
        Returns:
            CrawlerResult: 抓取结果
        """
        pass
    
    def crawl_multiple_sources(self, sources: List[NewsSource], max_articles: int = 10) -> CrawlerResult:
        """
        抓取多个新闻源
        
        Args:
            sources: 新闻源列表
            max_articles: 每个源的最大文章数
            
        Returns:
            CrawlerResult: 合并的抓取结果
        """
        combined_result = CrawlerResult()
        
        for source in sources:
            try:
                result = self.crawl_source(source, max_articles)
                
                # 合并结果
                combined_result.articles.extend(result.articles)
                combined_result.errors.extend(result.errors)
                
                # 合并元数据
                source_key = f"source_{source.name}"
                combined_result.metadata[source_key] = result.metadata
                
            except Exception as e:
                combined_result.add_error(f"抓取源 {source.name} 失败: {str(e)}")
        
        combined_result.success = len(combined_result.articles) > 0
        return combined_result


class DemoCrawler(BaseCrawler):
    """演示爬虫 - 生成模拟新闻数据"""
    
    def crawl_source(self, source: NewsSource, max_articles: int = 10) -> CrawlerResult:
        result = CrawlerResult()
        
        try:
            # 生成演示文章
            for i in range(max_articles):
                article = {
                    "title": f"【演示新闻】{source.name}重要新闻 {i+1}",
                    "content": f"""
这是来自 {source.name} 的重要新闻内容 {i+1}。

## 新闻摘要
这是一条演示新闻，展示了新闻爬虫系统的基本功能。本新闻包含标题、正文、来源、时间等完整信息。

## 详细内容
在这个演示中，我们展示了：
1. 新闻标题的正确提取
2. 新闻正文的完整获取
3. 发布时间的准确记录
4. 来源信息的正确标注

## 技术特点
- 支持多种新闻源格式
- 自动内容清洗和格式化
- 智能去重和质量过滤
- 完整的错误处理机制

这条新闻展示了系统的完整功能链路。
                    """.strip(),
                    "url": f"{source.url}/article-{i+1}",
                    "source": source.name,
                    "author": "演示作者",
                    "publish_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "crawl_time": datetime.now().isoformat(),
                    "category": "演示分类",
                    "tags": ["演示", "新闻", "测试"]
                }
                result.add_article(article)
            
            result.success = True
            result.set_metadata("crawler_type", "demo")
            result.set_metadata("source_url", source.url)
            
        except Exception as e:
            result.add_error(f"演示爬虫执行失败: {str(e)}")
        
        return result


class NewspaperCrawler(BaseCrawler):
    """基于newspaper3k的爬虫"""
    
    def crawl_source(self, source: NewsSource, max_articles: int = 10) -> CrawlerResult:
        result = CrawlerResult()
        
        try:
            import newspaper
            from newspaper import Article
            
            # 获取新闻站点
            paper = newspaper.build(source.url, language='zh')
            
            article_count = 0
            for article_url in paper.article_urls()[:max_articles * 2]:  # 获取更多URL以防解析失败
                if article_count >= max_articles:
                    break
                
                try:
                    article = Article(article_url, language='zh')
                    article.download()
                    article.parse()
                    
                    if article.text and article.title:
                        article_data = {
                            "title": article.title,
                            "content": article.text,
                            "url": article_url,
                            "source": source.name,
                            "author": ", ".join(article.authors) if article.authors else "未知",
                            "publish_time": article.publish_date.strftime("%Y-%m-%d %H:%M:%S") if article.publish_date else "未知",
                            "crawl_time": datetime.now().isoformat(),
                            "summary": article.summary if hasattr(article, 'summary') else "",
                            "image": article.top_image if article.top_image else ""
                        }
                        result.add_article(article_data)
                        article_count += 1
                
                except Exception as e:
                    result.add_error(f"解析文章失败 {article_url}: {str(e)}")
                    continue
            
            result.success = article_count > 0
            result.set_metadata("crawler_type", "newspaper3k")
            result.set_metadata("source_url", source.url)
            
        except ImportError:
            result.add_error("newspaper3k库未安装，请运行: pip install newspaper3k")
        except Exception as e:
            result.add_error(f"Newspaper爬虫执行失败: {str(e)}")
        
        return result


class ScrapyCrawler(BaseCrawler):
    """基于Scrapy的爬虫"""
    
    def crawl_source(self, source: NewsSource, max_articles: int = 10) -> CrawlerResult:
        result = CrawlerResult()
        
        try:
            # 这里是Scrapy实现的占位符
            # 实际实现需要根据具体的新闻站点编写Spider
            result.add_error("Scrapy爬虫需要根据具体站点实现")
            result.set_metadata("crawler_type", "scrapy")
            result.set_metadata("source_url", source.url)
            
        except Exception as e:
            result.add_error(f"Scrapy爬虫执行失败: {str(e)}")
        
        return result


class CrawlerFactory:
    """爬虫工厂类"""
    
    _crawlers = {
        "demo": DemoCrawler,
        "newspaper": NewspaperCrawler,
        "newspaper3k": NewspaperCrawler,
        "scrapy": ScrapyCrawler
    }
    
    @classmethod
    def create_crawler(cls, crawler_type: str, config: Dict[str, Any] = None) -> BaseCrawler:
        """
        创建爬虫实例
        
        Args:
            crawler_type: 爬虫类型 (demo, newspaper, scrapy)
            config: 爬虫配置
            
        Returns:
            BaseCrawler: 爬虫实例
        """
        if crawler_type not in cls._crawlers:
            raise ValueError(f"不支持的爬虫类型: {crawler_type}")
        
        crawler_class = cls._crawlers[crawler_type]
        return crawler_class(config)
    
    @classmethod
    def get_available_crawlers(cls) -> List[str]:
        """获取可用的爬虫类型"""
        return list(cls._crawlers.keys())
    
    @classmethod
    def register_crawler(cls, name: str, crawler_class: type):
        """注册新的爬虫类型"""
        if not issubclass(crawler_class, BaseCrawler):
            raise ValueError("爬虫类必须继承自BaseCrawler")
        cls._crawlers[name] = crawler_class


class NewsUploader:
    """新闻上传器 - 将抓取结果上传到RAGFlow"""
    
    def __init__(self, api_key: str, base_url: str = "http://localhost:9380"):
        self.api_key = api_key
        self.base_url = base_url
    
    def upload_crawler_result(self, crawler_result: CrawlerResult, kb_id: str, 
                            output_dir: str = None) -> Dict[str, Any]:
        """
        上传爬虫结果到RAGFlow
        
        Args:
            crawler_result: 爬虫结果
            kb_id: 知识库ID
            output_dir: 输出目录（可选，用于调试）
            
        Returns:
            Dict: 上传结果
        """
        try:
            from ragflow_sdk import RAGFlow
            
            # 初始化SDK客户端
            rag = RAGFlow(api_key=self.api_key, base_url=self.base_url)
            dataset = rag.get_dataset_by_id(kb_id)
            
            if not dataset:
                return {
                    "success": False,
                    "error": f"无法获取知识库: {kb_id}",
                    "uploaded_files": 0
                }
            
            # 创建临时目录
            import tempfile
            import shutil
            from uuid import uuid4
            
            temp_dir = os.path.join(tempfile.gettempdir(), f"news_upload_{uuid4().hex[:8]}")
            os.makedirs(temp_dir, exist_ok=True)
            
            try:
                uploaded_files = []
                
                # 保存文章为Markdown文件
                for i, article in enumerate(crawler_result.articles):
                    file_name = self._generate_filename(article, i)
                    file_path = os.path.join(temp_dir, file_name)
                    
                    # 生成Markdown内容
                    markdown_content = self._article_to_markdown(article)
                    
                    # 写入文件
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(markdown_content)
                    
                    uploaded_files.append({
                        "name": file_name,
                        "path": file_path,
                        "size": len(markdown_content.encode('utf-8'))
                    })
                
                # 如果指定了输出目录，复制文件
                if output_dir:
                    os.makedirs(output_dir, exist_ok=True)
                    for file_info in uploaded_files:
                        shutil.copy2(file_info["path"], output_dir)
                
                # 使用SDK上传文件夹
                if uploaded_files:
                    upload_result = dataset.upload_folder(temp_dir, "", auto_parse=True)
                    
                    # 处理上传结果
                    upload_data = upload_result.get('upload_result', {}).get('data', [])
                    
                    return {
                        "success": True,
                        "uploaded_files": len(upload_data),
                        "files": upload_data,
                        "parse_started": upload_result.get('parse_result', {}).get('status') == 'started',
                        "crawler_result": crawler_result.to_dict()
                    }
                
                return {
                    "success": True,
                    "uploaded_files": 0,
                    "files": [],
                    "crawler_result": crawler_result.to_dict()
                }
                
            finally:
                # 清理临时目录
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "uploaded_files": 0,
                "crawler_result": crawler_result.to_dict()
            }
    
    def _generate_filename(self, article: Dict[str, Any], index: int) -> str:
        """生成文件名"""
        title = article.get('title', f'文章{index+1}')
        # 清理文件名
        safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_', '【', '】')).strip()
        if len(safe_title) > 100:
            safe_title = safe_title[:100]
        return f"{safe_title}.md"
    
    def _article_to_markdown(self, article: Dict[str, Any]) -> str:
        """将文章转换为Markdown格式"""
        lines = [
            f"# {article.get('title', '无标题')}",
            "",
            f"**来源**: {article.get('source', '未知')}",
            f"**作者**: {article.get('author', '未知')}",
            f"**发布时间**: {article.get('publish_time', '未知')}",
            f"**链接**: {article.get('url', '')}",
            ""
        ]
        
        # 添加摘要
        if article.get('summary'):
            lines.extend([
                "## 摘要",
                "",
                article['summary'],
                ""
            ])
        
        # 添加正文
        lines.extend([
            "## 正文",
            "",
            article.get('content', '无内容'),
            ""
        ])
        
        # 添加标签
        if article.get('tags'):
            tags = ", ".join(article['tags'])
            lines.extend([
                f"**标签**: {tags}",
                ""
            ])
        
        # 添加元数据
        lines.extend([
            "---",
            "",
            f"*抓取时间: {article.get('crawl_time', '')}*",
            f"*分类: {article.get('category', '未分类')}*"
        ])
        
        return "\n".join(lines)


# 便捷函数
def create_news_source(name: str, url: str, **config) -> NewsSource:
    """创建新闻源"""
    return NewsSource(name, url, config)


def crawl_news(sources: List[NewsSource], crawler_type: str = "demo", 
               max_articles: int = 10, crawler_config: Dict[str, Any] = None) -> CrawlerResult:
    """
    爬取新闻的便捷函数
    
    Args:
        sources: 新闻源列表
        crawler_type: 爬虫类型
        max_articles: 每个源的最大文章数
        crawler_config: 爬虫配置
        
    Returns:
        CrawlerResult: 爬取结果
    """
    crawler = CrawlerFactory.create_crawler(crawler_type, crawler_config)
    return crawler.crawl_multiple_sources(sources, max_articles)


def upload_news(crawler_result: CrawlerResult, kb_id: str, api_key: str, 
                base_url: str = "http://localhost:9380") -> Dict[str, Any]:
    """
    上传新闻的便捷函数
    
    Args:
        crawler_result: 爬虫结果
        kb_id: 知识库ID
        api_key: API密钥
        base_url: RAGFlow服务地址
        
    Returns:
        Dict: 上传结果
    """
    uploader = NewsUploader(api_key, base_url)
    return uploader.upload_crawler_result(crawler_result, kb_id)


if __name__ == "__main__":
    # 示例用法
    print("新闻爬虫框架示例")
    
    # 创建新闻源
    sources = [
        create_news_source("示例新闻站", "https://example.com/news"),
        create_news_source("测试新闻站", "https://test.com/news")
    ]
    
    # 爬取新闻
    result = crawl_news(sources, crawler_type="demo", max_articles=3)
    
    print(f"爬取结果: {result.to_dict()}")
