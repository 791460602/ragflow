# **新闻抓取与管理平台 API 文档 (v1.1)**

**最后更新时间:** 2025-07-24

## **一、 介绍**

### **1.1 目标**
本文档旨在为新闻抓取与管理平台的前后端分离开发提供统一、明确的接口规范。所有开发工作应严格遵循本文档进行。

### **1.2 基础信息**
- **Base URL:** `/api/v1`
- **数据格式:** 所有请求和响应体均为 `application/json` 格式。
- **日期时间格式:** 所有日期时间字段，统一使用 `YYYY-MM-DD HH:mm:ss` 格式。

### **1.3 认证 (Authentication)**
- 除特殊说明外（如登录接口），所有需要认证的接口必须在 HTTP Header 中携带 `Authorization` 字段。
- **格式:** `Authorization: Bearer <TOKEN>`
- `TOKEN` 通过 `POST /api/v1/auth/login` 接口获取。

### **1.4 通用响应结构**
所有接口的响应体都遵循以下统一结构：

```json
{
  "code": 0,          // 业务状态码，0 表示成功
  "message": "success", // 对本次请求结果的文本描述
  "data": {}            // 实际返回的数据内容 (成功时) 或 null (失败时)
}
```

### **1.5 业务状态码与 HTTP 状态码**

| `code` | HTTP Status | 说明 |
| :--- | :--- | :--- |
| `200` | 200 OK | 请求成功 |
| `400`| 400 Bad Request | 请求参数错误 (格式、类型不匹配) |
| `401`| 401 Unauthorized | 未提供 Token 或 Token 无效/过期 |
| `403`| 403 Forbidden | 用户无权访问该资源 |
| `404`| 404 Not Found | 请求的资源不存在 |
| `422`| 422 Unprocessable Entity| 数据验证失败 (业务规则不满足) |
| `500`| 500 Internal Server Error | 服务器内部未知错误 |

**特别说明：对于 `422` 数据验证失败，`data` 字段将包含详细的错误信息：**
```json
{
  "code": 422,
  "message": "数据验证失败",
  "data": {
    "errors": {
      "name": "新闻源名称不能为空",
      "url": "URL 格式不正确"
    }
  }
}
```

---

## **二、 知识库管理 (Knowledge Base)**

### **2.1 获取知识库列表**
- **接口:** `GET /api/v1/news_collector/knowledge_bases`
- **描述:** 获取可用的 RAGFlow 知识库列表。
- **认证:** 是
- **查询参数:**
  - `page` (integer, 可选, 默认 1): 页码。
  - `size` (integer, 可选, 默认 20): 每页数量。
  - `keyword` (string, 可选): 按名称进行模糊搜索。
- **成功响应 (200 OK):**
  ```json
  {
    "code": 0,
    "message": "success",
    "data": {
      "total": 3,
      "page": 1,
      "size": 20,
      "list": [
        {
          "id": "kb_news_001",
          "name": "新闻知识库",
          "description": "用于存储新闻内容的知识库",
          "status": "active",
          "document_count": 1520,
          "created_at": "2024-06-01 10:00:00"
        }
      ]
    }
  }
  ```

### **2.2 创建知识库**
- **接口:** `POST /api/v1/news_collector/knowledge_bases`
- **认证:** 是
- **请求体 (JSON):**
  ```json
  {
    "name": "科技新闻库",
    "description": "专门用于科技类新闻的知识库",
    "chunk_method": "naive",
    "auto_parse": true
  }
  ```
- **成功响应 (200 OK):**
  ```json
  {
    "code": 0,
    "message": "创建成功",
    "data": { "id": "kb_tech_001" }
  }
  ```

---

## **三、 新闻源管理 (News Sources)**

### **3.1 获取新闻源列表**
- **接口:** `GET /api/v1/news_collector/sources`
- **描述:** 分页、筛选、排序获取新闻源列表。
- **认证:** 是
- **查询参数:**
  - `page` (integer, 可选, 默认 1): 页码。
  - `size` (integer, 可选, 默认 20): 每页数量。
  - `keyword` (string, 可选): 按名称或备注进行模糊搜索。
  - `status` (string, 可选): 按状态筛选 (`active` 或 `inactive`)。
  - `sort_by` (string, 可选, 默认 `created_at`): 排序字段 (`name`, `created_at`, `news_count`)。
  - `order` (string, 可选, 默认 `desc`): 排序方式 (`asc` 或 `desc`)。
- **成功响应 (200 OK):**
  ```json
  {
    "code": 0,
    "message": "success",
    "data": {
      "total": 1,
      "page": 1,
      "size": 20,
      "list": [
        {
          "id": 1,
          "name": "新浪新闻",
          "url": "https://news.sina.com.cn",
          "remark": "默认示例",
          "status": "active",
          "selector_config": {
            "title_selector": "h1.main-title",
            "content_selector": ".article-content",
            "time_selector": ".time-source .time"
          },
          "created_at": "2024-06-01 10:00:00",
          "updated_at": "2024-06-01 10:00:00",
          "news_count": 1520,
          "last_task_id": 1001,
          "last_run_status": "success",
          "last_run_time": "2024-06-05 10:05:00"
        }
      ]
    }
  }
  ```

### **3.2 新增新闻源**
- **接口:** `POST /api/v1/news_collector/sources`
- **认证:** 是
- **请求体 (JSON):**
  ```json
  {
    "name": "网易新闻",
    "url": "https://news.163.com",
    "remark": "科技和娱乐频道",
    "status": "active",
    "selector_config": {
      "title_selector": "h1",
      "content_selector": ".post-body",
      "time_selector": ".post-info .time"
    }
  }
  ```
- **成功响应 (200 OK):**
  ```json
  {
    "code": 0,
    "message": "创建成功",
    "data": { "id": 2 }
  }
  ```

### **3.3 获取单个新闻源详情**
- **接口:** `GET /api/v1/news_collector/sources/{id}`
- **认证:** 是
- **成功响应 (200 OK):** (内容同 3.1 列表中的单个对象)

### **3.4 更新新闻源**
- **接口:** `PUT /api/v1/news_collector/sources/{id}`
- **描述:** 全量更新。请求体需包含所有可修改字段。
- **认证:** 是
- **请求体 (JSON):**
  ```json
  {
    "name": "网易新闻-更新",
    "url": "https://news.163.com/latest/",
    "remark": "更新后的备注",
    "status": "inactive",
    "selector_config": {
      "title_selector": "h1.title",
      "content_selector": ".content",
      "time_selector": ".time"
    }
  }
  ```
- **成功响应 (200 OK):**
  ```json
  {
    "code": 0,
    "message": "更新成功",
    "data": { "id": 2 }
  }
  ```

### **3.5 删除新闻源**
- **接口:** `DELETE /api/v1/news_collector/sources/{id}`
- **描述:** 删除单个新闻源。
- **认证:** 是
- **成功响应 (200 OK):**
  ```json
  {
    "code": 0,
    "message": "删除成功",
    "data": null
  }
  ```

### **3.6 验证新闻源可用性**
- **接口:** `POST /api/v1/news_collector/sources/validate`
- **描述:** 测试给定的 URL 或规则是否能成功抓取到内容，不保存到数据库。
- **认证:** 是
- **请求体 (JSON):**
  ```json
  {
    "url": "https://tech.sina.com.cn/discovery/",
    "selector_config": {
      "title_selector": "h1",
      "content_selector": ".article-content"
    }
  }
  ```
- **成功响应 (200 OK):**
  ```json
  {
    "code": 0,
    "message": "验证通过，可抓取",
    "data": {
      "title": "抓取到的测试标题...",
      "content_sample": "抓取到的内容片段预览...",
      "article_count": 15
    }
  }
  ```

---

## **四、 新闻抓取任务管理 (Scraping Tasks)**

### **4.1 获取抓取任务列表**
- **接口:** `GET /api/v1/news_collector/tasks`
- **认证:** 是
- **查询参数:**
  - `page`, `size`, `sort_by`, `order` (同 3.1)
  - `status` (string, 可选): 任务状态 (`pending`, `running`, `success`, `failed`)
  - `start_date`, `end_date` (string, 可选): 按创建日期筛选 (`YYYY-MM-DD`)
- **成功响应 (200 OK):**
  ```json
  {
    "code": 0,
    "message": "success",
    "data": {
      "total": 1,
      "page": 1,
      "size": 20,
      "list": [
        {
          "id": 1001,
          "task_name": "每日新闻抓取",
          "kb_id": "kb_news_001",
          "kb_name": "新闻知识库",
          "source_names": ["新浪新闻", "网易新闻"],
          "status": "success",
          "success_count": 48,
          "failed_count": 2,
          "auto_parse": true,
          "finished_at": "2024-06-01 10:05:00",
          "created_at": "2024-06-01 09:55:00"
        }
      ]
    }
  }
  ```

### **4.2 创建抓取任务**
- **接口:** `POST /api/v1/news_collector/tasks`
- **认证:** 是
- **请求体 (JSON):**
  ```json
  {
    "task_name": "科技新闻定时抓取",
    "kb_id": "kb_tech_001",
    "source_ids": [1, 2],
    "auto_parse": true,
    "schedule_type": "daily",
    "schedule_time": "09:00",
    "schedule_days": [1, 2, 3, 4, 5],
    "max_articles_per_source": 50
  }
  ```
- **成功响应 (200 OK):**
  ```json
  { "code": 0, "message": "任务创建成功", "data": { "id": 1002 } }
  ```

### **4.3 获取单个任务详情**
- **接口:** `GET /api/v1/news_collector/tasks/{id}`
- **认证:** 是
- **成功响应 (200 OK):**
  ```json
  {
    "code": 0,
    "message": "success",
    "data": {
      "id": 1001,
      "task_name": "每日新闻抓取",
      "status": "success",
      "kb_id": "kb_news_001",
      "auto_parse": true,
      "run_log": [
        {
          "source_id": 1,
          "source_name": "新浪新闻",
          "status": "success",
          "fetched_count": 30,
          "parsed_count": 28,
          "message": "成功抓取30条新闻，解析28条"
        },
        {
          "source_id": 2,
          "source_name": "网易新闻",
          "status": "failed",
          "fetched_count": 18,
          "parsed_count": 0,
          "message": "抓取超时，部分新闻可能丢失"
        }
      ]
    }
  }
  ```

### **4.4 手动执行任务**
- **接口:** `POST /api/v1/news_collector/tasks/{id}/execute`
- **认证:** 是
- **成功响应 (200 OK):**
  ```json
  { "code": 0, "message": "任务已开始执行", "data": { "task_id": 1001, "status": "running" } }
  ```

### **4.5 停止执行任务**
- **接口:** `POST /api/v1/news_collector/tasks/{id}/stop`
- **认证:** 是
- **成功响应 (200 OK):**
  ```json
  { "code": 0, "message": "已发送停止指令", "data": { "task_id": 1001 } }
  ```

### **4.6 删除抓取任务**
- **接口:** `DELETE /api/v1/news_collector/tasks/{id}`
- **认证:** 是
- **成功响应 (200 OK):** (同 3.5)

---

## **五、 新闻内容管理 (News Content)**

### **5.1 获取新闻列表**
- **接口:** `GET /api/v1/news_collector/news`
- **认证:** 是
- **查询参数:** (同 3.1, `sort_by` 可选 `publish_time`)
  - `source_id` (integer, 可选): 按新闻源ID筛选。
  - `kb_id` (string, 可选): 按知识库ID筛选。
  - `parse_status` (string, 可选): 按解析状态筛选 (`pending`, `success`, `failed`)。
- **成功响应 (200 OK):**
  ```json
  {
    "code": 0,
    "message": "success",
    "data": {
      "total": 1,
      "page": 1,
      "size": 20,
      "list": [
        {
          "id": 2001,
          "title": "新闻标题",
          "summary": "新闻内容摘要...",
          "source_name": "新浪新闻",
          "kb_name": "新闻知识库",
          "status": "active",
          "parse_status": "success",
          "document_id": "doc_12345",
          "publish_time": "2024-06-01 09:00:00"
        }
      ]
    }
  }
  ```

### **5.2 获取新闻详情**
- **接口:** `GET /api/v1/news_collector/news/{id}`
- **认证:** 是
- **成功响应 (200 OK):**
  ```json
  {
    "code": 0,
    "message": "success",
    "data": {
      "id": 2001,
      "title": "新闻标题",
      "content_html": "<h1>...</h1><p>...</p>",
      "content_text": "...",
      "summary": "AI生成的摘要...",
      "url": "https://...",
      "publish_time": "...",
      "status": "active",
      "parse_status": "success",
      "document_id": "doc_12345",
      "tags": ["科技", "AI"],
      "metadata": { "author": "...", "word_count": 1500 },
      "source": { "id": 1, "name": "新浪新闻" },
      "knowledge_base": { "id": "kb_123", "name": "新闻知识库" },
      "task": { "id": 1001, "name": "每日新闻抓取" }
    }
  }
  ```

### **5.3 重新解析新闻到知识库**
- **接口:** `POST /api/v1/news_collector/news/{id}/reparse`
- **认证:** 是
- **成功响应 (200 OK):**
  ```json
  { "code": 0, "message": "重新解析已开始", "data": { "id": 2001, "status": "parsing" } }
  ```

### **5.4 更新新闻内容 (局部更新)**
- **接口:** `PATCH /api/v1/news_collector/news/{id}`
- **认证:** 是
- **请求体 (JSON):**
  ```json
  {
    "title": "（已编辑）新闻标题",
    "tags": ["科技", "AI", "深度学习"],
    "status": "inactive"
  }
  ```
- **成功响应 (200 OK):**
  ```json
  { "code": 0, "message": "更新成功", "data": { "id": 2001 } }
  ```

### **5.5 删除新闻**
- **接口:** `DELETE /api/v1/news_collector/news/{id}`
- **认证:** 是
- **成功响应 (200 OK):** (同 3.5)

---

## **六、 统计报表 (Statistics)**

### **6.1 获取统计概览**
- **接口:** `GET /api/v1/news_collector/stats/overview`
- **认证:** 是
- **成功响应 (200 OK):**
  ```json
  {
    "code": 0,
    "message": "success",
    "data": {
      "total_sources": 10,
      "total_tasks": 5,
      "total_news": 15230,
      "total_knowledge_bases": 3,
      "today_news_count": 128,
      "parsed_news_count": 14850,
      "success_rate_24h": 98.5,
      "parse_success_rate": 97.5
    }
  }
  ```

### **6.2 获取时序统计数据 (用于图表)**
- **接口:** `GET /api/v1/news_collector/stats/timeseries`
- **认证:** 是
- **查询参数:**
  - `start_date`, `end_date` (string, 必填)
  - `interval` (string, 可选, `daily` 或 `hourly`, 默认 `daily`)
- **成功响应 (200 OK):**
  ```json
  {
    "code": 0,
    "message": "success",
    "data": {
      "labels": ["06-01", "06-02", "06-03"],
      "datasets": [
        { "label": "抓取成功数", "data": [120, 150, 130] },
        { "label": "抓取失败数", "data": [5, 2, 8] },
        { "label": "解析成功数", "data": [115, 148, 125] },
        { "label": "解析失败数", "data": [5, 2, 5] }
      ]
    }
  }
  ```

## **七、 数据模型 (Data Models)**

### **7.1 KnowledgeBase**
```json
{
  "id": "string",
  "name": "string",
  "description": "string",
  "chunk_method": "string",
  "status": "active|inactive",
  "document_count": "integer",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

### **7.2 NewsSource**
```json
{
  "id": "integer",
  "name": "string",
  "url": "string",
  "remark": "string",
  "status": "active|inactive",
  "selector_config": {
    "title_selector": "string",
    "content_selector": "string",
    "time_selector": "string"
  },
  "created_at": "datetime",
  "updated_at": "datetime",
  "news_count": "integer",
  "last_task_id": "integer",
  "last_run_status": "string",
  "last_run_time": "datetime"
}
```

### **7.3 NewsTask**
```json
{
  "id": "integer",
  "task_name": "string",
  "kb_id": "string",
  "source_ids": ["integer"],
  "status": "pending|running|success|failed",
  "auto_parse": "boolean",
  "schedule_type": "manual|once|daily|weekly",
  "schedule_time": "string",
  "schedule_days": ["integer"],
  "max_articles_per_source": "integer",
  "success_count": "integer",
  "failed_count": "integer",
  "created_at": "datetime",
  "updated_at": "datetime",
  "finished_at": "datetime"
}
```

### **7.4 NewsContent**
```json
{
  "id": "integer",
  "title": "string",
  "content_html": "string",
  "content_text": "string",
  "summary": "string",
  "url": "string",
  "publish_time": "datetime",
  "status": "active|inactive",
  "parse_status": "pending|success|failed",
  "document_id": "string",
  "tags": ["string"],
  "metadata": "object",
  "source_id": "integer",
  "kb_id": "string",
  "task_id": "integer",
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

---

## **八、 变更记录**

### **v1.1 (2025-07-24)**
- 添加知识库管理接口
- 为新闻源添加 selector_config 配置
- 为任务添加 auto_parse 和 max_articles_per_source 参数  
- 为新闻内容添加 parse_status 和 document_id 字段
- 添加重新解析新闻接口
- 更新统计接口，增加解析相关统计
- 完善数据模型定义
