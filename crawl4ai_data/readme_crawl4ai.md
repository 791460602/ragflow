# 新闻收集器 API 使用文档

本文档为新闻收集器模块提供详细的API使用说明，旨在帮助团队成员快速理解和使用相关功能。该模块主要负责新闻源的维护、基于`crawl4ai`的即时网页抓取，以及通过持久化哈希记录实现的增量抓取。

## 核心概念

### 抓取模式
本系统支持两种网页抓取模式，通过在创建或更新新闻源时设置 `remark` 字段来控制：

1.  **精确模式 (`remark: "1"`)**:
    * 此模式依赖于用户提供的CSS选择器 (`fetch_config`) 来精确提取网页的标题、正文、作者、发布时间等信息。
    * **优点**: 准确度高，能从结构复杂的页面中提取干净的数据。
    * **适用场景**: 针对特定、结构固定的网站进行长期、高质量的数据采集。

2.  **自动模式 (`remark: "0"`)**:
    * 此模式不依赖任何CSS选择器，完全依靠 `crawl4ai` 自身的AI算法智能分析和提取页面的核心内容。
    * **优点**: 配置简单，适应性强，无需为每个网站单独配置选择器。
    * **适用场景**: 快速对新网站进行探索性抓取或批量抓取结构简单的网站。

---

## API 端点详解

**通用头部信息**: 所有需要授权的API都必须在HTTP请求的Header中包含 `Authorization` 字段。
`Authorization: Bearer <YOUR_API_TOKEN>`

### 1. 新闻源管理 (CRUD)

#### 1.1 获取新闻源列表
* **功能**: 分页获取已配置的新闻源列表。
* **Endpoint**: `GET /api/v1/news_collector/sources`
* **Query 参数**:
    * `page` (可选, 整数, 默认值 `1`): 页码。
    * `page_size` (可选, 整数, 默认值 `20`): 每页数量。
* **`curl` 示例**:
    ```bash
    curl -X GET 'http://localhost:9380/api/v1/news_collector/sources?page=1&page_size=5' \
    -H 'Authorization: Bearer <YOUR_API_TOKEN>'
    ```

#### 1.2 创建新闻源
* **功能**: 新增一个新闻源，并指定其抓取模式。
* **Endpoint**: `POST /api/v1/news_collector/sources`
* **Body**: JSON对象

* **`curl` 示例 (精确模式, `remark: "1"`)**:
    ```bash
    curl -X POST 'http://localhost:9380/api/v1/news_collector/sources' \
    -H 'Authorization: Bearer <YOUR_API_TOKEN>' \
    -H 'Content-Type: application/json' \
    -d '{
        "name": "发改委-精确模式",
        "url": "https://www.ndrc.gov.cn",
        "status": "active",
        "remark": "1",
        "fetch_config": {
            "link_selector": "div.nav a[href], div.main a[href], div.news-left a[href], div.news-right a[href], div.xxgk-left a[href], div.dating-right a[href], div.data-left a[href], div.data-right a[href], div.hudong-left a[href], div.hudong-right a[href]",
            "title_selector": "h2.article_title, span.title, h1, div.titles",
            "content_selector": "div.article-content, div.TRS_Editor, div.article-box, p.te",
            "publication_time_selector": "span.date, span.times, div.time",
            "author_selector": "span.author, div.ly.laiyuantext"
        }
    }'
    ```

* **`curl` 示例 (自动模式, `remark: "0"`)**:
    ```bash
    curl -X POST 'http://localhost:9380/api/v1/news_collector/sources' \
    -H 'Authorization: Bearer <YOUR_API_TOKEN>' \
    -H 'Content-Type: application/json' \
    -d '{
        "name": "国家能源局-自动模式",
        "url": "https://www.nea.gov.cn",
        "remark": "0",
        "status": "active",
        "fetch_config": {}
    }'
    ```

#### 1.3 更新新闻源
* **功能**: 修改指定ID的新闻源信息。
* **Endpoint**: `PUT /api/v1/news_collector/sources/{source_id}`
* **Body**: JSON对象 (包含需要修改的字段)
* **`curl` 示例**:
    ```bash
    curl -X PUT 'http://localhost:9380/api/v1/news_collector/sources/your_source_id_here' \
    -H 'Authorization: Bearer <YOUR_API_TOKEN>' \
    -H 'Content-Type: application/json' \
    -d '{
        "name": "这是一个更新后的名称",
        "status": "inactive"
    }'
    ```

#### 1.4 删除新闻源
* **功能**: 删除指定ID的新闻源 (逻辑删除，状态置为`deleted`)。
* **Endpoint**: `DELETE /api/v1/news_collector/sources/{source_id}`
* **`curl` 示例**:
    ```bash
    curl -X DELETE 'http://localhost:9380/api/v1/news_collector/sources/your_source_id_here' \
    -H 'Authorization: Bearer <YOUR_API_TOKEN>'
    ```

### 2. 即时抓取

* **功能**: 根据传入的新闻源ID列表，启动一个后台异步抓取任务。任务会从数据库加载配置，并根据 `remark` 字段自动选择抓取模式。
* **Endpoint**: `POST /api/v1/news_collector/crawl_from_post`
* **Body**: JSON对象
* **`curl` 示例**:
    ```bash
    curl -X POST 'http://localhost:9380/api/v1/news_collector/crawl_from_post' \
    -H 'Authorization: Bearer <YOUR_API_TOKEN>' \
    -H 'Content-Type: application/json' \
    -d '{
        "source_ids": [
            "id_of_source_A",
            "id_of_source_B"
        ],
        "depth": 1,
        "max_pages_per_source": 10
    }'
    ```
* **注意**: 此接口会立即返回成功消息，实际的抓取在后台进行。请观察后端服务日志查看抓取进度和结果。抓取结果会保存在项目根目录下的 `crawl4ai_data` 文件夹中。

### 3. 内容与哈希管理

#### 3.1 查询已存储内容的哈希
* **功能**: 分页查看所有已抓取并存入数据库的内容记录及其哈希值，用于调试持久化去重功能。
* **Endpoint**: `GET /api/v1/news_collector/contents/hashes`
* **`curl` 示例**:
    ```bash
    curl -X GET 'http://localhost:9380/api/v1/news_collector/contents/hashes?page=1&page_size=10' \
    -H 'Authorization: Bearer <YOUR_API_TOKEN>'
    ```

#### 3.2 清除所有抓取历史
* **功能**: 删除数据库中所有已存储的内容记录，从而重置持久化去重历史。这是一个危险操作，请谨慎使用。
* **Endpoint**: `DELETE /api/v1/news_collector/contents`
* **`curl` 示例**:
    ```bash
    curl -X DELETE 'http://localhost:9380/api/v1/news_collector/contents' \
    -H 'Authorization: Bearer <YOUR_API_TOKEN>'
    ```