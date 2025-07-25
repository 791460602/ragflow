# 新闻收集器完整实现指南

## 🚀 实现概览

现在新闻收集器已经完全集成到RAGFlow项目中，包含了完整的数据库支持和实际的新闻抓取功能。

## 📁 文件结构

```
api/
├── apps/
│   └── news_collector_app.py          # 新闻收集器API接口
├── db/
│   ├── db_models.py                    # 数据库模型（已添加新闻模型）
│   └── services/
│       └── news_service.py            # 新闻收集器服务层
└── utils/
    └── news_fetcher.py                 # 新闻抓取核心模块

init_news_tables.py                    # 数据库初始化脚本
NEWS_COLLECTOR_API.md                  # API文档
NEWS_COLLECTOR_INTEGRATION_GUIDE.md   # 集成指南
```

## 🗄️ 数据库模型

已添加到 `api/db/db_models.py` 中的三个核心模型：

### NewsSource (新闻源)
```python
- id: 主键
- name: 新闻源名称
- url: 新闻源URL
- status: 状态 (active/inactive)
- fetch_config: 抓取配置
- total_articles: 总文章数
- user_id, tenant_id: 用户和租户关联
```

### NewsTask (抓取任务)
```python
- id: 主键
- task_name: 任务名称
- kb_id: 关联知识库ID
- source_ids: 新闻源ID列表
- status: 任务状态 (pending/running/completed/failed)
- statistics: 执行统计信息
- user_id, tenant_id: 用户和租户关联
```

### NewsContent (新闻内容)
```python
- id: 主键
- title: 新闻标题
- content: 新闻正文
- url: 原文URL
- parse_status: 解析状态
- content_hash: 内容哈希（去重）
- user_id, tenant_id: 用户和租户关联
```

## 🔧 服务层架构

### NewsSourceService
- `create_source()` - 创建新闻源
- `get_by_user()` - 获取用户新闻源
- `update_source()` - 更新新闻源
- `delete_source()` - 删除新闻源

### NewsTaskService
- `create_task()` - 创建抓取任务
- `get_by_user()` - 获取用户任务
- `update_task_status()` - 更新任务状态
- `get_runnable_tasks()` - 获取可执行任务

### NewsContentService
- `create_content()` - 创建新闻内容
- `get_by_user()` - 获取用户新闻（支持分页）
- `update_parse_status()` - 更新解析状态
- `get_statistics()` - 获取统计信息

## 🌐 API端点

### 认证
所有API（除ping外）都需要用户登录认证，自动获取用户和租户信息。

### 新闻源管理
```
GET    /v1/news_collector/sources           # 获取新闻源列表
POST   /v1/news_collector/sources           # 创建新闻源
GET    /v1/news_collector/sources/{id}      # 获取单个新闻源
PUT    /v1/news_collector/sources/{id}      # 更新新闻源
DELETE /v1/news_collector/sources/{id}      # 删除新闻源
```

### 抓取任务管理
```
GET    /v1/news_collector/tasks             # 获取任务列表
POST   /v1/news_collector/tasks             # 创建抓取任务
GET    /v1/news_collector/tasks/{id}        # 获取单个任务
POST   /v1/news_collector/tasks/{id}/execute # 执行任务
DELETE /v1/news_collector/tasks/{id}        # 删除任务
```

### 新闻内容管理
```
GET    /v1/news_collector/news              # 获取新闻列表（分页）
GET    /v1/news_collector/news/{id}         # 获取单个新闻
DELETE /v1/news_collector/news/{id}         # 删除新闻
```

### 监控统计
```
GET    /v1/news_collector/statistics        # 获取统计信息
GET    /v1/news_collector/ping              # 健康检查
```

## 📦 新闻抓取功能

### NewsFetcher 类
实现了实际的网页抓取功能：
- 支持自定义请求头和超时
- 智能HTML解析（支持BeautifulSoup或正则表达式）
- 多种文章选择器策略
- 完整文章内容抓取

### NewsTaskExecutor 类
任务执行器：
- 批量新闻源处理
- 错误处理和统计
- 请求频率控制
- 内容去重机制

## 🚀 部署和使用

### 1. 数据库初始化
```bash
# 运行数据库初始化脚本
python init_news_tables.py
```

### 2. 启动RAGFlow服务
确保RAGFlow主服务正在运行，新闻收集器API会自动注册。

### 3. 基本使用流程

#### 创建新闻源
```bash
curl -X POST http://localhost:9380/v1/news_collector/sources \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_token" \
  -d '{
    "name": "科技新闻",
    "url": "https://example-tech-news.com",
    "remark": "每日科技资讯",
    "fetch_config": {
      "timeout": 30,
      "encoding": "utf-8"
    }
  }'
```

#### 创建抓取任务
```bash
curl -X POST http://localhost:9380/v1/news_collector/tasks \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_token" \
  -d '{
    "task_name": "每日科技新闻抓取",
    "kb_id": "your_knowledge_base_id",
    "source_ids": ["source_id_1", "source_id_2"],
    "auto_parse": true,
    "max_articles_per_source": 20
  }'
```

#### 执行任务
```bash
curl -X POST http://localhost:9380/v1/news_collector/tasks/task_id/execute \
  -H "Authorization: Bearer your_token"
```

#### 查看抓取结果
```bash
curl "http://localhost:9380/v1/news_collector/news?page=1&page_size=10" \
  -H "Authorization: Bearer your_token"
```

## 🔧 技术特性

### 1. 数据库设计
- 完全符合RAGFlow的数据库架构
- 支持多租户和用户隔离
- 包含创建时间、更新时间等标准字段
- 合理的索引设计提高查询性能

### 2. 服务层设计
- 继承CommonService基类
- 使用数据库连接上下文管理
- 完整的错误处理和日志记录
- 支持事务操作

### 3. API设计
- 遵循RESTful设计原则
- 统一的错误响应格式
- 完整的权限验证
- 支持分页和过滤

### 4. 抓取引擎
- 支持多种网站结构
- 智能内容提取
- 防重复机制
- 可配置的抓取策略

## 🔄 扩展开发

### 1. 添加新的新闻源类型
在 `news_fetcher.py` 中扩展 `NewsFetcher` 类：
```python
def _parse_special_site(self, html_content):
    # 针对特定网站的解析逻辑
    pass
```

### 2. 集成到知识库
在任务执行成功后，将新闻内容自动添加到RAGFlow知识库：
```python
from api.db.services.document_service import DocumentService

# 创建文档并解析
doc = DocumentService.insert({
    "name": article["title"],
    "type": "text",
    "kb_id": task.kb_id,
    # ... 其他字段
})
```

### 3. 定时任务支持
集成Celery或其他任务队列：
```python
from celery import Celery

@celery.task
def execute_news_task(task_id):
    # 执行新闻抓取任务
    pass
```

### 4. 实时监控
添加WebSocket支持实时任务状态推送：
```python
from flask_socketio import emit

def notify_task_progress(task_id, progress):
    emit('task_progress', {'task_id': task_id, 'progress': progress})
```

## 📊 监控和统计

### 系统监控
- 新闻源状态监控
- 任务执行状态追踪
- 抓取成功率统计
- 内容质量分析

### 性能指标
- 抓取速度和效率
- 数据库查询性能
- API响应时间
- 错误率统计

## 🛡️ 安全和限制

### 1. 访问控制
- 基于用户和租户的权限隔离
- API访问频率限制
- 敏感操作审计日志

### 2. 数据安全
- 内容哈希去重防止重复
- SQL注入防护
- XSS攻击防护

### 3. 系统限制
- 单次抓取文章数量限制
- 请求频率控制
- 超时和重试机制

## 📝 总结

新闻收集器现在已经完全集成到RAGFlow中，提供了：

✅ **完整的数据库支持** - 三个核心数据表，完整的服务层
✅ **标准的API接口** - 符合项目规范的RESTful API
✅ **实际的抓取功能** - 真实的网页内容抓取和解析
✅ **用户权限管理** - 多租户支持和访问控制
✅ **监控和统计** - 完整的运行状态监控
✅ **扩展性设计** - 易于添加新功能和集成

接下来只需要：
1. 运行数据库初始化脚本
2. 根据实际需求配置新闻源
3. 创建和执行抓取任务
4. 根据需要扩展特定功能

这个实现完全符合您的要求，使用了项目原有的数据库操作模式，并提供了实际可用的新闻抓取功能！
