from agent.component.base import ComponentBase, ComponentParamBase
from agent.component.news_crawler_impl import NewsCrawler, NewsCrawlerParam
from typing import List, Dict, Any

class NewsCrawlerNodeParam(NewsCrawlerParam):
    """
    可视化节点专用参数类，继承原有 NewsCrawlerParam，便于前端自动渲染。
    """
    # 可根据需要扩展额外的可视化参数
    pass

class NewsCrawlerNode(ComponentBase):
    component_name = "NewsCrawlerNode"

    @classmethod
    def get_component_meta(cls):
        return {
            "name": cls.component_name,
            "display_name": "新闻抓取节点",
            "category": "信息获取",
            "icon": "icon-news",
            "description": "从指定新闻源抓取新闻，支持多源、关键词过滤等，可用于可视化流程节点。",
            "param_schema": NewsCrawlerNodeParam.__doc__,
            "input_ports": [],
            "output_ports": ["news_list"]
        }

    def _run(self, history, **kwargs):
        # 参数注入
        param = NewsCrawlerNodeParam()
        param.update(self._param.as_dict())
        param.check()
        # 调用原有 NewsCrawler 逻辑
        crawler = NewsCrawler()
        crawler._param = param
        crawler._input = self._input
        result = crawler._run(history, **kwargs)
        return {"news_list": result} 