from .services import add_news_history, get_news_sources, save_news_to_kb_with_sdk
from typing import List

def fetch_news(source_ids: List[int], kb_id=None, sdk_client=None):
    sources = [s for s in get_news_sources() if s.id in source_ids]
    news_list = []
    results = []
    for source in sources:
        # 这里只做模拟，实际可用 requests/BeautifulSoup 抓取网页内容
        title = f"来自 {source.name} 的模拟新闻标题"
        content = f"{source.name} 的新闻内容正文。"
        news_list.append({"title": title, "content": content})
        item = add_news_history(source.name, title, status="成功")
        results.append(item)
    # 新增：上传到知识库
    if kb_id and sdk_client:
        save_news_to_kb_with_sdk(news_list, kb_id, sdk_client)
    return results 