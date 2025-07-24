"""
新闻抓取与管理模块

这个模块提供新闻抓取、管理和与RAGFlow知识库集成的功能。

主要功能：
- 新闻源管理
- 抓取任务调度
- 内容解析和存储
- 与RAGFlow知识库集成
- 统计报表
"""

__version__ = "1.0.0"
__author__ = "RAGFlow Team"

from .models import NewsSource, NewsTask, NewsContent
from .scraper import NewsScraper
from .manager import NewsManager

__all__ = [
    "NewsSource",
    "NewsTask", 
    "NewsContent",
    "NewsScraper",
    "NewsManager"
]
