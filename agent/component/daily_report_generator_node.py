from agent.component.base import ComponentBase, ComponentParamBase
from agent.component.daily_report_generator import DailyReportGenerator, DailyReportGeneratorParam
from typing import List, Dict, Any

class DailyReportGeneratorNodeParam(DailyReportGeneratorParam):
    """
    可视化节点专用参数类，继承原有 DailyReportGeneratorParam，便于前端自动渲染。
    """
    # 可根据需要扩展额外的可视化参数
    pass

class DailyReportGeneratorNode(ComponentBase):
    component_name = "DailyReportGeneratorNode"

    @classmethod
    def get_component_meta(cls):
        return {
            "name": cls.component_name,
            "display_name": "简报生成节点",
            "category": "内容生成",
            "icon": "icon-report",
            "description": "基于知识库内容生成结构化简报，支持多模板和附件摘要，可用于可视化流程节点。",
            "param_schema": DailyReportGeneratorNodeParam.__doc__,
            "input_ports": ["processed_news"],
            "output_ports": ["report"]
        }

    def _run(self, history, processed_news=None, **kwargs):
        param = DailyReportGeneratorNodeParam()
        param.update(self._param.as_dict())
        param.check()
        generator = DailyReportGenerator()
        generator._param = param
        generator._input = {"content": processed_news} if processed_news is not None else self._input
        result = generator._run(history, **kwargs)
        return {"report": result} 