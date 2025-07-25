# 新闻抓取与管理平台

一个集成到 RAGFlow 的智能新闻抓取与管理系统，提供自动化新闻抓取、内容解析和知识库管理功能。

## 🌟 功能特性

- **智能新闻抓取**: 支持多种新闻网站的自动抓取
- **可配置解析器**: 灵活的CSS选择器配置，适应不同网站结构
- **任务调度系统**: 支持手动、定时和周期性抓取任务
- **RAGFlow集成**: 自动将新闻内容解析到知识库
- **统计报表**: 详细的抓取和解析统计数据
- **RESTful API**: 完整的API接口，支持前后端分离
- **异步处理**: 高效的并发抓取和处理

## 📋 系统架构

```
新闻抓取系统/
├── news_collector/           # 核心模块
│   ├── models.py            # 数据模型
│   ├── scraper.py           # 新闻抓取器
│   ├── manager.py           # 管理器
│   ├── database.py          # 数据库模型
│   └── config.py            # 配置管理
├── api/apps/news_collector/ # API接口
│   ├── routes.py            # 路由定义
│   ├── services.py          # 业务逻辑
│   └── schemas.py           # 数据结构
├── docs/                    # 文档
│   └── news_collector_api_v1.1.md
└── 脚本文件
    ├── setup_news_collector.py
    ├── test_news_collector.py
    └── install_news_collector.bat
```

## 🚀 快速开始

### 1. 安装依赖

**Windows:**
```bash
install_news_collector.bat
```

**Linux/macOS:**
```bash
pip install -r news_collector_requirements.txt
```

### 2. 配置环境

创建或编辑 `.env` 文件：
```env
RAGFLOW_API_KEY=your-ragflow-api-key
RAGFLOW_BASE_URL=http://localhost:9380
LOG_LEVEL=INFO
SCRAPER_TIMEOUT=30
SCRAPER_MAX_CONCURRENT=10
```

### 3. 初始化系统

```bash
python setup_news_collector.py
```

### 4. 运行测试

```bash
python test_news_collector.py
```

## 📖 API 文档

完整的API文档请参考：[news_collector_api_v1.1.md](docs/news_collector_api_v1.1.md)

### 主要接口

| 功能 | 方法 | 端点 |
|------|------|------|
| 知识库管理 | GET/POST | `/api/v1/news_collector/knowledge_bases` |
| 新闻源管理 | GET/POST/PUT/DELETE | `/api/v1/news_collector/sources` |
| 抓取任务 | GET/POST/DELETE | `/api/v1/news_collector/tasks` |
| 新闻内容 | GET/PATCH/DELETE | `/api/v1/news_collector/news` |
| 统计报表 | GET | `/api/v1/news_collector/stats` |

## 💡 使用示例

### 创建新闻源

```python
from news_collector import services

source_data = {
    "name": "新浪科技",
    "url": "https://tech.sina.com.cn/",
    "remark": "新浪科技频道",
    "selector_config": {
        "title_selector": "h1",
        "content_selector": ".article-content",
        "time_selector": ".time-source .time"
    }
}

result = services.create_news_source(source_data)
print(f"新闻源ID: {result['id']}")
```

### 创建抓取任务

```python
task_data = {
    "task_name": "每日科技新闻抓取",
    "kb_id": "your_knowledge_base_id",
    "source_ids": [1, 2],
    "auto_parse": True,
    "max_articles_per_source": 50
}

result = services.create_news_task(task_data)
print(f"任务ID: {result['id']}")
```

### 执行抓取任务

```python
import asyncio

async def run_task():
    result = await services.execute_news_task(task_id=1)
    print(f"任务状态: {result['status']}")

asyncio.run(run_task())
```

## 🔧 配置说明

### 选择器配置

系统支持为不同网站配置CSS选择器：

```python
selector_config = {
    "title_selector": "h1",                    # 标题选择器
    "content_selector": ".article-content",   # 内容选择器
    "time_selector": ".time",                 # 时间选择器
    "author_selector": ".author",             # 作者选择器
    "link_selector": "a"                      # 链接选择器
}
```

### 预设配置

系统为常见新闻网站提供了预设配置：
- 新浪新闻 (sina.com.cn)
- 网易新闻 (163.com)
- 搜狐新闻 (sohu.com)
- 新华网 (xinhuanet.com)
- 人民网 (people.com.cn)

## 📊 功能模块

### 1. 新闻源管理
- 添加、编辑、删除新闻源
- 配置抓取规则和选择器
- 验证新闻源可用性
- 查看抓取统计

### 2. 抓取任务管理
- 创建手动或定时任务
- 配置抓取参数
- 监控任务执行状态
- 查看执行日志

### 3. 新闻内容管理
- 浏览抓取的新闻列表
- 查看新闻详细内容
- 管理新闻标签和状态
- 重新解析到知识库

### 4. 知识库集成
- 自动创建和管理知识库
- 智能文档解析
- 支持多种格式输出
- 解析状态跟踪

### 5. 统计报表
- 抓取成功率统计
- 解析成功率统计
- 时序数据图表
- 性能监控指标

## 🛠️ 技术栈

- **后端**: Python 3.7+, Flask, SQLAlchemy
- **异步处理**: aiohttp, asyncio
- **HTML解析**: BeautifulSoup4
- **数据库**: SQLite/MySQL/PostgreSQL
- **API**: RESTful, JSON
- **集成**: RAGFlow SDK

## 📈 性能特性

- **并发抓取**: 支持多线程并发处理
- **错误处理**: 完善的重试和错误恢复机制
- **内存优化**: 流式处理大文件
- **缓存机制**: 智能缓存减少重复请求
- **限流控制**: 尊重网站robots.txt和访问频率

## 🔒 安全考虑

- **User-Agent轮换**: 避免被反爬虫机制阻止
- **请求间隔**: 控制访问频率，避免对目标网站造成压力
- **数据验证**: 严格的输入验证和数据清洗
- **权限控制**: API访问权限管理

## 📝 开发指南

### 添加新的新闻源

1. 分析目标网站结构
2. 配置CSS选择器
3. 测试抓取效果
4. 添加预设配置（可选）

### 扩展功能

1. 继承基础类实现自定义功能
2. 添加新的API端点
3. 更新数据模型
4. 编写测试用例

### 部署建议

1. 使用Docker容器化部署
2. 配置负载均衡
3. 设置监控和日志
4. 定期备份数据

## 🤝 贡献指南

1. Fork 项目
2. 创建功能分支
3. 提交变更
4. 创建 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 🆘 常见问题

### Q: 抓取失败怎么办？
A: 检查网络连接、目标网站可用性、选择器配置是否正确。

### Q: 如何提高抓取效率？
A: 调整并发数量、优化选择器、使用缓存机制。

### Q: 如何处理反爬虫？
A: 设置合理的请求间隔、轮换User-Agent、使用代理IP。

### Q: 如何集成到现有项目？
A: 参考`setup_news_collector.py`文件的集成方法。

## 📞 支持

如有问题或建议，请：
1. 查看文档和FAQ
2. 提交Issue
3. 联系开发团队

---

**开发团队**: RAGFlow Team  
**版本**: v1.0.0  
**更新日期**: 2025-07-24
