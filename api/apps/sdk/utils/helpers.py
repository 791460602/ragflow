# -*- coding: utf-8 -*-
"""
辅助工具函数模块
"""

import re


def enrich_metadata(article_data: dict, source: dict) -> dict:
    """将新闻源的结构化信息写入文章 metadata 方便后续过滤。"""
    if not isinstance(article_data, dict):
        return article_data

    metadata = article_data.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}

    source_dict = source or {}

    metadata.update(
        {
            "source_id": source_dict.get("id") or metadata.get("source_id"),
            "source_name": source_dict.get("name") or metadata.get("source_name"),
            "source_url": source_dict.get("url") or metadata.get("source_url") or article_data.get("url"),
            "source_type": source_dict.get("source_type") or metadata.get("source_type") or "news",
            "region": source_dict.get("region") or metadata.get("region"),
            "issuer": source_dict.get("issuer") or metadata.get("issuer"),
            "policy_theme": source_dict.get("policy_theme") or metadata.get("policy_theme") or [],
        }
    )

    article_data["metadata"] = metadata
    return article_data


def sanitize_filename(name: str) -> str:
    """清理字符串，使其成为一个合法的文件名的一部分"""
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    name = re.sub(r"\s+", "_", name)
    return name[:50]
