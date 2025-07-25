# 🚀 新闻收集器文档集成方案

## 💡 核心设计理念

**"统一文档流"** - 将新闻内容直接集成到RAGFlow的现有文档系统中，避免重复存储，实现前端文件管理页面的完整展示。

## 🏗️ 架构设计

### 1. 数据流程图
```
新闻抓取 → 转换为Document → 存储到Storage → 显示在文件管理
    ↓           ↓              ↓            ↓
NewsSource  Document       STORAGE_IMPL   前端文件树
NewsTask    File           (MinIO/本地)    统一界面
NewsContent File2Document
```

### 2. 核心优势

✅ **避免重复存储** - 新闻内容直接转为Document，不在NewsContent中重复存储正文
✅ **统一文件管理** - 在前端文件管理页面中完整展示抓取结果和目录结构
✅ **自动解析集成** - 新闻可自动触发RAGFlow的解析流程
✅ **保持元数据** - 新闻特有信息（作者、发布时间等）保存在NewsContent中
✅ **目录结构化** - 自动创建层级文件夹："新闻收集" → "新闻源名称" → "具体文章"

## 📊 数据库模型变更

### 原有模型 → 优化后模型

**NewsContent (优化前):**
```python
- title, content, summary  # 重复存储内容
- kb_id, doc_id           # 关联混乱
```

**NewsContent (优化后):**
```python
- document_id             # 直接关联Document
- original_url, author    # 新闻元数据
- category, tags, summary # 新闻特有字段
- 移除 title, content     # 避免重复存储
```

## 🔄 集成流程详解

### 1. 文件夹结构创建
```
📁 知识库根目录
└── 📰 新闻收集/
    ├── 📡 科技新闻源/
    │   ├── 📄 最新AI技术突破.txt
    │   └── 📄 量子计算进展.txt
    └── 📡 财经新闻源/
        ├── 📄 股市分析报告.txt
        └── 📄 经济政策解读.txt
```

### 2. 新闻转文档流程
```python
# 1. 抓取新闻
news_data = fetcher.fetch_article_list()

# 2. 创建File记录（在文件管理中显示）
file = File.create({
    "name": "新闻标题.txt",
    "parent_id": source_folder_id,
    "type": "text",
    "source_type": "news_article"
})

# 3. 创建Document记录（用于解析和搜索）
document = Document.create({
    "name": news_data["title"],
    "kb_id": task.kb_id,
    "location": "news/task_id/file_id.txt",
    "meta_fields": {
        "source_url": news_data["url"],
        "author": news_data["author"],
        "news_source": source.name
    }
})

# 4. 建立关联关系
File2Document.create({
    "file_id": file.id,
    "document_id": document.id
})

# 5. 保存内容到存储
STORAGE_IMPL.put(document.location, formatted_content)

# 6. 创建新闻元数据记录
NewsContent.create({
    "document_id": document.id,
    "original_url": news_data["url"],
    "author": news_data["author"]
    # 不再存储title和content
})
```

### 3. 自动解析触发
```python
# 如果任务启用auto_parse，自动触发文档解析
if task.auto_parse:
    Document.update(run="1").where(Document.id == doc_id).execute()
```

## 🎯 前端展示效果

### 文件管理页面
```
📁 知识库文件
├── 📰 新闻收集/           ← 自动创建的新闻根目录
│   ├── 📡 科技新闻/       ← 按新闻源分组
│   │   ├── 📄 AI突破.txt  ← 每篇新闻一个文件
│   │   └── 📄 量子计算.txt
│   └── 📡 财经新闻/
│       └── 📄 股市分析.txt
├── 📁 用户上传文档/
└── 📁 其他资料/
```

### 文档详情页面
```
标题: AI技术最新突破
来源: 科技新闻源
作者: 张三
发布时间: 2024-01-15 10:30:00
原文链接: https://example.com/ai-news
解析状态: 已完成
分块数量: 15
索引状态: 已索引
```

## 📝 API增强

### 新增端点
```bash
# 获取任务产生的文档列表
GET /v1/news_collector/tasks/{task_id}/documents

# 响应示例
{
  "code": 0,
  "data": {
    "task_id": "task_123",
    "documents": [
      {
        "id": "doc_456",
        "name": "AI技术突破",
        "progress": 100,
        "chunk_num": 15,
        "news_url": "https://example.com/ai-news",
        "news_author": "张三",
        "news_category": "科技"
      }
    ],
    "total": 1
  }
}
```

## 🛠️ 实现细节

### 1. 内容格式化
```python
def _format_news_content(news_data, source):
    return f"""
标题: {news_data['title']}
来源: {source.name}
原文链接: {news_data['url']}
作者: {news_data.get('author', '未知')}
发布时间: {format_time(news_data.get('publish_time'))}

正文内容:
{'=' * 50}
{news_data.get('content', '')}
{'=' * 50}
抓取时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
```

### 2. 文件名处理
```python
def _sanitize_filename(title):
    # 移除非法字符，限制长度
    sanitized = re.sub(r'[<>:"/\\|?*]', '_', title)
    return sanitized[:100] if len(sanitized) > 100 else sanitized
```

### 3. 去重机制
```python
# 基于标题+URL的哈希去重
content_hash = hashlib.md5((title + url).encode('utf-8')).hexdigest()
existing = NewsContent.select().where(
    NewsContent.content_hash == content_hash,
    NewsContent.tenant_id == tenant_id
).first()
```

## 🚀 使用步骤

### 1. 数据库迁移
```bash
# 运行更新后的初始化脚本
python init_news_tables.py
```

### 2. 创建新闻源和任务
```bash
# 创建新闻源
curl -X POST /v1/news_collector/sources \
  -d '{"name": "科技新闻", "url": "https://tech.example.com"}'

# 创建抓取任务
curl -X POST /v1/news_collector/tasks \
  -d '{
    "task_name": "每日科技新闻",
    "kb_id": "your_kb_id",
    "source_ids": ["source_id"],
    "auto_parse": true
  }'
```

### 3. 执行任务并查看结果
```bash
# 执行任务
curl -X POST /v1/news_collector/tasks/{task_id}/execute

# 查看生成的文档
curl /v1/news_collector/tasks/{task_id}/documents
```

### 4. 前端查看
- 打开RAGFlow前端
- 进入对应知识库的文件管理页面
- 查看 "📰 新闻收集" 文件夹下的结构化内容

## 📈 优势总结

### 对比传统方案
| 特性 | 传统方案 | 统一文档流方案 |
|------|----------|----------------|
| 存储效率 | 重复存储 | 统一存储 |
| 前端展示 | 需要额外开发 | 直接使用现有界面 |
| 解析集成 | 需要手动处理 | 自动触发解析 |
| 搜索功能 | 需要单独实现 | 直接使用RAGFlow搜索 |
| 维护成本 | 高 | 低 |

### 核心收益
✅ **零重复存储** - 新闻内容只在Document中存储一份  
✅ **完美前端集成** - 在文件管理页面完整展示抓取结果  
✅ **自动解析流程** - 新闻自动进入RAGFlow解析pipeline  
✅ **结构化展示** - 按新闻源自动组织文件夹结构  
✅ **统一搜索体验** - 新闻内容可通过RAGFlow搜索找到  

这个方案完美解决了您提出的问题，避免了重复存储，并且让新闻收集的结果能够在前端文件管理页面中完整、美观地展示！🎯
