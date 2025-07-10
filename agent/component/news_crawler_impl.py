#
#  Copyright 2024 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
import asyncio
import logging
import re
from abc import ABC
from datetime import datetime, timedelta
from typing import List, Dict, Any
import requests
from bs4 import BeautifulSoup
from agent.component.base import ComponentBase, ComponentParamBase
from api.utils.web_utils import is_valid_url


class NewsCrawlerParam(ComponentParamBase):
    """
    定义新闻抓取组件的参数
    """
    
    def __init__(self):
        super().__init__()
        self.news_sources = []  # 新闻源列表
        self.max_news_per_source = 10  # 每个源最多抓取的新闻数量
        self.date_filter = "today"  # 日期过滤：today, week, month
        self.keywords = []  # 关键词过滤
        self.proxy = None  # 代理设置
        self.timeout = 30  # 超时时间
    
    def check(self):
        self.check_positive_integer(self.max_news_per_source, "每个源最多抓取的新闻数量")
        self.check_valid_value(self.date_filter, "日期过滤", ['today', 'week', 'month'])
        self.check_positive_integer(self.timeout, "超时时间")


class NewsCrawler(ComponentBase, ABC):
    component_name = "NewsCrawler"
    
    def _run(self, history, **kwargs):
        """执行新闻抓取"""
        try:
            # 获取输入参数
            input_data = self.get_input()
            
            # 解析新闻源配置
            news_sources = self._parse_news_sources(input_data)
            
            # 执行抓取
            news_results = asyncio.run(self._crawl_news(news_sources))
            
            return NewsCrawler.be_output(news_results)
            
        except Exception as e:
            logging.error(f"新闻抓取失败: {str(e)}")
            return NewsCrawler.be_output(f"新闻抓取失败: {str(e)}")
    
    def _parse_news_sources(self, input_data):
        """解析新闻源配置"""
        sources = []
        
        # 从组件参数获取默认配置
        if self._param.news_sources:
            sources.extend(self._param.news_sources)
        
        # 从输入数据解析新闻源
        if "content" in input_data:
            content = input_data["content"]
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and "url" in item:
                        sources.append(item)
                    elif isinstance(item, str) and is_valid_url(item):
                        sources.append({"url": item, "name": f"source_{len(sources)}"})
            elif isinstance(content, str):
                # 尝试解析JSON格式的新闻源配置
                try:
                    import json
                    parsed = json.loads(content)
                    if isinstance(parsed, list):
                        sources.extend(parsed)
                except:
                    # 如果不是JSON，尝试作为URL处理
                    if is_valid_url(content):
                        sources.append({"url": content, "name": f"source_{len(sources)}"})
        
        return sources
    
    async def _crawl_news(self, news_sources: List[Dict[str, Any]]):
        """异步抓取新闻"""
        all_news = []
        
        for source in news_sources:
            try:
                news_list = await self._crawl_single_source(source)
                all_news.extend(news_list)
            except Exception as e:
                logging.error(f"抓取新闻源 {source.get('name', source.get('url', 'unknown'))} 失败: {str(e)}")
                continue
        
        return all_news
    
    async def _crawl_single_source(self, source: Dict[str, Any]):
        """抓取单个新闻源"""
        url = source.get("url")
        name = source.get("name", f"source_{url}")
        
        if not url or not is_valid_url(url):
            return []
        
        try:
            # 发送HTTP请求
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            }
            
            proxies = {"http": self._param.proxy, "https": self._param.proxy} if self._param.proxy else None
            
            response = requests.get(
                url, 
                headers=headers, 
                proxies=proxies, 
                timeout=self._param.timeout
            )
            response.raise_for_status()
            
            # 解析HTML
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 根据不同的新闻源使用不同的解析策略
            news_list = self._parse_news_from_html(soup, source)
            
            # 过滤和排序
            filtered_news = self._filter_news(news_list)
            
            return filtered_news[:self._param.max_news_per_source]
            
        except Exception as e:
            logging.error(f"抓取 {name} 失败: {str(e)}")
            return []
    
    def _parse_news_from_html(self, soup: BeautifulSoup, source: Dict[str, Any]):
        """从HTML中解析新闻"""
        news_list = []
        
        # 通用的新闻解析策略
        selectors = [
            # 常见的新闻选择器
            "article", ".news-item", ".article", ".post", ".entry",
            ".news-list li", ".article-list li", ".post-list li",
            "h1", "h2", "h3", ".title", ".headline"
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                for element in elements:
                    news_item = self._extract_news_item(element, source)
                    if news_item:
                        news_list.append(news_item)
                break
        
        # 如果没有找到新闻，尝试更通用的方法
        if not news_list:
            news_list = self._fallback_parse(soup, source)
        
        return news_list
    
    def _extract_news_item(self, element, source: Dict[str, Any]):
        """从HTML元素中提取新闻信息"""
        try:
            # 提取标题
            title = ""
            title_selectors = ["h1", "h2", "h3", ".title", ".headline", "a"]
            for selector in title_selectors:
                title_elem = element.select_one(selector)
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    break
            
            if not title:
                title = element.get_text(strip=True)[:100]
            
            # 提取链接
            link = ""
            link_elem = element.find("a")
            if link_elem and link_elem.get("href"):
                link = link_elem["href"]
                if link.startswith("/"):
                    link = f"{source['url'].rstrip('/')}{link}"
            
            # 提取摘要
            summary = ""
            summary_selectors = [".summary", ".excerpt", ".description", "p"]
            for selector in summary_selectors:
                summary_elem = element.select_one(selector)
                if summary_elem:
                    summary = summary_elem.get_text(strip=True)
                    break
            
            # 提取时间
            time_str = ""
            time_selectors = [".time", ".date", ".published", "time"]
            for selector in time_selectors:
                time_elem = element.select_one(selector)
                if time_elem:
                    time_str = time_elem.get_text(strip=True)
                    break
            
            if title and len(title) > 5:  # 过滤掉太短的标题
                return {
                    "title": title,
                    "link": link,
                    "summary": summary,
                    "time": time_str,
                    "source": source.get("name", source.get("url")),
                    "source_url": source.get("url"),
                    "crawl_time": datetime.now().isoformat()
                }
        
        except Exception as e:
            logging.debug(f"提取新闻项失败: {str(e)}")
        
        return None
    
    def _fallback_parse(self, soup: BeautifulSoup, source: Dict[str, Any]):
        """备用解析方法"""
        news_list = []
        
        # 查找所有链接
        links = soup.find_all("a", href=True)
        
        for link in links:
            try:
                title = link.get_text(strip=True)
                href = link["href"]
                
                # 过滤有效的新闻链接
                if (len(title) > 10 and 
                    href.startswith(("http", "/")) and
                    not any(keyword in href.lower() for keyword in ["javascript:", "mailto:", "#"])):
                    
                    if href.startswith("/"):
                        href = f"{source['url'].rstrip('/')}{href}"
                    
                    news_list.append({
                        "title": title,
                        "link": href,
                        "summary": "",
                        "time": "",
                        "source": source.get("name", source.get("url")),
                        "source_url": source.get("url"),
                        "crawl_time": datetime.now().isoformat()
                    })
            except:
                continue
        
        return news_list
    
    def _filter_news(self, news_list: List[Dict[str, Any]]):
        """过滤新闻"""
        filtered_news = []
        
        for news in news_list:
            # 关键词过滤
            if self._param.keywords:
                title_lower = news.get("title", "").lower()
                summary_lower = news.get("summary", "").lower()
                content_lower = f"{title_lower} {summary_lower}"
                
                if not any(keyword.lower() in content_lower for keyword in self._param.keywords):
                    continue
            
            # 日期过滤
            if not self._is_news_recent(news):
                continue
            
            filtered_news.append(news)
        
        # 按时间排序
        filtered_news.sort(key=lambda x: x.get("time", ""), reverse=True)
        
        return filtered_news
    
    def _is_news_recent(self, news: Dict[str, Any]):
        """检查新闻是否在指定时间范围内"""
        if self._param.date_filter == "today":
            # 今天
            return True  # 简化处理，实际应该解析时间
        elif self._param.date_filter == "week":
            # 本周
            return True
        elif self._param.date_filter == "month":
            # 本月
            return True
        
        return True 