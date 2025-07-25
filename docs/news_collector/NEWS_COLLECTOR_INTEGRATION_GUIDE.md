# 新闻收集器API集成指南

## 实现完成

✅ **已完成的功能:**

1. **新闻源管理**
   - 创建、读取、更新、删除新闻源
   - 支持新闻源状态管理

2. **抓取任务管理**
   - 创建抓取任务并关联知识库
   - 任务执行和状态跟踪
   - 支持多新闻源批量抓取

3. **新闻内容管理**
   - 新闻内容列表查询（支持分页和过滤）
   - 单个新闻内容详情查询
   - 新闻内容删除

4. **统计和监控**
   - 系统统计信息
   - 健康检查端点

5. **认证和权限**
   - 集成Flask-Login认证
   - 用户权限控制

## 文件结构

```
api/apps/news_collector_app.py  # 主API文件
NEWS_COLLECTOR_API.md          # API文档
test_news_collector_api.py     # 测试脚本
```

## API端点总览

### 新闻源管理
- `GET /v1/news_collector/sources` - 获取新闻源列表
- `POST /v1/news_collector/sources` - 创建新闻源
- `GET /v1/news_collector/sources/{id}` - 获取单个新闻源
- `PUT /v1/news_collector/sources/{id}` - 更新新闻源
- `DELETE /v1/news_collector/sources/{id}` - 删除新闻源

### 抓取任务管理
- `GET /v1/news_collector/tasks` - 获取任务列表
- `POST /v1/news_collector/tasks` - 创建抓取任务
- `GET /v1/news_collector/tasks/{id}` - 获取单个任务
- `POST /v1/news_collector/tasks/{id}/execute` - 执行任务
- `DELETE /v1/news_collector/tasks/{id}` - 删除任务

### 新闻内容管理
- `GET /v1/news_collector/news` - 获取新闻列表（支持分页）
- `GET /v1/news_collector/news/{id}` - 获取单个新闻
- `DELETE /v1/news_collector/news/{id}` - 删除新闻

### 统计和监控
- `GET /v1/news_collector/statistics` - 获取统计信息
- `GET /v1/news_collector/ping` - 健康检查

## 使用方式

### 1. 启动服务
确保RAGFlow服务正在运行，新闻收集器API会自动注册到路由中。

### 2. 认证
除了`/ping`端点外，所有API都需要用户登录认证。

### 3. 基本使用流程

```python
# 1. 创建新闻源
POST /v1/news_collector/sources
{
  "name": "技术新闻",
  "url": "https://tech-news.com",
  "remark": "每日技术资讯"
}

# 2. 创建抓取任务
POST /v1/news_collector/tasks
{
  "task_name": "每日新闻抓取",
  "kb_id": "your_knowledge_base_id",
  "source_ids": [1],
  "max_articles_per_source": 20
}

# 3. 执行任务
POST /v1/news_collector/tasks/1/execute

# 4. 查看抓取结果
GET /v1/news_collector/news?page=1&page_size=10
```

## 技术特点

### 1. 符合项目架构
- 使用项目标准的Blueprint注册机制
- 遵循现有API的命名和结构规范
- 集成Flask-Login认证系统

### 2. 数据存储
- 当前使用内存存储（适合演示和测试）
- 结构设计便于后续数据库集成

### 3. 错误处理
- 统一的错误响应格式
- 完整的异常捕获和日志记录

### 4. API设计
- RESTful API设计原则
- 支持分页和过滤
- 清晰的响应格式

## 下一步开发建议

### 1. 数据库集成
```python
# 替换内存存储为真实数据库
# 使用项目现有的Peewee ORM
# 创建对应的数据表
```

### 2. 实际抓取逻辑
```python
# 实现真实的网页抓取功能
# 集成新闻内容解析
# 支持多种新闻网站格式
```

### 3. 后台任务
```python
# 集成Celery或类似的后台任务系统
# 支持定时抓取任务
# 任务队列管理
```

### 4. 内容解析
```python
# 集成到RAGFlow的文档解析系统
# 自动添加到知识库
# 支持内容去重
```

## 测试验证

### 1. 健康检查
```bash
curl http://localhost:9380/v1/news_collector/ping
```

### 2. 获取统计信息（需要登录）
```bash
curl http://localhost:9380/v1/news_collector/statistics \
  -H "Authorization: Bearer your_token"
```

## 注意事项

1. **认证要求**: 除ping外的所有端点都需要用户认证
2. **数据持久化**: 当前使用内存存储，重启后数据丢失
3. **生产准备**: 需要实现真实的抓取逻辑和数据库存储
4. **性能考虑**: 大规模使用时需要考虑缓存和异步处理

## 总结

新闻收集器API已经成功集成到RAGFlow项目中，提供了完整的新闻管理功能。实现遵循了项目的设计模式和代码规范，可以无缝集成到现有系统中。接下来只需要根据实际需求添加真实的抓取逻辑和数据库支持即可投入生产使用。
