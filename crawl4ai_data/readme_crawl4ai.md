# 新闻收集器 API 使用文档

本文档提供新闻收集器模块的完整API参考和使用指南。该模块基于`crawl4ai`实现智能网页抓取，支持多种抓取模式和增量更新。

**最后更新**: 2026-01-15 | **当前版本**: v5.2

---

## 目录

- [快速开始](#快速开始)
- [核心概念](#核心概念)
- [API 参考](#api-参考)
- [爬虫架构](#爬虫架构)
- [性能优化与稳定性](#性能优化与稳定性)
- [问题排查](#问题排查)
- [更新日志](#更新日志)

---

## 快速开始

### 通用认证

所有API都需要在请求头中包含Bearer Token：
```bash
Authorization: Bearer <YOUR_API_TOKEN>
```

### 常用场景

#### 1. 批量添加新闻源

```bash
curl -X POST 'http://localhost:9380/api/v1/news_collector/sources' \
  -H 'Authorization: Bearer <YOUR_API_TOKEN>' \
  -H 'Content-Type: application/json' \
  -d "[
    {
      "name": "国家能源局",
      "url": "http://www.nea.gov.cn/",
      "source_type": "policy",
      "region": "国家"
    },
    {
      "name": "国家发改委",
      "url": "https://www.ndrc.gov.cn/",
      "source_type": "policy",
      "region": "国家"
    }
  ]"
```

#### 2. 主题搜索爬取（推荐）

```bash
curl -X POST 'http://localhost:9380/api/v1/news_collector/topic_search' \
  -H 'Authorization: Bearer <YOUR_API_TOKEN>' \
  -H 'Content-Type: application/json' \
  -d '{
    "source_ids": ["source_id_1", "source_id_2"],
    "keywords": ["电力市场", "现货交易"],
    "max_pages_per_source": 30,
    "kb_id": "your_kb_id",
    "parse": false
  }'
```

---

## 核心概念

### 抓取模式

系统通过新闻源的`remark`字段控制抓取模式：

| 模式 | remark值 | 说明 | 适用场景 |
|------|----------|------|----------|
| **精确模式** | `"1"` | 使用CSS选择器提取内容 | 固定结构网站，需要高精度 |
| **自动模式** | `"0"` | AI自动识别内容 | 快速探索，结构简单网站 |

### 抓取方法对比

| 方法 | 适用场景 | 优势 | 限制 |
|------|----------|------|------|
| **主题搜索** (推荐) | 政策文档收集 | 智能评分、政策识别、Task隔离 | 需要BestFirst策略支持 |
| **URL Seeding** | 有sitemap的网站 | 快速URL发现 | 中国政府网站支持率低 |
| **即时抓取** | 简单递归爬取 | 配置简单 | 无智能过滤 |

---

## 性能优化与稳定性

### v5.2 重大改进 (2026-01-15)

#### 1. Task Isolation (任务隔离) ⭐

**问题**: 在多源连续爬取时，前一个源的 `crawl4ai` 内部状态（如 `ContextVars`）可能未清理干净，导致后续源无法启动 Streaming 模式甚至崩溃。

**解决方案**: 采用 **Task Isolation** 架构。
- 每个新闻源的爬取任务都在一个独立的 `asyncio.Task` 中运行。
- 利用 `asyncio` 的上下文隔离特性，确保每个源的 `crawl4ai` 环境是完全隔离和干净的。
- 即使前一个源发生异常（如 `ValueError: ContextVar...`），也不会污染主线程或后续源。

#### 2. Streaming 模式增强

**改进**: 即使在多源环境下，也能稳定保持 Streaming 模式。
- **效果**: 实时返回爬取结果，无需等待整个任务完成。
- **内存**: 显著降低峰值内存占用。

#### 3. 稳健的等待策略 (Commit Strategy)

**调整**: 将默认等待策略从 `domcontentloaded` 调整为 `commit`，并配合较长的超时时间（30s）。
- **原因**: 部分政府网站（如国家能源局）响应较慢或包含阻塞资源，`domcontentloaded` 可能超时或导致连接被重置。
- **效果**: `commit` 策略只要服务器开始响应即视为成功，大大提高了对慢速/老旧网站的兼容性，同时配合 `BestFirst` 策略依然能有效提取链接。

#### 4. 反爬虫增强

- **User-Agent**: 自动注入真实浏览器的 User-Agent。
- **Viewport**: 模拟标准桌面分辨率。

---

## 问题排查

### 常见问题

#### Q1: 爬取结果为0或很少

**可能原因**:
1. **反爬虫**: 网站检测到爬虫，返回 403 或空页面。
   - *解决*: 检查日志中的 `HTML前200字符`。系统已内置 User-Agent 伪装。
2. **超时**: 网站响应过慢。
   - *解决*: 系统已将超时延长至 30s 并使用 `commit` 策略。
3. **已访问**: URL 已在数据库中存在。
   - *解决*: 查看日志中 "跳过已访问URL" 的数量。

#### Q2: 报错 "ValueError: ... created in a different Context"

**原因**: `crawl4ai` 在 `async generator` 清理时的已知问题。
**影响**: 在 v5.2 之前会导致后续任务失败。
**现状**: 在 v5.2 中，通过 **Task Isolation** 已完全隔离该错误，**可以忽略此日志**，它不会影响后续爬取。

#### Q3: 第二个源总是失败

**原因**: 上下文污染。
**解决**: 已通过 v5.2 的 Task Isolation 架构彻底解决。

---

## 更新日志

### v5.2 (2026-01-15) - 稳定性与隔离版

**核心修复**:
- ✅ **Task Isolation**: 使用独立 Task 封装每个源的爬取，彻底解决多源连续爬取时的上下文污染问题。
- ✅ **ContextVar 修复**: 解决了第二个源无法启动 Streaming 模式的 Bug。
- ✅ **Wait Strategy**: 调整为 `wait_until="commit"`，显著提升对国家能源局 (NEA) 等网站的抓取成功率。
- ✅ **Anti-Bot**: 增加了 User-Agent 和 Viewport 伪装。

### v5.1 (2026-01-13) - 性能优化版

- ✅ **Streaming模式**: TopicCrawler启用实时流式处理。
- ✅ **批量预加载去重**: URL查重速度提升250倍。

---

**维护者**: RagFlow News Collector Team
