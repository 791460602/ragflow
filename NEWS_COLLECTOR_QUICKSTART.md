# 新闻收集器 - 快速开始

## 🎯 系统状态
✅ **已完成集成** - 新闻收集器已成功集成到RAGFlow  
✅ **数据库就绪** - 相关数据表已创建  
✅ **API可用** - 新闻收集器API已注册  

## 🚀 下一步操作

### 1. 配置认证信息
编辑 `test_news_collector_api.py` 文件，填入您的认证信息：
```python
AUTH_TOKEN = "你的Authorization值"
SESSION_COOKIE = "你的session值" 
```

### 2. 测试API功能
```bash
python test_news_collector_api.py
```

### 3. 测试系统功能
```bash
python test_news_collector.py
```

### 4. 创建知识库和新闻源
- 在RAGFlow前端创建知识库
- 使用API创建新闻源和抓取任务

## 📂 核心文件

### 🔧 配置和测试
- `setup_news_collector.py` - 系统初始化脚本
- `test_news_collector.py` - 功能测试脚本  
- `test_news_collector_api.py` - API测试脚本
- `quick_auth_test.py` - 认证测试脚本
- `fix_nltk.py` - NLTK依赖修复

### 💻 核心代码
- `api/db/db_models.py` - 数据库模型
- `api/db/services/news_service.py` - 新闻服务
- `api/db/services/news_integration_service.py` - 文档集成服务
- `api/apps/news_collector_app.py` - API路由

### 📚 文档
- `docs/news_collector/` - 完整文档集合

## 🎯 API端点

| 端点 | 功能 | 认证 |
|------|------|------|
| `GET /v1/news_collector/ping` | 健康检查 | ❌ |
| `GET/POST /v1/news_collector/sources` | 新闻源管理 | ✅ |
| `GET/POST /v1/news_collector/tasks` | 任务管理 | ✅ |
| `GET /v1/news_collector/news` | 内容查看 | ✅ |
| `GET /v1/news_collector/statistics` | 统计信息 | ✅ |

## 🔗 相关命令

```bash
# 启动RAGFlow服务
python api/ragflow_server.py

# 初始化新闻收集器
python setup_news_collector.py

# 测试功能
python test_news_collector.py

# 测试API
python test_news_collector_api.py
```

---
📖 **详细文档**: 查看 `docs/news_collector/` 文件夹获取完整文档
