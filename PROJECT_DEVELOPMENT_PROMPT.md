# RAGFlow新闻收集器项目开发Prompt

## 项目背景
我正在基于RAGFlow开源项目开发一个新闻收集器功能。RAGFlow是一个基于深度文档理解的RAG（检索增强生成）引擎，使用Python Flask框架、Peewee ORM、MySQL/PostgreSQL数据库。

## 已完成的开发工作

### 1. 数据库层 (100%完成)
**位置**: `api/db/db_models.py`

已实现3个核心数据模型：
```python
class NewsSource(DataBaseModel):
    # 新闻源管理，包含name, url, status, fetch_config等字段
    # 使用RAGFlow标准的DataBaseModel基类
    # 包含tenant_id多租户支持

class NewsTask(DataBaseModel): 
    # 抓取任务管理，包含task_name, kb_id, source_ids, status等
    # 支持crawler_config配置和statistics统计

class NewsContent(DataBaseModel):
    # 新闻内容存储，关联document_id复用RAGFlow文档系统
    # 包含元数据：author, publish_time, category, tags等
```

**关键特点**：
- 遵循RAGFlow的DataBaseModel模式
- 使用CharField、TextField、JSONField、BigIntegerField等标准字段类型
- 自动包含create_time、update_time时间戳
- 已在migrate_db()函数中添加表创建迁移

### 2. 服务层 (100%完成)
**位置**: `api/db/services/news_service.py`

实现了3个服务类：
```python
class NewsSourceService(CommonService):
    # 新闻源CRUD操作，继承RAGFlow CommonService模式
    # 方法：get_by_tenant_id, create_source, update_source, update_statistics

class NewsTaskService(CommonService):
    # 任务管理服务，支持任务状态更新
    # 方法：create_task, update_task, update_task_status, get_pending_tasks

class NewsContentService(CommonService):
    # 内容管理服务，支持统计分析
    # 方法：create_content, get_statistics_by_time_range, check_duplicate
```

**设计原则**：
- 继承CommonService基类，使用@DB.connection_context()装饰器
- 遵循RAGFlow的服务层模式：query/get/save/delete标准方法
- 支持分页、过滤、排序等通用功能
- 完整的错误处理和数据验证

### 3. API层 (100%完成)
**位置**: `api/apps/sdk/news_collector.py`

实现了20个完整API端点：

**新闻源管理** (6个端点):
- `POST /sources` - 创建新闻源
- `GET /sources` - 获取新闻源列表 
- `GET /sources/{id}` - 获取新闻源详情
- `PUT /sources/{id}` - 更新新闻源
- `DELETE /sources/{id}` - 删除新闻源
- `POST /test` - 测试新闻源连接

**任务管理** (7个端点):
- `POST /tasks` - 创建抓取任务
- `GET /tasks` - 获取任务列表
- `GET /tasks/{id}` - 获取任务详情
- `PUT /tasks/{id}` - 更新任务
- `DELETE /tasks/{id}` - 删除任务
- `POST /tasks/{id}/execute` - 执行任务
- `POST /tasks/{id}/stop` - 停止任务

**内容管理与系统** (5个端点):
- `GET /content` - 获取新闻内容列表
- `GET /content/{id}` - 获取新闻内容详情
- `GET /statistics` - 获取统计数据
- `GET /ping` - 服务状态检查
- `GET /crawlers` - 获取支持的爬虫类型

### 4. 架构集成 (100%完成)
完全遵循RAGFlow现有架构模式：

**认证机制**：
- 使用`@token_required`装饰器，自动提取tenant_id
- 支持多租户数据隔离

**数据库集成**：
- 使用RAGFlow的Peewee ORM和连接池
- 遵循DataBaseModel字段定义规范
- 集成现有的迁移系统

**文件存储集成**：
- 可接入STORAGE_IMPL抽象层（minio/本地存储）
- 复用FileService文件上传下载功能

**搜索引擎集成**：
- 可接入DocStoreConnection抽象（ES/OpenSearch/Infinity）
- 支持内容索引和检索

### 5. 爬虫架构 (接口完成，实现待扩展)
**位置**: `api/interfaces/news_crawler_interface.py`, `api/crawlers/news_crawler_implementations.py`

采用两阶段解耦架构：
```
阶段1: 新闻网站 → 外部爬虫工具 → 标准化本地目录
阶段2: 本地目录 → RAGFlow文件夹上传 → 知识库文档
```

**设计模式**：
- 抽象接口：`Newscrawler`基类定义标准方法
- 工厂模式：`CrawlerFactory`管理多种爬虫实现
- 当前支持：DemoCrawler（演示）、Newspaper3kCrawler、ScrapyNewsCrawler

## 开发规范和约定

### 1. 代码结构规范
```
api/
├── db/
│   ├── db_models.py          # 数据模型定义
│   └── services/
│       └── news_service.py   # 业务逻辑服务层
├── apps/sdk/
│   └── news_collector.py     # API端点定义
├── interfaces/
│   └── news_crawler_interface.py  # 爬虫接口
└── crawlers/
    └── news_crawler_implementations.py  # 爬虫实现
```

### 2. 命名约定
- **数据模型**: CamelCase，如`NewsSource`
- **服务类**: `{模型名}Service`，如`NewsSourceService`  
- **API端点**: RESTful风格，如`/sources`, `/tasks/{id}/execute`
- **数据库表**: snake_case，如`news_source`, `news_task`
- **字段名**: snake_case，如`tenant_id`, `create_time`

### 3. RAGFlow集成规范
**数据模型必须**：
- 继承`DataBaseModel`基类
- 包含`tenant_id`字段支持多租户
- 使用标准字段类型：CharField, TextField, JSONField, BigIntegerField
- 定义`__str__`方法和Meta类指定db_table

**服务层必须**：
- 继承`CommonService`基类
- 使用`@DB.connection_context()`装饰器
- 实现`to_dict`方法进行序列化
- 支持分页参数：page, page_size

**API层必须**：
- 使用`@token_required`装饰器进行认证
- 使用`get_json_result`和`server_error_response`统一响应格式
- 通过`manager.route`装饰器定义路由（manager由框架自动注入）
- 遵循RESTful设计原则

### 4. 错误处理规范
```python
try:
    # 业务逻辑
    result = service.method()
    return get_json_result(data=result)
except Exception as e:
    return server_error_response(e)
```

### 5. 数据库操作规范
```python
@classmethod
@DB.connection_context()
def method_name(cls, **kwargs):
    # 数据库操作
    query = cls.model.select().where(...)
    return [cls.to_dict(item) for item in query]
```

## 当前项目状态

### ✅ 已完成 (100%功能覆盖)
- 完整的数据库模型和迁移
- 完整的服务层业务逻辑
- 20个API端点全部实现
- RAGFlow架构完全集成
- 多租户和认证支持
- 爬虫接口框架

### 📋 待扩展功能
- 实际爬虫工具集成（当前只有演示实现）
- 增量抓取和去重机制
- 定时任务调度
- 内容质量评估
- 分布式爬虫支持

### 🛠️ 支持工具
- 数据库迁移脚本：`api/scripts/migrate_news_collector.py`
- 功能测试脚本：`api/scripts/test_news_collector.py`
- 部署指南：`NEWS_COLLECTOR_DEPLOYMENT_GUIDE.md`

## 与大模型对话时的期望

请你基于这个完整的架构和规范，帮我：

1. **扩展功能**：在现有框架基础上添加新功能，必须遵循RAGFlow的架构模式
2. **集成爬虫**：实现具体的爬虫工具，遵循两阶段解耦架构
3. **优化性能**：在保持架构一致性的前提下优化代码
4. **问题排查**：基于现有代码结构分析和解决问题
5. **功能调试**：使用已有的测试工具验证功能

请确保所有建议都遵循已建立的开发规范，保持与RAGFlow核心架构的一致性。
