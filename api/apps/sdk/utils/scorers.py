# -*- coding: utf-8 -*-
"""
内容评分器模块
"""

from typing import List


class ChineseContentScorer:
    """基于内容的中文关键词相关性评分器"""

    def __init__(self, keywords: List[str], k1: float = 1.5, b: float = 0.75):
        self.keywords = keywords
        self.k1 = k1
        self.b = b
        self.keyword_patterns = self._build_keyword_patterns(keywords)

    def _build_keyword_patterns(self, keywords: List[str]) -> List[str]:
        """构建关键词匹配模式"""
        patterns = []
        for kw in keywords:
            patterns.append(kw)
            if len(kw) > 2:
                for i in range(len(kw) - 1):
                    patterns.append(kw[i : i + 2])
                    if i + 3 <= len(kw):
                        patterns.append(kw[i : i + 3])
        return list(set(patterns))

    def score(self, content: str, title: str = "") -> float:
        """计算内容与关键词的相关性分数"""
        if not content:
            return 0.0

        full_text = (title + " ") * 3 + content
        full_text_lower = full_text.lower()
        doc_length = len(full_text)
        avg_doc_length = 500

        total_score = 0.0
        matched_keywords = 0

        for keyword in self.keywords:
            keyword_lower = keyword.lower()

            if keyword_lower in full_text_lower:
                freq = full_text_lower.count(keyword_lower)
                numerator = freq * (self.k1 + 1)
                denominator = freq + self.k1 * (1 - self.b + self.b * doc_length / avg_doc_length)
                score = numerator / denominator
                total_score += score * 2
                matched_keywords += 1

        if matched_keywords == 0:
            return 0.0

        coverage = matched_keywords / len(self.keywords)
        normalized_score = min(1.0, total_score / (len(self.keywords) * 3))
        final_score = coverage * 0.4 + normalized_score * 0.6

        return round(final_score, 4)

    def get_matched_keywords(self, content: str) -> List[str]:
        """返回匹配到的关键词列表"""
        matched = []
        content_lower = content.lower()
        for keyword in self.keywords:
            if keyword.lower() in content_lower:
                matched.append(keyword)
        return matched
