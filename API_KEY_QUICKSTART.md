# 新闻收集器API Key认证快速入门

## 概述

新闻收集器已升级为基于API Key认证的两阶段架构：
1. **第一阶段**：使用Python抽象接口的外部爬虫工具抓取新闻
2. **第二阶段**：RAGFlow自动导入标准化目录结构

## 核心优势

### 🔐 API Key认证
- **程序化访问**：无需手动登录，适合自动化流程
- **细粒度权限**：读取、写入、管理权限分离
- **安全可靠**：HMAC签名，长期有效
- **速率限制**：防止滥用，保护服务稳定

### 🐍 Python抽象接口
- **类型安全**：抽象类和类型注解确保接口一致性
- **易于扩展**：标准化接口支持多种爬虫工具
- **代码复用**：通用方法提供默认实现
- **测试友好**：接口清晰，便于单元测试

### 🏗️ 两阶段架构
- **职责分离**：爬虫专注数据采集，RAGFlow专注文档处理
- **标准化输出**：统一的Markdown格式和目录结构
- **工具选择**：可选择最适合的专业爬虫工具
- **维护简单**：减少复杂依赖，提高稳定性

## 快速开始

### 1. 生成API Key

```python
from api.auth.api_key_auth import generate_user_api_key, init_api_key_manager

# 初始化API Key管理器（系统启动时执行一次）
init_api_key_manager("your_secret_key")

# 为用户生成API Key
api_key = generate_user_api_key(
    user_id="your_user_id",
    permissions=["news:read", "news:write"]
)

print(f"Your API Key: {api_key}")
```

### 2. 使用API Key调用接口

```python
import requests

# 设置请求头
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}

# 测试连接
response = requests.get("http://localhost:9222/v1/news_collector/ping", headers=headers)
print(response.json())
```

### 3. 创建新闻源

```python
# 创建新闻源
source_data = {
    "name": "科技新闻源",
    "url": "https://tech.example.com",
    "crawler_config": {
        "type": "scrapy",  # 可选: demo, scrapy, newspaper, selenium
        "max_articles": 10,
        "output_format": "markdown"
    }
}

response = requests.post(
    "http://localhost:9222/v1/news_collector/sources",
    headers=headers,
    json=source_data
)
source_id = response.json()["data"]["id"]
```

### 4. 创建并执行任务

```python
# 创建抓取任务
task_data = {
    "task_name": "日常新闻收集",
    "kb_id": "your_knowledge_base_id",
    "source_ids": [source_id],
    "max_articles_per_source": 5,
    "auto_parse": True
}

response = requests.post(
    "http://localhost:9222/v1/news_collector/tasks",
    headers=headers,
    json=task_data
)
task_id = response.json()["data"]["task_id"]

# 执行任务
response = requests.post(
    f"http://localhost:9222/v1/news_collector/tasks/{task_id}/execute",
    headers=headers
)
print(response.json())
```

### 5. 查询任务状态

```python
# 查询任务状态
response = requests.get(
    f"http://localhost:9222/v1/news_collector/tasks/{task_id}",
    headers=headers
)
task_status = response.json()["data"]
print(f"任务状态: {task_status['status']}")
print(f"处理文章数: {task_status['statistics']['total_articles']}")
```

## 权限说明

### news:read
- 查询任务状态
- 获取执行结果
- 访问服务状态

### news:write
- 创建新闻源
- 创建抓取任务
- 执行任务

### news:admin
- 所有新闻收集器管理权限
- 系统配置管理

## 实现自定义爬虫

### 1. 继承抽象接口

```python
from api.interfaces.news_crawler_interface import INewsCrawler, NewsSource, NewsArticle, CrawlTask, CrawlResult

class MyCustomCrawler(INewsCrawler):
    def validate_source(self, source: NewsSource) -> bool:
        # 验证新闻源是否支持
        return source.url.startswith('https://mysite.com')
    
    def crawl_articles(self, task: CrawlTask) -> CrawlResult:
        # 实现具体的爬虫逻辑
        pass
    
    def get_supported_domains(self) -> List[str]:
        return ["mysite.com"]
```

### 2. 注册爬虫

```python
from api.crawlers.news_crawler_implementations import crawler_registry

# 注册自定义爬虫
my_crawler = MyCustomCrawler()
crawler_registry.register_crawler(my_crawler, ["mysite.com"])
```

## 目录结构规范

爬虫输出应遵循以下目录结构：

```
output_directory/
├── sources/
│   ├── 新闻源1/
│   │   ├── 文章1.md
│   │   ├── 文章2.md
│   │   └── source_info.json
│   └── 新闻源2/
│       ├── 文章1.md
│       └── source_info.json
└── task_summary.json
```

### 文章文件格式（Markdown）

```markdown
---
title: "文章标题"
url: "https://example.com/article"
author: "作者姓名"
publish_time: "2024-07-26T10:00:00"
category: "分类"
tags: ["标签1", "标签2"]
summary: "文章摘要"
crawled_at: "2024-07-26T10:30:00"
---

# 文章标题

文章正文内容...
```

### source_info.json 格式

```json
{
  "name": "新闻源名称",
  "url": "https://example.com",
  "crawled_at": "2024-07-26T10:30:00",
  "articles_count": 5,
  "success_count": 5,
  "failed_count": 0
}
```

## 错误处理

### 常见HTTP状态码

- **401 Unauthorized**: API Key缺失或无效
- **403 Forbidden**: 权限不足
- **404 Not Found**: 资源不存在
- **429 Too Many Requests**: 请求过于频繁
- **500 Internal Server Error**: 服务器内部错误

### 错误响应格式

```json
{
  "success": false,
  "error": "错误描述",
  "error_code": "ERROR_CODE"
}
```

## 最佳实践

### 1. API Key管理
- 安全存储API Key，避免硬编码
- 定期轮换API Key
- 为不同应用使用不同的API Key

### 2. 错误处理
- 实现指数退避重试机制
- 记录详细的错误日志
- 优雅处理网络异常

### 3. 性能优化
- 合理设置请求超时时间
- 控制并发请求数量
- 使用连接池复用连接

### 4. 监控告警
- 监控API调用成功率
- 跟踪任务执行时间
- 设置异常情况告警

## 运行测试

```bash
# 运行API Key认证测试
python news_architecture_test.py

# 运行特定爬虫测试
python -m pytest tests/test_crawlers.py
```

## 下一步计划

1. **实现具体爬虫工具**
   - Scrapy项目模板
   - Newspaper3k集成
   - Selenium动态页面支持

2. **增强功能**
   - 图片下载和处理
   - 视频内容提取
   - 多语言支持

3. **运维工具**
   - 监控面板
   - 日志分析
   - 性能调优

4. **文档完善**
   - API文档
   - 开发指南
   - 故障排查

## 获取帮助

- 查看API文档：`NEWS_COLLECTOR_API.md`
- 架构说明：`ARCHITECTURE_REFACTOR_SUMMARY.md`
- 问题反馈：提交Issue到项目仓库

---

**注意**：本指南基于新的两阶段架构设计，确保在使用前已正确配置相关依赖和环境。
