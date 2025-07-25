#
#  新闻抓取模块
#
#  实现实际的新闻网站内容抓取功能
#

import requests
import time
import hashlib
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin, urlparse
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class NewsArticle:
    """新闻文章数据结构"""
    
    def __init__(self, title: str, content: str, url: str, 
                 author: str = None, publish_time: datetime = None):
        self.title = title
        self.content = content
        self.url = url
        self.author = author
        self.publish_time = publish_time


class NewsFetcher:
    """新闻抓取器"""
    
    def __init__(self, source_config: Dict[str, Any]):
        """
        初始化新闻抓取器
        
        Args:
            source_config: 新闻源配置，包含URL、选择器等信息
        """
        self.url = source_config.get("url")
        self.fetch_config = source_config.get("fetch_config", {})
        self.headers = self.fetch_config.get("headers", {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        self.timeout = self.fetch_config.get("timeout", 30)
        self.encoding = self.fetch_config.get("encoding", "utf-8")
        
    def fetch_article_list(self, max_articles: int = 10) -> List[Dict[str, Any]]:
        """
        抓取文章列表
        
        Args:
            max_articles: 最大抓取文章数
            
        Returns:
            包含文章信息的字典列表
        """
        try:
            response = requests.get(self.url, headers=self.headers, timeout=self.timeout)
            response.encoding = self.encoding
            
            if response.status_code != 200:
                logger.error(f"抓取失败，状态码: {response.status_code}")
                return []
            
            # 简单的文章抓取模拟
            # 在实际使用中，需要根据具体网站的HTML结构来解析
            articles = self._parse_articles(response.text, max_articles)
            
            return articles
            
        except Exception as e:
            logger.error(f"抓取文章列表失败: {e}")
            return []
    
    def _parse_articles(self, html_content: str, max_articles: int) -> List[Dict[str, Any]]:
        """
        解析HTML内容，提取文章信息
        
        这是一个简化的示例实现，实际使用中需要根据具体网站结构来实现
        """
        try:
            # 使用BeautifulSoup解析HTML（需要安装beautifulsoup4）
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(html_content, 'html.parser')
                
                articles = []
                
                # 尝试通过常见的新闻文章选择器来抓取
                selectors = [
                    'article', 'div.article', 'div.news-item', 
                    'div.post', 'div.entry', '.article-item'
                ]
                
                for selector in selectors:
                    elements = soup.select(selector)[:max_articles]
                    if elements:
                        for elem in elements:
                            article = self._extract_article_info(elem)
                            if article:
                                articles.append(article)
                        break
                
                return articles[:max_articles]
                
            except ImportError:
                # 如果没有安装BeautifulSoup，使用简单的正则表达式
                return self._simple_parse(html_content, max_articles)
                
        except Exception as e:
            logger.error(f"解析文章失败: {e}")
            return []
    
    def _extract_article_info(self, element) -> Optional[Dict[str, Any]]:
        """从HTML元素中提取文章信息"""
        try:
            # 提取标题
            title_elem = element.find(['h1', 'h2', 'h3', 'h4', '.title', '.headline'])
            title = title_elem.get_text(strip=True) if title_elem else "无标题"
            
            # 提取链接
            link_elem = element.find('a')
            if link_elem and link_elem.get('href'):
                url = urljoin(self.url, link_elem.get('href'))
            else:
                url = self.url
            
            # 提取摘要或内容预览
            content_elem = element.find(['p', '.summary', '.excerpt', '.content'])
            content = content_elem.get_text(strip=True) if content_elem else ""
            
            # 提取作者
            author_elem = element.find(['.author', '.by', '.writer'])
            author = author_elem.get_text(strip=True) if author_elem else None
            
            if not title or len(title) < 5:
                return None
                
            return {
                "title": title,
                "content": content,
                "url": url,
                "author": author,
                "publish_time": int(time.time())
            }
            
        except Exception as e:
            logger.error(f"提取文章信息失败: {e}")
            return None
    
    def _simple_parse(self, html_content: str, max_articles: int) -> List[Dict[str, Any]]:
        """简单的HTML解析（不依赖外部库）"""
        import re
        
        articles = []
        
        # 简单的标题提取
        title_pattern = r'<(?:h[1-6]|title)[^>]*>([^<]+)</(?:h[1-6]|title)>'
        titles = re.findall(title_pattern, html_content, re.IGNORECASE)
        
        # 简单的链接提取
        link_pattern = r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>([^<]+)</a>'
        links = re.findall(link_pattern, html_content, re.IGNORECASE)
        
        # 组合文章信息
        for i, (title, content) in enumerate(zip(titles[:max_articles], 
                                                  ["抓取的内容摘要..."] * max_articles)):
            if len(title.strip()) > 5:
                url = links[i][0] if i < len(links) else self.url
                if not url.startswith('http'):
                    url = urljoin(self.url, url)
                    
                articles.append({
                    "title": title.strip(),
                    "content": content,
                    "url": url,
                    "author": None,
                    "publish_time": int(time.time())
                })
        
        return articles
    
    def fetch_full_article(self, article_url: str) -> Optional[str]:
        """
        抓取完整文章内容
        
        Args:
            article_url: 文章URL
            
        Returns:
            文章完整内容
        """
        try:
            response = requests.get(article_url, headers=self.headers, timeout=self.timeout)
            response.encoding = self.encoding
            
            if response.status_code != 200:
                return None
            
            # 简单的内容提取
            try:
                from bs4 import BeautifulSoup
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # 移除脚本和样式
                for script in soup(["script", "style"]):
                    script.decompose()
                
                # 尝试常见的文章内容选择器
                content_selectors = [
                    'article', '.article-content', '.post-content',
                    '.entry-content', '.main-content', '.content'
                ]
                
                for selector in content_selectors:
                    content_elem = soup.select_one(selector)
                    if content_elem:
                        return content_elem.get_text(strip=True)
                
                # 如果没有找到特定选择器，返回body内容
                body = soup.find('body')
                return body.get_text(strip=True) if body else response.text
                
            except ImportError:
                # 简单的正则表达式提取
                import re
                text = re.sub(r'<[^>]+>', '', response.text)
                return text.strip()
                
        except Exception as e:
            logger.error(f"抓取完整文章失败: {e}")
            return None


class NewsTaskExecutor:
    """新闻抓取任务执行器"""
    
    def __init__(self):
        self.session = requests.Session()
    
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
        results = {
            "total_articles": 0,
            "success_count": 0,
            "failed_count": 0,
            "skipped_count": 0,
            "articles": []
        }
        
        max_articles_per_source = task_config.get("max_articles_per_source", 10)
        
        for source_config in sources_config:
            try:
                fetcher = NewsFetcher(source_config)
                articles = fetcher.fetch_article_list(max_articles_per_source)
                
                for article_data in articles:
                    try:
                        # 如果需要，抓取完整内容
                        if task_config.get("fetch_full_content", False):
                            full_content = fetcher.fetch_full_article(article_data["url"])
                            if full_content:
                                article_data["content"] = full_content
                        
                        results["articles"].append(article_data)
                        results["success_count"] += 1
                        
                    except Exception as e:
                        logger.error(f"处理文章失败: {e}")
                        results["failed_count"] += 1
                
                results["total_articles"] += len(articles)
                
                # 添加延迟避免过于频繁的请求
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"抓取新闻源失败: {e}")
                results["failed_count"] += 1
        
        return results
