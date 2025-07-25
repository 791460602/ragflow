# 新闻收集器使用指南

## 🎉 系统状态

✅ **已完成集成**: 新闻收集器已成功集成到RAGFlow项目中  
✅ **数据库就绪**: 新闻相关数据表已创建  
✅ **演示数据**: 已创建3个示例新闻源  
✅ **API接口**: 新闻收集器API已注册到RAGFlow  

## 🚀 快速开始

### 第一步：启动服务

```bash
# 进入RAGFlow项目目录
cd e:\Remote\ragflow

# 启动RAGFlow服务
python api/ragflow_server.py
```

### 第二步：登录获取Token

1. 浏览器访问: `http://localhost:9380`
2. 登录RAGFlow系统
3. 在设置页面或浏览器开发者工具中获取API Token

### 第三步：测试API

```bash
# 测试服务健康检查（无需认证）
curl http://localhost:9380/v1/news_collector/ping

# 测试获取新闻源（需要认证）
curl -H "Authorization: Bearer <YOUR_TOKEN>" \
     http://localhost:9380/v1/news_collector/sources
```

## 📋 API接口列表

| 端点 | 方法 | 描述 | 认证 |
|------|------|------|------|
| `/v1/news_collector/ping` | GET | 健康检查 | ❌ |
| `/v1/news_collector/sources` | GET/POST | 新闻源管理 | ✅ |
| `/v1/news_collector/tasks` | GET/POST | 抓取任务管理 | ✅ |
| `/v1/news_collector/news` | GET | 新闻内容查看 | ✅ |
| `/v1/news_collector/statistics` | GET | 统计信息 | ✅ |
| `/v1/news_collector/tasks/{id}/documents` | GET | 任务文档 | ✅ |

## 🔧 测试工具

### 1. 功能测试脚本
```bash
python test_news_collector.py
```
**功能**: 测试数据库、新闻源、任务创建等功能

### 2. API连通性测试
```bash
python test_news_collector_api.py
```
**功能**: 测试API端点连通性和基础功能

### 3. 修复NLTK依赖
```bash
python fix_nltk.py
```
**功能**: 解决自然语言处理依赖问题

## 📝 使用示例

### 创建新闻源
```bash
curl -X POST \
  -H "Authorization: Bearer <YOUR_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "科技新闻",
    "url": "https://tech.sina.com.cn/",
    "remark": "新浪科技频道"
  }' \
  http://localhost:9380/v1/news_collector/sources
```

### 创建抓取任务
```bash
curl -X POST \
  -H "Authorization: Bearer <YOUR_TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "task_name": "每日科技新闻",
    "kb_id": "<知识库ID>",
    "source_ids": ["<新闻源ID>"],
    "auto_parse": true,
    "max_articles_per_source": 10
  }' \
  http://localhost:9380/v1/news_collector/tasks
```

## 💡 特色功能

### 🔄 统一文档流
- **功能**: 新闻内容直接转换为RAGFlow文档
- **优势**: 避免重复存储，统一管理
- **位置**: 前端文件管理页面的"📰 新闻收集"文件夹

### 📁 自动文件组织
- **结构**: 按新闻源自动创建文件夹
- **命名**: `新闻收集/{新闻源名称}/{日期}`
- **格式**: 支持多种文档格式（HTML、Markdown、纯文本）

### 🔍 全文搜索
- **集成**: 新闻内容自动进入RAGFlow搜索索引
- **能力**: 支持语义搜索和关键词搜索
- **应用**: 可用于知识问答和内容检索

## ⚠️ 常见问题

### Q1: API返回401错误
**原因**: 缺少认证令牌  
**解决**: 确保在请求头中添加 `Authorization: Bearer <TOKEN>`

### Q2: NLTK相关错误
**原因**: 缺少自然语言处理依赖  
**解决**: 运行 `python fix_nltk.py` 下载必要资源

### Q3: 任务创建失败
**原因**: 需要有效的知识库ID  
**解决**: 先在RAGFlow前端创建知识库，然后使用其ID

### Q4: 新闻抓取失败
**原因**: 网站反爬虫策略或网络问题  
**解决**: 检查网络连接，调整User-Agent和请求频率

## 📊 系统监控

### 查看统计信息
```bash
curl -H "Authorization: Bearer <YOUR_TOKEN>" \
     http://localhost:9380/v1/news_collector/statistics
```

### 查看任务状态
```bash
curl -H "Authorization: Bearer <YOUR_TOKEN>" \
     http://localhost:9380/v1/news_collector/tasks
```

## 🔗 相关文档

- [RAGFlow官方文档](https://github.com/infiniflow/ragflow)
- [API详细说明](NEWS_COLLECTOR_API_DOCS.md)
- [统一文档流架构](NEWS_COLLECTOR_UNIFIED_DOCUMENT_FLOW.md)

## 🎯 后续开发

1. **前端界面**: 集成到RAGFlow Web界面
2. **定时任务**: 添加定时抓取功能
3. **内容过滤**: 增强内容质量过滤
4. **多语言支持**: 扩展多语言新闻处理

---

**🎉 恭喜！新闻收集器已完全集成到RAGFlow中，开始您的智能新闻管理之旅吧！**
