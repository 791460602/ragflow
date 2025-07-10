from agent.component.base import ComponentBase, ComponentParamBase
from typing import Dict, Any

class NewsSchedulerNodeParam(ComponentParamBase):
    """
    可视化节点专用参数类，支持调度类型、cron表达式、间隔等参数，便于前端自动渲染。
    """
    schedule_type: str = "cron"  # cron/interval/manual
    cron: str = "0 8 * * *"      # 默认每天8点
    interval_seconds: int = 86400 # 默认一天
    # 可扩展更多调度参数

    def check(self):
        assert self.schedule_type in ["cron", "interval", "manual"], "schedule_type必须为cron/interval/manual"
        if self.schedule_type == "cron":
            assert isinstance(self.cron, str) and self.cron, "cron表达式不能为空"
        if self.schedule_type == "interval":
            assert self.interval_seconds > 0, "interval_seconds必须大于0"

class NewsSchedulerNode(ComponentBase):
    component_name = "NewsSchedulerNode"

    @classmethod
    def get_component_meta(cls):
        return {
            "name": cls.component_name,
            "display_name": "新闻调度节点",
            "category": "调度控制",
            "icon": "icon-schedule",
            "description": "定时或手动触发新闻抓取-处理-简报流程，可用于可视化流程节点。",
            "param_schema": NewsSchedulerNodeParam.__doc__,
            "input_ports": ["workflow"],
            "output_ports": ["result"]
        }

    def _run(self, history, workflow=None, **kwargs):
        param = NewsSchedulerNodeParam()
        param.update(self._param.as_dict())
        param.check()
        # 这里只做参数透传，实际调度由服务层实现
        # 可扩展为调用后端调度API
        return {"result": f"调度已设置: {param.schedule_type}"} 