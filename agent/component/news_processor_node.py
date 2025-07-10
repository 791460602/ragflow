from agent.component.base import ComponentBase, ComponentParamBase
from agent.component.news_processor_impl import NewsProcessor, NewsProcessorParam
from typing import List, Dict, Any

class NewsProcessorNodeParam(NewsProcessorParam):
    """
    可视化节点专用参数类，继承原有 NewsProcessorParam，便于前端自动渲染。
    """
    # 可根据需要扩展额外的可视化参数
    pass

class NewsProcessorNode(ComponentBase):
    component_name = "NewsProcessorNode"

    @classmethod
    def get_component_meta(cls):
        return {
            "name": cls.component_name,
            "display_name": "新闻处理节点",
            "category": "信息处理",
            "icon": "icon-process",
            "description": "处理新闻内容，解析并存储到知识库，支持附件下载，可用于可视化流程节点。",
            "param_schema": NewsProcessorNodeParam.__doc__,
            "input_ports": ["news_list"],
            "output_ports": ["processed_news"]
        }

    def _run(self, history, news_list=None, **kwargs):
        param = NewsProcessorNodeParam()
        param.update(self._param.as_dict())
        param.check()
        processor = NewsProcessor()
        processor._param = param
        processor._input = {"content": news_list} if news_list is not None else self._input
        result = processor._run(history, **kwargs)
        return {"processed_news": result} 