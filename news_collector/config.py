"""
新闻抓取系统配置文件
"""

import os
from typing import Dict, Any

# 基础配置
NEWS_COLLECTOR_CONFIG = {
    # RAGFlow配置
    "ragflow": {
        "api_key": os.getenv("RAGFLOW_API_KEY", "ragflow-M3NDJjZmEyNjYwZDExZjBhMTAwYjlkOD"),
        "base_url": os.getenv("RAGFLOW_BASE_URL", "http://localhost:9380"),
    },
    
    # 抓取器配置
    "scraper": {
        "timeout": int(os.getenv("SCRAPER_TIMEOUT", 30)),
        "max_concurrent": int(os.getenv("SCRAPER_MAX_CONCURRENT", 10)),
        "user_agent": os.getenv("SCRAPER_USER_AGENT", 
                               "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"),
    },
    
    # 任务配置
    "task": {
        "max_articles_per_source": int(os.getenv("MAX_ARTICLES_PER_SOURCE", 100)),
        "default_auto_parse": os.getenv("DEFAULT_AUTO_PARSE", "true").lower() == "true",
        "retry_count": int(os.getenv("TASK_RETRY_COUNT", 3)),
        "retry_delay": int(os.getenv("TASK_RETRY_DELAY", 60)),  # 秒
    },
    
    # 数据库配置（如果需要）
    "database": {
        "url": os.getenv("DATABASE_URL", "sqlite:///news_collector.db"),
        "echo": os.getenv("DATABASE_ECHO", "false").lower() == "true",
    },
    
    # 日志配置
    "logging": {
        "level": os.getenv("LOG_LEVEL", "INFO"),
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        "file": os.getenv("LOG_FILE", "logs/news_collector.log"),
    },
    
    # API配置
    "api": {
        "host": os.getenv("API_HOST", "0.0.0.0"),
        "port": int(os.getenv("API_PORT", 5000)),
        "debug": os.getenv("API_DEBUG", "false").lower() == "true",
    },
    
    # 安全配置
    "security": {
        "secret_key": os.getenv("SECRET_KEY", "your-secret-key-here"),
        "jwt_expire_hours": int(os.getenv("JWT_EXPIRE_HOURS", 24)),
    }
}


def get_config(key: str = None) -> Any:
    """
    获取配置项
    
    Args:
        key: 配置键，支持点号分隔的嵌套键，如 "ragflow.api_key"
        
    Returns:
        配置值，如果key为None则返回完整配置
    """
    if key is None:
        return NEWS_COLLECTOR_CONFIG
    
    keys = key.split('.')
    value = NEWS_COLLECTOR_CONFIG
    
    for k in keys:
        if isinstance(value, dict) and k in value:
            value = value[k]
        else:
            return None
    
    return value


def update_config(key: str, value: Any) -> None:
    """
    更新配置项
    
    Args:
        key: 配置键，支持点号分隔的嵌套键
        value: 新的配置值
    """
    keys = key.split('.')
    config = NEWS_COLLECTOR_CONFIG
    
    # 导航到目标位置
    for k in keys[:-1]:
        if k not in config:
            config[k] = {}
        config = config[k]
    
    # 设置值
    config[keys[-1]] = value


# 默认选择器配置
DEFAULT_SELECTOR_CONFIGS = {
    "sina.com.cn": {
        "title_selector": "h1",
        "content_selector": ".article-content, .content",
        "time_selector": ".time-source .time, .date",
        "author_selector": ".author",
        "link_selector": "a[href*='/news/']"
    },
    "163.com": {
        "title_selector": "h1",
        "content_selector": ".post-body, .content",
        "time_selector": ".post-info .time, .date",
        "author_selector": ".source",
        "link_selector": "a[href*='/news/']"
    },
    "sohu.com": {
        "title_selector": "h1",
        "content_selector": ".article-text, .content",
        "time_selector": ".time, .date",
        "author_selector": ".media-name",
        "link_selector": "a[href*='/news/']"
    },
    "xinhuanet.com": {
        "title_selector": "h1",
        "content_selector": ".article-content, #detail",
        "time_selector": ".time, .date",
        "author_selector": ".author",
        "link_selector": "a[href*='/news/']"
    },
    "people.com.cn": {
        "title_selector": "h1",
        "content_selector": ".article-content, .text_c",
        "time_selector": ".time, .date",
        "author_selector": ".author",
        "link_selector": "a[href*='/news/']"
    }
}


def get_selector_config_for_domain(domain: str) -> Dict[str, str]:
    """
    根据域名获取预设的选择器配置
    
    Args:
        domain: 域名
        
    Returns:
        选择器配置字典
    """
    # 查找匹配的域名配置
    for preset_domain, config in DEFAULT_SELECTOR_CONFIGS.items():
        if preset_domain in domain:
            return config.copy()
    
    # 返回默认配置
    return {
        "title_selector": "h1",
        "content_selector": ".content, .article-content, .post-content",
        "time_selector": ".time, .date, .publish-time",
        "author_selector": ".author, .writer",
        "link_selector": "a"
    }
