# -*- coding: utf-8 -*-
"""
政策文档检测器模块
"""

import re


class PolicyFeatureDetector:
    """检测页面是否为电力能源政策文档

    识别特征：
    1. 标题包含政策关键词（通知、文件、政策、办法等）
    2. 内容包含能源电力关键词
    3. 包含文号格式（如：发改能源〔2024〕123号）
    4. 包含附件下载链接
    """

    # 政策文档类型关键词
    POLICY_TYPE_KEYWORDS = [
        "通知",
        "文件",
        "政策",
        "办法",
        "规定",
        "意见",
        "方案",
        "规划",
        "决定",
        "批复",
        "公告",
        "函",
        "指导",
        "措施",
        "制度",
        "条例",
        "纲要",
        "指南",
        "标准",
        "细则",
        "暂行",
        "试行",
    ]

    # 能源电力相关关键词
    ENERGY_KEYWORDS = [
        "电力",
        "能源",
        "电网",
        "电价",
        "供电",
        "用电",
        "发电",
        "输电",
        "配电",
        "售电",
        "电量",
        "电费",
        "电力市场",
        "现货",
        "辅助服务",
        "可再生能源",
        "新能源",
        "光伏",
        "风电",
        "储能",
        "电站",
        "变电",
        "输变电",
        "电力系统",
        "电力调度",
        "电力交易",
        "电力改革",
        "电力规划",
        "电力建设",
        "电力监管",
        "电力安全",
        "节能减排",
    ]

    # 发文单位关键词
    ISSUER_KEYWORDS = [
        "发改委",
        "发展改革委",
        "国家发展改革委",
        "国家能源局",
        "能源局",
        "电监会",
        "能监办",
        "国务院",
        "工信部",
        "住建部",
        "财政部",
        "国家电网",
        "南方电网",
        "电力公司",
        "省政府",
        "市政府",
    ]

    # 文号正则表达式（匹配如：发改能源〔2024〕123号）
    DOC_NUMBER_PATTERNS = [
        re.compile(r"[〔\[]?\d{4}[〕\]]\s?\d{1,4}\s?号"),  # 〔2024〕123号
        re.compile(r"第\s?\d{1,4}\s?号"),  # 第123号
        re.compile(r"\d{4}年第\d{1,4}号"),  # 2024年第123号
    ]

    # 附件相关关键词
    ATTACHMENT_KEYWORDS = ["附件", "下载", "文件下载", "政策原文", "解读", "全文"]

    def __init__(self):
        pass

    def detect(self, html: str, title: str, content: str, url: str = "") -> dict:
        """检测是否为政策文档

        返回:
        {
            'is_policy': bool,          # 是否为政策文档
            'score': float,             # 政策特征分数 (0-1)
            'features': {               # 识别到的特征
                'has_policy_type': bool,
                'has_energy_keywords': bool,
                'has_doc_number': bool,
                'has_issuer': bool,
                'has_attachment': bool,
                'doc_number': str or None,
                'matched_energy_keywords': list
            }
        }
        """
        features = {
            "has_policy_type": False,
            "has_energy_keywords": False,
            "has_doc_number": False,
            "has_issuer": False,
            "has_attachment": False,
            "doc_number": None,
            "matched_energy_keywords": [],
        }

        # 1. 检测标题中的政策类型关键词
        for keyword in self.POLICY_TYPE_KEYWORDS:
            if keyword in title:
                features["has_policy_type"] = True
                break

        # 2. 检测能源电力关键词
        full_text = title + " " + content
        for keyword in self.ENERGY_KEYWORDS:
            if keyword in full_text:
                features["has_energy_keywords"] = True
                features["matched_energy_keywords"].append(keyword)

        # 3. 检测文号
        for pattern in self.DOC_NUMBER_PATTERNS:
            match = pattern.search(full_text[:500])  # 只搜索前500字符
            if match:
                features["has_doc_number"] = True
                features["doc_number"] = match.group(0)
                break

        # 4. 检测发文单位
        for keyword in self.ISSUER_KEYWORDS:
            if keyword in full_text[:300]:  # 只搜索前300字符
                features["has_issuer"] = True
                break

        # 5. 检测附件链接（从HTML中）
        for keyword in self.ATTACHMENT_KEYWORDS:
            if keyword in html:
                features["has_attachment"] = True
                break

        # 计算政策特征分数
        score = 0.0
        if features["has_policy_type"]:
            score += 0.3
        if features["has_energy_keywords"]:
            score += 0.3
        if features["has_doc_number"]:
            score += 0.2
        if features["has_issuer"]:
            score += 0.1
        if features["has_attachment"]:
            score += 0.1

        # 判定为政策文档的条件：
        # 1. 有政策类型关键词 + 有能源关键词，或
        # 2. 有文号 + 有能源关键词
        is_policy = (features["has_policy_type"] and features["has_energy_keywords"]) or (features["has_doc_number"] and features["has_energy_keywords"])

        return {"is_policy": is_policy, "score": score, "features": features}
