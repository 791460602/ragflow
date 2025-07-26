# 新闻收集器 API

基于RAGFlow SDK架构的新闻收集器，支持多种外部爬虫工具。

## 架构概述

```
新闻收集器 = 外部爬虫工具 + RAGFlow上传机制
```

### 组件结构

1. **抽象接口** (`api/interfaces/news_crawler_interface.py`)
   - 定义统一的爬虫接口规范
   - 包含数据结构：NewsSource、NewsArticle、CrawlTask等

2. **爬虫实现** (`api/crawlers/news_crawler_implementations.py`)
   - ScrapyNewsCrawler：基于Scrapy的爬虫
   - Newspaper3kCrawler：基于Newspaper3k的爬虫  
   - DemoCrawler：演示爬虫，生成示例数据

3. **SDK端点** (`api/apps/sdk/news_collector.py`)
   - 使用RAGFlow的@token_required认证
   - 提供REST API接口
   - 集成爬虫工厂模式

## API端点

### 1. 服务状态检查
```http
GET /news/ping
Authorization: Bearer <your_token>
```

### 2. 获取支持的爬虫类型
```http
GET /news/crawlers
Authorization: Bearer <your_token>
```

### 3. 创建新闻源
```http
POST /news/sources
Content-Type: application/json
Authorization: Bearer <your_token>

{
  "name": "科技媒体",
  "url": "https://tech.example.com",
  "description": "科技新闻来源",
  "crawler_type": "newspaper"
}
```

### 4. 创建抓取任务
```http
POST /news/tasks
Content-Type: application/json
Authorization: Bearer <your_token>

{
  "task_name": "每日科技新闻",
  "kb_id": "your_knowledge_base_id",
  "crawler_type": "newspaper",
  "max_articles": 10,
  "sources": [
    {
      "name": "科技媒体",
      "url": "https://tech.example.com"
    }
  ]
}
```

### 5. 执行抓取任务
```http
POST /news/tasks/{task_id}/execute
Authorization: Bearer <your_token>
```

### 6. 查询任务状态
```http
GET /news/tasks/{task_id}
Authorization: Bearer <your_token>
```

### 7. 获取任务列表
```http
GET /news/tasks?page=1&page_size=10
Authorization: Bearer <your_token>
```

## 支持的爬虫类型

| 类型 | 描述 | 适用场景 |
|------|------|----------|
| `demo` | 演示爬虫 | 测试和演示 |
| `scrapy` | Scrapy爬虫 | 复杂网站结构爬取 |
| `newspaper` | Newspaper3k | 新闻网站文章提取 |

## 工作流程

1. **选择爬虫类型**：根据目标网站选择合适的爬虫工具
2. **创建新闻源**：配置要爬取的新闻网站
3. **创建抓取任务**：指定知识库和爬取参数
4. **执行任务**：爬虫工具抓取内容并保存为Markdown文件
5. **自动上传**：将爬取结果上传到RAGFlow知识库

## 扩展爬虫

要添加新的爬虫实现：

1. 继承 `INewsCrawler` 接口
2. 实现必需的方法：
   - `validate_source()`
   - `crawl_articles()` 
   - `get_supported_domains()`
3. 在 `CrawlerFactory` 中注册新的爬虫类型

## 文件输出格式

爬取的文章保存为Markdown格式，包含：

- YAML前端元数据（标题、来源、发布时间等）
- Markdown正文内容
- 自动生成的文件名和目录结构

每个任务会创建独立的输出目录，便于管理和上传到RAGFlow知识库。
