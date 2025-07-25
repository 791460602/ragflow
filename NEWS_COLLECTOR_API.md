# 新闻收集器API文档

## 概述

新闻收集器API提供了完整的新闻源管理、抓取任务创建和新闻内容管理功能。

## API端点

### 基础URL
```
http://localhost:9380/v1/news_collector
```

### 认证
所有API（除ping外）都需要用户登录认证。需要在请求头中包含有效的session或access_token。

## 新闻源管理

### 1. 获取新闻源列表
```
GET /sources
```

**响应示例:**
```json
{
  "code": 0,
  "data": [
    {
      "id": 1,
      "name": "示例新闻网站",
      "url": "https://example.com/news",
      "remark": "测试新闻源",
      "status": "active",
      "created_at": "2024-01-01T10:00:00",
      "updated_at": "2024-01-01T10:00:00",
      "user_id": "user123"
    }
  ]
}
```

### 2. 创建新闻源
```
POST /sources
```

**请求体:**
```json
{
  "name": "新闻网站名称",
  "url": "https://example.com/news",
  "remark": "备注信息（可选）"
}
```

### 3. 获取单个新闻源
```
GET /sources/{source_id}
```

### 4. 更新新闻源
```
PUT /sources/{source_id}
```

**请求体:**
```json
{
  "name": "更新后的名称",
  "url": "https://updated-url.com",
  "remark": "更新后的备注",
  "status": "active"
}
```

### 5. 删除新闻源
```
DELETE /sources/{source_id}
```

## 抓取任务管理

### 1. 获取任务列表
```
GET /tasks
```

### 2. 创建抓取任务
```
POST /tasks
```

**请求体:**
```json
{
  "task_name": "任务名称",
  "kb_id": "knowledge_base_id",
  "source_ids": [1, 2, 3],
  "auto_parse": true,
  "max_articles_per_source": 10
}
```

### 3. 获取单个任务
```
GET /tasks/{task_id}
```

### 4. 执行任务
```
POST /tasks/{task_id}/execute
```

### 5. 删除任务
```
DELETE /tasks/{task_id}
```

## 新闻内容管理

### 1. 获取新闻列表
```
GET /news?page=1&page_size=10&source_id=1
```

**查询参数:**
- `page`: 页码（默认1）
- `page_size`: 每页数量（默认10）
- `source_id`: 过滤指定新闻源（可选）

### 2. 获取单个新闻内容
```
GET /news/{content_id}
```

### 3. 删除新闻内容
```
DELETE /news/{content_id}
```

## 统计信息

### 获取统计信息
```
GET /statistics
```

**响应示例:**
```json
{
  "code": 0,
  "data": {
    "total_sources": 5,
    "active_sources": 4,
    "total_tasks": 10,
    "total_news": 100,
    "completed_tasks": 8,
    "running_tasks": 1
  }
}
```

## 健康检查

### 服务健康检查
```
GET /ping
```

**响应示例:**
```json
{
  "code": 0,
  "data": {
    "message": "news_collector service is running"
  }
}
```

## 错误处理

API使用标准的HTTP状态码和统一的错误响应格式：

```json
{
  "code": 1,
  "message": "错误描述信息"
}
```

## 使用示例

### 创建完整的新闻抓取流程

1. **创建新闻源:**
```bash
curl -X POST http://localhost:9380/v1/news_collector/sources \
  -H "Content-Type: application/json" \
  -d '{"name": "技术新闻", "url": "https://tech-news.com"}'
```

2. **创建抓取任务:**
```bash
curl -X POST http://localhost:9380/v1/news_collector/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "task_name": "每日技术新闻抓取",
    "kb_id": "your_knowledge_base_id",
    "source_ids": [1],
    "max_articles_per_source": 20
  }'
```

3. **执行任务:**
```bash
curl -X POST http://localhost:9380/v1/news_collector/tasks/1/execute
```

4. **查看抓取结果:**
```bash
curl http://localhost:9380/v1/news_collector/news?page=1&page_size=10
```

## 注意事项

1. 所有时间字段使用ISO 8601格式
2. 当前版本使用内存存储，重启服务后数据会丢失
3. 生产环境需要集成真实的数据库存储
4. 需要实现实际的新闻抓取逻辑
5. 建议添加更多的数据验证和错误处理
