# 新闻调度器使用指南

## 概述

新闻调度器是RAGFlow的一个强大功能，能够自动从指定网站抓取新闻，处理内容并生成每日简报。该功能支持多新闻源、关键词过滤、内容解析、附件下载和知识库存储。

## 主要功能

### 1. 新闻抓取 (NewsCrawler)
- **多源支持**: 支持RSS、HTML页面等多种新闻源
- **智能过滤**: 基于关键词和日期进行内容过滤
- **并发处理**: 支持多线程并发抓取，提高效率
- **错误处理**: 完善的错误处理和重试机制

### 2. 新闻处理 (NewsProcessor)
- **内容解析**: 自动提取新闻标题、摘要、详细内容
- **附件处理**: 自动发现和下载PDF、Word、PowerPoint等附件
- **知识库存储**: 将新闻和附件存储到指定知识库
- **结构化输出**: 支持Markdown、JSON、纯文本等多种格式

### 3. 简报生成 (DailyReportGenerator)
- **智能分析**: 基于知识库内容生成结构化简报
- **多模板支持**: 支持多种报告模板和语言
- **附件摘要**: 自动生成附件内容摘要
- **趋势分析**: 分析热门话题和行业趋势

### 4. 调度服务 (NewsSchedulerService)
- **定时执行**: 支持Cron表达式和间隔调度
- **多租户**: 支持多租户独立配置
- **状态监控**: 实时监控任务执行状态
- **通知机制**: 支持邮件和Webhook通知

## 配置说明

### 基础配置

```json
{
  "scheduler_config": {
    "enabled": true,
    "timezone": "Asia/Shanghai",
    "max_concurrent_jobs": 5,
    "job_timeout": 3600
  }
}
```

### 新闻源配置

```json
{
  "news_sources": [
    {
      "name": "新浪新闻",
      "url": "https://news.sina.com.cn/",
      "type": "rss",
      "rss_url": "https://feed.mix.sina.com.cn/api/roll/get?pageid=153&lid=2509&k=&num=50&page=1&r=",
      "keywords": ["科技", "AI", "人工智能"],
      "exclude_keywords": ["广告", "推广"],
      "max_news_count": 20,
      "enabled": true
    }
  ]
}
```

### 新闻处理配置

```json
{
  "news_processor": {
    "kb_id": "your_knowledge_base_id",
    "process_content": true,
    "max_content_length": 5000,
    "save_to_kb": true,
    "format_output": "markdown",
    "download_attachments": true,
    "attachment_types": ["pdf", "doc", "docx", "ppt", "pptx", "xls", "xlsx"],
    "max_attachment_size": 52428800,
    "attachment_timeout": 60
  }
}
```

### 简报生成配置

```json
{
  "report_generator": {
    "template": "daily_brief",
    "language": "zh-CN",
    "include_attachments": true,
    "attachment_summary": true,
    "max_attachment_summary_length": 500,
    "output_format": "markdown",
    "sections": ["summary", "key_events", "industry_trends", "attachments"]
  }
}
```

## 附件处理功能

### 功能特性

1. **自动发现**: 自动扫描新闻页面中的附件链接
2. **类型识别**: 支持PDF、Word、PowerPoint、Excel等常见格式
3. **智能过滤**: 基于文件扩展名、链接文本和URL关键词识别附件
4. **大小控制**: 可配置最大附件大小限制（默认50MB）
5. **超时控制**: 可配置下载超时时间（默认60秒）
6. **去重处理**: 自动去除重复的附件链接

### 支持的附件类型

- **PDF文档**: `.pdf`
- **Word文档**: `.doc`, `.docx`
- **PowerPoint演示**: `.ppt`, `.pptx`
- **Excel表格**: `.xls`, `.xlsx`

### 附件识别规则

1. **文件扩展名**: 检查URL路径中的文件扩展名
2. **链接文本**: 检查链接文本中的关键词（如"PDF"、"附件"、"下载"）
3. **URL关键词**: 检查URL中的关键词（如"pdf"、"attachment"、"download"）

### 配置参数

```json
{
  "download_attachments": true,           // 是否下载附件
  "attachment_types": [                   // 支持的附件类型
    "pdf", "doc", "docx", "ppt", "pptx", "xls", "xlsx"
  ],
  "max_attachment_size": 52428800,        // 最大附件大小（字节）
  "attachment_timeout": 60                // 下载超时时间（秒）
}
```

### 附件存储

1. **文件存储**: 附件以二进制形式存储到知识库存储系统
2. **元数据记录**: 在数据库中记录附件的元数据信息
3. **类型映射**: 根据文件类型自动选择对应的解析器
4. **命名规则**: 使用"新闻标题_文件名"的格式避免冲突

## 调度配置

### Cron表达式

```json
{
  "schedule": {
    "crawl_schedule": "0 8,12,18 * * *",    // 每天8点、12点、18点抓取
    "report_schedule": "0 9 * * *",         // 每天9点生成简报
    "cleanup_schedule": "0 2 * * 0"         // 每周日凌晨2点清理
  }
}
```

### 常用Cron表达式

| 表达式 | 说明 |
|--------|------|
| `0 8 * * *` | 每天上午8点 |
| `0 8,12,18 * * *` | 每天8点、12点、18点 |
| `0 9 * * 1-5` | 工作日9点 |
| `0 2 * * 0` | 每周日凌晨2点 |
| `*/30 * * * *` | 每30分钟 |
| `0 */2 * * *` | 每2小时 |

## API接口

### 1. 获取配置

```bash
GET /api/v1/news-scheduler/config
```

### 2. 更新配置

```bash
PUT /api/v1/news-scheduler/config
Content-Type: application/json

{
  "scheduler_config": { ... },
  "news_sources": [ ... ],
  "news_processor": { ... },
  "report_generator": { ... }
}
```

### 3. 启动服务

```bash
POST /api/v1/news-scheduler/start
```

### 4. 停止服务

```bash
POST /api/v1/news-scheduler/stop
```

### 5. 测试抓取

```bash
POST /api/v1/news-scheduler/test-crawl
Content-Type: application/json

{
  "source_name": "新浪新闻"
}
```

### 6. 生成简报

```bash
POST /api/v1/news-scheduler/generate-report
Content-Type: application/json

{
  "template": "daily_brief",
  "language": "zh-CN"
}
```

### 7. 获取任务状态

```bash
GET /api/v1/news-scheduler/status
```

## 使用示例

### 1. 基础设置

```python
from api.services.news_scheduler_service import NewsSchedulerService

# 创建调度服务
scheduler = NewsSchedulerService()

# 加载配置
config = {
    "scheduler_config": {
        "enabled": True,
        "timezone": "Asia/Shanghai"
    },
    "news_sources": [
        {
            "name": "科技新闻",
            "url": "https://tech.news.com/",
            "type": "rss",
            "rss_url": "https://tech.news.com/rss",
            "keywords": ["AI", "科技"],
            "max_news_count": 10
        }
    ],
    "news_processor": {
        "kb_id": "your_kb_id",
        "download_attachments": True,
        "max_attachment_size": 50 * 1024 * 1024
    }
}

# 启动服务
scheduler.start(config)
```

### 2. 自定义附件处理

```python
# 配置附件处理参数
processor_config = {
    "download_attachments": True,
    "attachment_types": ["pdf", "doc", "docx"],
    "max_attachment_size": 100 * 1024 * 1024,  # 100MB
    "attachment_timeout": 120  # 2分钟超时
}

# 启动带附件处理的新闻抓取
scheduler.start_news_crawl(processor_config)
```

### 3. 生成包含附件的简报

```python
# 配置简报生成
report_config = {
    "include_attachments": True,
    "attachment_summary": True,
    "max_attachment_summary_length": 1000,
    "sections": ["summary", "key_events", "attachments"]
}

# 生成简报
report = scheduler.generate_daily_report(report_config)
```

## 最佳实践

### 1. 新闻源配置

- **选择可靠源**: 选择更新频率高、内容质量好的新闻源
- **关键词优化**: 使用精确的关键词提高内容相关性
- **排除词设置**: 设置排除词过滤无关内容
- **数量控制**: 合理设置每个源的新闻数量限制

### 2. 附件处理

- **大小限制**: 根据存储容量设置合理的附件大小限制
- **类型过滤**: 只下载需要的文件类型
- **超时设置**: 根据网络情况设置合适的超时时间
- **错误处理**: 监控附件下载失败的情况

### 3. 调度优化

- **错峰执行**: 避免在高峰时段执行大量任务
- **资源控制**: 合理设置并发数量避免系统过载
- **监控告警**: 设置任务执行状态监控和告警
- **备份策略**: 定期备份配置和重要数据

### 4. 知识库管理

- **定期清理**: 设置自动清理过期数据
- **存储监控**: 监控知识库存储使用情况
- **内容质量**: 定期检查存储内容的质量和相关性
- **索引优化**: 确保知识库索引性能良好

## 故障排除

### 常见问题

1. **抓取失败**
   - 检查网络连接
   - 验证新闻源URL是否有效
   - 检查关键词配置是否正确

2. **附件下载失败**
   - 检查附件URL是否可访问
   - 验证文件大小是否超限
   - 检查网络超时设置

3. **知识库存储失败**
   - 验证知识库ID是否正确
   - 检查存储空间是否充足
   - 确认用户权限是否足够

4. **调度任务不执行**
   - 检查Cron表达式格式
   - 验证时区设置
   - 确认服务是否正常启动

### 日志查看

```bash
# 查看调度服务日志
tail -f logs/news_scheduler.log

# 查看抓取任务日志
tail -f logs/news_crawler.log

# 查看处理任务日志
tail -f logs/news_processor.log
```

### 性能优化

1. **并发控制**: 根据系统性能调整并发数量
2. **缓存策略**: 对重复内容使用缓存
3. **资源监控**: 监控CPU、内存、网络使用情况
4. **数据库优化**: 定期清理历史数据

## 扩展开发

### 自定义新闻源

```python
class CustomNewsSource:
    def __init__(self, config):
        self.config = config
    
    def fetch_news(self):
        # 实现自定义抓取逻辑
        pass
```

### 自定义附件处理器

```python
class CustomAttachmentProcessor:
    def __init__(self, config):
        self.config = config
    
    def process_attachment(self, attachment):
        # 实现自定义处理逻辑
        pass
```

### 自定义报告模板

```python
class CustomReportTemplate:
    def __init__(self, config):
        self.config = config
    
    def generate_report(self, data):
        # 实现自定义报告生成逻辑
        pass
```

## 更新日志

### v1.1.0 (最新)
- 新增附件处理功能
- 支持PDF、Word、PowerPoint、Excel等格式
- 添加附件摘要生成
- 优化简报生成模板
- 增强错误处理和日志记录

### v1.0.0
- 基础新闻抓取功能
- 多源支持
- 知识库存储
- 基础简报生成
- 调度服务

## 技术支持

如有问题，请通过以下方式获取支持：

1. **文档**: 查看完整的技术文档
2. **社区**: 参与社区讨论
3. **Issues**: 提交GitHub Issues
4. **邮件**: 发送邮件到技术支持邮箱 