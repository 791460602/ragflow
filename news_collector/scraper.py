"""
新闻抓取器模块

提供网页内容抓取、解析和提取功能
"""

import asyncio
import re
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from urllib.parse import urljoin, urlparse
import logging

try:
    import aiohttp
except ImportError:
    aiohttp = None

try:
    from bs4 import BeautifulSoup, Tag
except ImportError:
    BeautifulSoup = None
    Tag = None

from .models import NewsSource, NewsContent, SelectorConfig


logger = logging.getLogger(__name__)


class NewsScraper:
    """新闻抓取器"""
    
    def __init__(self, timeout: int = 30, max_concurrent: int = 10):
        """
        初始化抓取器
        
        Args:
            timeout: 请求超时时间（秒）
            max_concurrent: 最大并发数
        """
        self.timeout = timeout
        self.max_concurrent = max_concurrent
        self.session: Optional[aiohttp.ClientSession] = None
        self.semaphore = asyncio.Semaphore(max_concurrent)
        
        # 默认请求头
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
    
    async def __aenter__(self):
        """异步上下文管理器入口"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout),
            headers=self.headers
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self.session:
            await self.session.close()
    
    async def fetch_page(self, url: str) -> Optional[str]:
        """
        获取单个页面内容
        
        Args:
            url: 页面URL
            
        Returns:
            页面HTML内容，失败返回None
        """
        async with self.semaphore:
            try:
                if not self.session:
                    raise RuntimeError("Session not initialized. Use async context manager.")
                
                async with self.session.get(url) as response:
                    if response.status == 200:
                        content = await response.text(encoding='utf-8')
                        logger.info(f"Successfully fetched: {url}")
                        return content
                    else:
                        logger.warning(f"Failed to fetch {url}: HTTP {response.status}")
                        return None
                        
            except asyncio.TimeoutError:
                logger.error(f"Timeout fetching {url}")
                return None
            except Exception as e:
                logger.error(f"Error fetching {url}: {str(e)}")
                return None
    
    def extract_links(self, html: str, base_url: str, selector_config: SelectorConfig) -> List[str]:
        """
        从HTML中提取文章链接
        
        Args:
            html: HTML内容
            base_url: 基础URL
            selector_config: 选择器配置
            
        Returns:
            文章链接列表
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')
            links = []
            
            # 使用配置的链接选择器
            link_elements = soup.select(selector_config.link_selector)
            
            for link in link_elements:
                if isinstance(link, Tag):
                    href = link.get('href')
                    if href:
                        # 转换为绝对URL
                        absolute_url = urljoin(base_url, href)
                        
                        # 简单的文章URL过滤（可以根据需要调整）
                        if self._is_article_url(absolute_url):
                            links.append(absolute_url)
            
            # 去重并限制数量
            unique_links = list(set(links))
            logger.info(f"Extracted {len(unique_links)} unique links from {base_url}")
            return unique_links
            
        except Exception as e:
            logger.error(f"Error extracting links from {base_url}: {str(e)}")
            return []
    
    def _is_article_url(self, url: str) -> bool:
        """
        判断是否为文章URL
        
        Args:
            url: URL字符串
            
        Returns:
            是否为文章URL
        """
        # 简单的文章URL判断逻辑，可以根据需要扩展
        article_patterns = [
            r'/news/',
            r'/article/',
            r'/\d{4}/',  # 包含年份
            r'/\d{6}/',  # 包含年月
            r'/\d{8}/',  # 包含年月日
        ]
        
        for pattern in article_patterns:
            if re.search(pattern, url):
                return True
        
        # 排除明显不是文章的URL
        exclude_patterns = [
            r'\.(css|js|jpg|jpeg|png|gif|pdf|zip)$',
            r'/(login|register|search|tag|category)/',
            r'#',
            r'\?.*page=',
        ]
        
        for pattern in exclude_patterns:
            if re.search(pattern, url, re.IGNORECASE):
                return False
        
        return True
    
    def extract_article_content(self, html: str, url: str, selector_config: SelectorConfig) -> Optional[NewsContent]:
        """
        从HTML中提取文章内容
        
        Args:
            html: HTML内容
            url: 文章URL
            selector_config: 选择器配置
            
        Returns:
            新闻内容对象，失败返回None
        """
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # 提取标题
            title = self._extract_title(soup, selector_config.title_selector)
            if not title:
                logger.warning(f"No title found for {url}")
                return None
            
            # 提取内容
            content_html, content_text = self._extract_content(soup, selector_config.content_selector)
            if not content_text:
                logger.warning(f"No content found for {url}")
                return None
            
            # 提取发布时间
            publish_time = self._extract_publish_time(soup, selector_config.time_selector)
            
            # 提取作者
            author = self._extract_author(soup, selector_config.author_selector)
            
            # 生成摘要（取前200个字符）
            summary = content_text[:200] + "..." if len(content_text) > 200 else content_text
            
            # 创建NewsContent对象
            news_content = NewsContent(
                title=title.strip(),
                content_html=content_html,
                content_text=content_text.strip(),
                summary=summary,
                url=url,
                publish_time=publish_time,
                metadata={
                    "author": author,
                    "word_count": len(content_text),
                    "extracted_at": datetime.now().isoformat()
                }
            )
            
            logger.info(f"Successfully extracted article: {title[:50]}...")
            return news_content
            
        except Exception as e:
            logger.error(f"Error extracting content from {url}: {str(e)}")
            return None
    
    def _extract_title(self, soup: BeautifulSoup, selector: str) -> Optional[str]:
        """提取标题"""
        try:
            # 尝试使用配置的选择器
            title_element = soup.select_one(selector)
            if title_element:
                return title_element.get_text(strip=True)
            
            # 备用方案：使用常见的标题选择器
            fallback_selectors = ['h1', 'title', '.title', '.headline', '.article-title']
            for sel in fallback_selectors:
                element = soup.select_one(sel)
                if element:
                    text = element.get_text(strip=True)
                    if text and len(text) > 5:  # 标题应该有一定长度
                        return text
            
            return None
        except Exception as e:
            logger.error(f"Error extracting title: {str(e)}")
            return None
    
    def _extract_content(self, soup: BeautifulSoup, selector: str) -> Tuple[str, str]:
        """提取内容（HTML和纯文本）"""
        try:
            # 尝试使用配置的选择器
            content_elements = soup.select(selector)
            
            if not content_elements:
                # 备用方案：使用常见的内容选择器
                fallback_selectors = [
                    '.content', '.article-content', '.post-content', 
                    '.article-body', '.post-body', '.text', 'article'
                ]
                for sel in fallback_selectors:
                    content_elements = soup.select(sel)
                    if content_elements:
                        break
            
            if content_elements:
                # 合并所有内容元素
                html_parts = []
                text_parts = []
                
                for element in content_elements:
                    # 清理不需要的元素
                    for unwanted in element.select('script, style, .ad, .advertisement, .share'):
                        unwanted.decompose()
                    
                    html_parts.append(str(element))
                    text_parts.append(element.get_text(separator='\n', strip=True))
                
                content_html = '\n'.join(html_parts)
                content_text = '\n'.join(text_parts)
                
                # 清理文本
                content_text = re.sub(r'\n\s*\n', '\n\n', content_text)  # 合并多个空行
                content_text = re.sub(r'\s+', ' ', content_text)  # 合并多个空格
                
                return content_html, content_text
            
            return "", ""
            
        except Exception as e:
            logger.error(f"Error extracting content: {str(e)}")
            return "", ""
    
    def _extract_publish_time(self, soup: BeautifulSoup, selector: str) -> Optional[datetime]:
        """提取发布时间"""
        try:
            time_element = soup.select_one(selector)
            if time_element:
                time_text = time_element.get_text(strip=True)
                return self._parse_time_string(time_text)
            
            # 备用方案：查找time标签或包含时间的元素
            time_patterns = [
                'time[datetime]',
                '.time', '.date', '.publish-time', '.publish-date',
                '[class*="time"]', '[class*="date"]'
            ]
            
            for pattern in time_patterns:
                element = soup.select_one(pattern)
                if element:
                    # 优先使用datetime属性
                    datetime_attr = element.get('datetime')
                    if datetime_attr:
                        return self._parse_time_string(datetime_attr)
                    
                    # 使用文本内容
                    time_text = element.get_text(strip=True)
                    parsed_time = self._parse_time_string(time_text)
                    if parsed_time:
                        return parsed_time
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting publish time: {str(e)}")
            return None
    
    def _extract_author(self, soup: BeautifulSoup, selector: str) -> Optional[str]:
        """提取作者"""
        try:
            author_element = soup.select_one(selector)
            if author_element:
                return author_element.get_text(strip=True)
            
            # 备用方案
            author_patterns = [
                '.author', '.writer', '.byline', '[rel="author"]',
                '[class*="author"]', '[class*="writer"]'
            ]
            
            for pattern in author_patterns:
                element = soup.select_one(pattern)
                if element:
                    author = element.get_text(strip=True)
                    if author and len(author) < 50:  # 作者名不应该太长
                        return author
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting author: {str(e)}")
            return None
    
    def _parse_time_string(self, time_str: str) -> Optional[datetime]:
        """解析时间字符串"""
        if not time_str:
            return None
        
        # 常见的时间格式
        time_formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
            "%Y/%m/%d %H:%M:%S",
            "%Y/%m/%d %H:%M",
            "%Y/%m/%d",
            "%m/%d/%Y %H:%M:%S",
            "%m/%d/%Y %H:%M",
            "%m/%d/%Y",
        ]
        
        # 清理时间字符串
        time_str = re.sub(r'[^\d\-\/:\s]', '', time_str.strip())
        
        for fmt in time_formats:
            try:
                return datetime.strptime(time_str, fmt)
            except ValueError:
                continue
        
        # 尝试解析相对时间（如"2小时前"）
        relative_time = self._parse_relative_time(time_str)
        if relative_time:
            return relative_time
        
        logger.warning(f"Unable to parse time string: {time_str}")
        return None
    
    def _parse_relative_time(self, time_str: str) -> Optional[datetime]:
        """解析相对时间"""
        now = datetime.now()
        
        # 匹配"X小时前"、"X分钟前"等格式
        patterns = [
            (r'(\d+)\s*小时前', 'hours'),
            (r'(\d+)\s*分钟前', 'minutes'),
            (r'(\d+)\s*天前', 'days'),
            (r'(\d+)\s*秒前', 'seconds'),
        ]
        
        for pattern, unit in patterns:
            match = re.search(pattern, time_str)
            if match:
                amount = int(match.group(1))
                if unit == 'hours':
                    return now - timedelta(hours=amount)
                elif unit == 'minutes':
                    return now - timedelta(minutes=amount)
                elif unit == 'days':
                    return now - timedelta(days=amount)
                elif unit == 'seconds':
                    return now - timedelta(seconds=amount)
        
        return None
    
    async def scrape_news_source(self, news_source: NewsSource, max_articles: int = 100) -> List[NewsContent]:
        """
        抓取新闻源的内容
        
        Args:
            news_source: 新闻源配置
            max_articles: 最大文章数量
            
        Returns:
            新闻内容列表
        """
        articles = []
        
        try:
            # 获取主页内容
            main_page_html = await self.fetch_page(news_source.url)
            if not main_page_html:
                logger.error(f"Failed to fetch main page: {news_source.url}")
                return articles
            
            # 提取文章链接
            article_links = self.extract_links(main_page_html, news_source.url, news_source.selector_config)
            
            # 限制文章数量
            article_links = article_links[:max_articles]
            
            logger.info(f"Found {len(article_links)} article links for {news_source.name}")
            
            # 并发抓取文章内容
            tasks = []
            for link in article_links:
                task = asyncio.create_task(self._scrape_single_article(link, news_source))
                tasks.append(task)
            
            # 等待所有任务完成
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 收集成功的结果
            for result in results:
                if isinstance(result, NewsContent):
                    result.source_id = news_source.id
                    articles.append(result)
                elif isinstance(result, Exception):
                    logger.error(f"Error in article scraping: {str(result)}")
            
            logger.info(f"Successfully scraped {len(articles)} articles from {news_source.name}")
            return articles
            
        except Exception as e:
            logger.error(f"Error scraping news source {news_source.name}: {str(e)}")
            return articles
    
    async def _scrape_single_article(self, url: str, news_source: NewsSource) -> Optional[NewsContent]:
        """抓取单篇文章"""
        try:
            html = await self.fetch_page(url)
            if not html:
                return None
            
            article = self.extract_article_content(html, url, news_source.selector_config)
            return article
            
        except Exception as e:
            logger.error(f"Error scraping article {url}: {str(e)}")
            return None
    
    async def validate_news_source(self, url: str, selector_config: SelectorConfig) -> Dict[str, Any]:
        """
        验证新闻源配置
        
        Args:
            url: 新闻源URL
            selector_config: 选择器配置
            
        Returns:
            验证结果
        """
        result = {
            "valid": False,
            "title": None,
            "content_sample": None,
            "article_count": 0,
            "error": None
        }
        
        try:
            # 获取主页
            html = await self.fetch_page(url)
            if not html:
                result["error"] = "无法访问URL"
                return result
            
            # 提取链接
            links = self.extract_links(html, url, selector_config)
            result["article_count"] = len(links)
            
            if not links:
                result["error"] = "未找到文章链接"
                return result
            
            # 尝试抓取第一篇文章
            first_article_html = await self.fetch_page(links[0])
            if first_article_html:
                article = self.extract_article_content(first_article_html, links[0], selector_config)
                if article:
                    result["valid"] = True
                    result["title"] = article.title
                    result["content_sample"] = article.content_text[:200] + "..." if len(article.content_text) > 200 else article.content_text
                else:
                    result["error"] = "无法提取文章内容"
            else:
                result["error"] = "无法访问文章页面"
            
            return result
            
        except Exception as e:
            result["error"] = f"验证过程出错: {str(e)}"
            return result
