#
#  Copyright 2024 The InfiniFlow Authors. All Rights Reserved.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#
import logging
import json
import re
from abc import ABC
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import pandas as pd
from agent.component.base import ComponentBase, ComponentParamBase
from api.db.services.knowledgebase_service import KnowledgebaseService
from api.db.services.document_service import DocumentService
from api.db.services.chat_service import ChatService
from api.db import StatusEnum


class DailyReportGeneratorParam(ComponentParamBase):
    """
    定义每日简报生成组件的参数
    """
    
    def __init__(self):
        super().__init__()
        self.kb_ids = []  # 知识库ID列表
        self.template = "daily_brief"  # 报告模板
        self.language = "zh-CN"  # 报告语言
        self.include_attachments = True  # 是否包含附件信息
        self.attachment_summary = True  # 是否生成附件摘要
        self.max_attachment_summary_length = 500  # 附件摘要最大长度
        self.output_format = "markdown"  # 输出格式
        self.sections = ["summary", "key_events", "industry_trends", "attachments"]  # 报告章节
        self.max_news_count = 20  # 最大新闻数量
        self.categorize_news = True  # 是否对新闻分类
        self.include_summary = True  # 是否包含摘要
        self.date_range = 1  # 日期范围（天数）
        self.llm_model = "gpt-3.5-turbo"  # 使用的LLM模型
    
    def check(self):
        self.check_list_not_empty(self.kb_ids, "知识库ID列表")
        self.check_valid_value(self.template, "报告模板", ['daily_brief', 'executive_summary', 'industry_report', 'custom'])
        self.check_valid_value(self.language, "报告语言", ['zh-CN', 'en-US', 'ja-JP'])
        self.check_boolean(self.include_attachments, "是否包含附件信息")
        self.check_boolean(self.attachment_summary, "是否生成附件摘要")
        self.check_positive_integer(self.max_attachment_summary_length, "附件摘要最大长度")
        self.check_valid_value(self.output_format, "输出格式", ['markdown', 'json', 'text', 'html'])
        self.check_positive_integer(self.max_news_count, "最大新闻数量")
        self.check_boolean(self.categorize_news, "是否对新闻分类")
        self.check_boolean(self.include_summary, "是否包含摘要")
        self.check_positive_integer(self.date_range, "日期范围")


class DailyReportGenerator(ComponentBase, ABC):
    component_name = "DailyReportGenerator"
    
    def _run(self, history, **kwargs):
        """执行每日简报生成"""
        try:
            # 获取知识库数据
            news_data = self._get_news_from_kbs()
            
            if not news_data:
                return DailyReportGenerator.be_output("没有找到新闻数据")
            
            # 处理附件信息
            if self._param.include_attachments:
                news_data = self._process_attachments(news_data)
            
            # 生成报告内容
            report_content = self._generate_report(news_data)
            
            # 格式化输出
            output = self._format_output(report_content)
            
            return DailyReportGenerator.be_output(output)
            
        except Exception as e:
            logging.error(f"生成每日简报失败: {str(e)}")
            return DailyReportGenerator.be_output(f"生成每日简报失败: {str(e)}")
    
    def _get_news_from_kbs(self) -> List[Dict[str, Any]]:
        """从知识库获取新闻数据"""
        all_news = []
        
        for kb_id in self._param.kb_ids:
            try:
                # 验证知识库
                e, kb = KnowledgebaseService.get_by_id(kb_id)
                if not e:
                    logging.warning(f"知识库不存在: {kb_id}")
                    continue
                
                # 获取文档列表
                docs = DocumentService.get_docs_by_kb_id(kb_id)
                
                # 过滤新闻文档
                news_docs = []
                for doc in docs:
                    if self._is_news_document(doc):
                        news_docs.append(doc)
                
                # 转换为新闻数据
                for doc in news_docs:
                    news_item = self._convert_doc_to_news(doc)
                    if news_item:
                        all_news.append(news_item)
                
            except Exception as e:
                logging.error(f"获取知识库 {kb_id} 数据失败: {str(e)}")
                continue
        
        # 按时间排序
        all_news.sort(key=lambda x: x.get('time', ''), reverse=True)
        
        # 限制数量
        return all_news[:self._param.max_news_count]
    
    def _is_news_document(self, doc) -> bool:
        """判断是否是新闻文档"""
        # 检查文档名称或内容是否包含新闻特征
        name = doc.get('name', '').lower()
        content = doc.get('content', '').lower()
        
        # 新闻文档通常包含时间戳或特定格式
        news_patterns = [
            r'\d{4}[-/]\d{1,2}[-/]\d{1,2}',  # 日期格式
            r'\d{1,2}:\d{1,2}',  # 时间格式
            '新闻', 'news', '报道', '消息'
        ]
        
        for pattern in news_patterns:
            if re.search(pattern, name) or re.search(pattern, content):
                return True
        
        return False
    
    def _convert_doc_to_news(self, doc) -> Optional[Dict[str, Any]]:
        """将文档转换为新闻数据"""
        try:
            content = doc.get('content', '')
            if not content:
                return None
            
            # 解析结构化内容
            news_item = self._parse_structured_content(content)
            
            # 添加文档元信息
            news_item['doc_id'] = doc.get('id')
            news_item['kb_id'] = doc.get('kb_id')
            news_item['created_time'] = doc.get('created_time')
            
            return news_item
            
        except Exception as e:
            logging.error(f"转换文档失败: {str(e)}")
            return None
    
    def _parse_structured_content(self, content: str) -> Dict[str, Any]:
        """解析结构化内容"""
        news_item = {
            'title': '',
            'source': '',
            'time': '',
            'link': '',
            'summary': '',
            'full_content': '',
            'attachments': []
        }
        
        try:
            # 尝试解析Markdown格式
            lines = content.split('\n')
            current_section = None
            
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # 标题
                if line.startswith('# '):
                    news_item['title'] = line[2:].strip()
                
                # 元信息
                elif line.startswith('**元信息:**'):
                    meta_text = line.replace('**元信息:**', '').strip()
                    self._parse_meta_info(meta_text, news_item)
                
                # 摘要
                elif line.startswith('**摘要:**'):
                    news_item['summary'] = line.replace('**摘要:**', '').strip()
                
                # 详细内容
                elif line.startswith('**详细内容:**'):
                    current_section = 'content'
                    continue
                elif current_section == 'content':
                    if line.startswith('**附件:**'):
                        current_section = 'attachments'
                        continue
                    else:
                        if news_item['full_content']:
                            news_item['full_content'] += '\n' + line
                        else:
                            news_item['full_content'] = line
                
                # 附件
                elif current_section == 'attachments' and line.startswith(('1.', '2.', '3.', '4.', '5.')):
                    attachment_info = self._parse_attachment_line(line)
                    if attachment_info:
                        news_item['attachments'].append(attachment_info)
            
        except Exception as e:
            logging.error(f"解析结构化内容失败: {str(e)}")
        
        return news_item
    
    def _parse_meta_info(self, meta_text: str, news_item: Dict[str, Any]):
        """解析元信息"""
        parts = meta_text.split(' | ')
        for part in parts:
            if '来源:' in part:
                news_item['source'] = part.replace('来源:', '').strip()
            elif '时间:' in part:
                news_item['time'] = part.replace('时间:', '').strip()
            elif '链接:' in part:
                news_item['link'] = part.replace('链接:', '').strip()
    
    def _parse_attachment_line(self, line: str) -> Optional[Dict[str, Any]]:
        """解析附件行"""
        try:
            # 格式: "1. filename.pdf (12345 bytes)"
            match = re.match(r'\d+\.\s*(.+?)\s*\((\d+)\s*bytes\)', line)
            if match:
                return {
                    'filename': match.group(1).strip(),
                    'size': int(match.group(2))
                }
        except Exception as e:
            logging.error(f"解析附件行失败: {str(e)}")
        
        return None
    
    def _process_attachments(self, news_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """处理附件信息"""
        for news in news_data:
            if news.get('attachments'):
                # 生成附件摘要
                if self._param.attachment_summary:
                    news['attachment_summary'] = self._generate_attachment_summary(news['attachments'])
                
                # 统计附件信息
                news['attachment_stats'] = {
                    'total_count': len(news['attachments']),
                    'total_size': sum(att.get('size', 0) for att in news['attachments']),
                    'types': self._get_attachment_types(news['attachments'])
                }
        
        return news_data
    
    def _generate_attachment_summary(self, attachments: List[Dict[str, Any]]) -> str:
        """生成附件摘要"""
        if not attachments:
            return ""
        
        summary_parts = []
        
        # 按类型分组
        type_groups = {}
        for att in attachments:
            file_type = self._get_file_type(att['filename'])
            if file_type not in type_groups:
                type_groups[file_type] = []
            type_groups[file_type].append(att)
        
        # 生成摘要
        for file_type, atts in type_groups.items():
            count = len(atts)
            total_size = sum(att.get('size', 0) for att in atts)
            size_mb = total_size / (1024 * 1024)
            
            summary_parts.append(f"{count}个{file_type}文件，总大小{size_mb:.1f}MB")
        
        summary = "；".join(summary_parts)
        
        # 截断长度
        if len(summary) > self._param.max_attachment_summary_length:
            summary = summary[:self._param.max_attachment_summary_length] + "..."
        
        return summary
    
    def _get_file_type(self, filename: str) -> str:
        """获取文件类型"""
        ext = filename.lower().split('.')[-1] if '.' in filename else ''
        
        type_mapping = {
            'pdf': 'PDF',
            'doc': 'Word',
            'docx': 'Word',
            'ppt': 'PowerPoint',
            'pptx': 'PowerPoint',
            'xls': 'Excel',
            'xlsx': 'Excel'
        }
        
        return type_mapping.get(ext, '其他')
    
    def _get_attachment_types(self, attachments: List[Dict[str, Any]]) -> List[str]:
        """获取附件类型列表"""
        types = set()
        for att in attachments:
            file_type = self._get_file_type(att['filename'])
            types.add(file_type)
        return list(types)
    
    def _generate_report(self, news_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """生成报告内容"""
        report = {
            'title': self._generate_title(),
            'generated_time': datetime.now().isoformat(),
            'news_count': len(news_data),
            'sections': {}
        }
        
        # 生成各个章节
        for section in self._param.sections:
            if section == 'summary':
                report['sections']['summary'] = self._generate_summary(news_data)
            elif section == 'key_events':
                report['sections']['key_events'] = self._generate_key_events(news_data)
            elif section == 'industry_trends':
                report['sections']['industry_trends'] = self._generate_industry_trends(news_data)
            elif section == 'attachments':
                report['sections']['attachments'] = self._generate_attachments_section(news_data)
        
        return report
    
    def _generate_title(self) -> str:
        """生成报告标题"""
        today = datetime.now().strftime('%Y年%m月%d日')
        
        if self._param.language == 'zh-CN':
            return f"{today} 每日新闻简报"
        elif self._param.language == 'en-US':
            return f"Daily News Brief - {datetime.now().strftime('%B %d, %Y')}"
        else:
            return f"Daily News Brief - {today}"
    
    def _generate_summary(self, news_data: List[Dict[str, Any]]) -> str:
        """生成摘要章节"""
        if not self._param.include_summary:
            return ""
        
        # 统计信息
        total_news = len(news_data)
        sources = set(news.get('source', '') for news in news_data if news.get('source'))
        attachment_news = [news for news in news_data if news.get('attachments')]
        
        summary_parts = [
            f"今日共收集到 {total_news} 条新闻",
            f"涉及 {len(sources)} 个新闻源"
        ]
        
        if attachment_news:
            total_attachments = sum(len(news.get('attachments', [])) for news in attachment_news)
            summary_parts.append(f"其中 {len(attachment_news)} 条新闻包含附件，共 {total_attachments} 个附件")
        
        return "；".join(summary_parts) + "。"
    
    def _generate_key_events(self, news_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """生成关键事件章节"""
        key_events = []
        
        for news in news_data:
            event = {
                'title': news.get('title', ''),
                'source': news.get('source', ''),
                'time': news.get('time', ''),
                'summary': news.get('summary', ''),
                'link': news.get('link', ''),
                'has_attachments': bool(news.get('attachments'))
            }
            
            if news.get('attachment_summary'):
                event['attachment_summary'] = news['attachment_summary']
            
            key_events.append(event)
        
        return key_events
    
    def _generate_industry_trends(self, news_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """生成行业趋势章节"""
        trends = {
            'hot_topics': self._extract_hot_topics(news_data),
            'source_distribution': self._analyze_source_distribution(news_data),
            'attachment_analysis': self._analyze_attachments(news_data)
        }
        
        return trends
    
    def _extract_hot_topics(self, news_data: List[Dict[str, Any]]) -> List[str]:
        """提取热门话题"""
        # 简单的关键词提取
        all_text = " ".join([
            news.get('title', '') + " " + news.get('summary', '')
            for news in news_data
        ])
        
        # 常见关键词
        keywords = ['AI', '人工智能', '科技', '创新', '投资', '创业', '数字化转型', '互联网']
        hot_topics = []
        
        for keyword in keywords:
            if keyword in all_text:
                hot_topics.append(keyword)
        
        return hot_topics[:5]  # 返回前5个热门话题
    
    def _analyze_source_distribution(self, news_data: List[Dict[str, Any]]) -> Dict[str, int]:
        """分析来源分布"""
        source_count = {}
        
        for news in news_data:
            source = news.get('source', '未知来源')
            source_count[source] = source_count.get(source, 0) + 1
        
        return source_count
    
    def _analyze_attachments(self, news_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """分析附件情况"""
        attachment_news = [news for news in news_data if news.get('attachments')]
        
        if not attachment_news:
            return {'total_attachments': 0, 'attachment_ratio': 0}
        
        total_attachments = sum(len(news.get('attachments', [])) for news in attachment_news)
        attachment_ratio = len(attachment_news) / len(news_data) * 100
        
        return {
            'total_attachments': total_attachments,
            'attachment_ratio': round(attachment_ratio, 1),
            'news_with_attachments': len(attachment_news)
        }
    
    def _generate_attachments_section(self, news_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """生成附件章节"""
        if not self._param.include_attachments:
            return {}
        
        attachment_news = [news for news in news_data if news.get('attachments')]
        
        if not attachment_news:
            return {'message': '今日无附件'}
        
        # 统计信息
        total_attachments = sum(len(news.get('attachments', [])) for news in attachment_news)
        total_size = sum(
            sum(att.get('size', 0) for att in news.get('attachments', []))
            for news in attachment_news
        )
        
        # 按类型统计
        type_stats = {}
        for news in attachment_news:
            for att in news.get('attachments', []):
                file_type = self._get_file_type(att['filename'])
                if file_type not in type_stats:
                    type_stats[file_type] = {'count': 0, 'size': 0}
                type_stats[file_type]['count'] += 1
                type_stats[file_type]['size'] += att.get('size', 0)
        
        return {
            'total_attachments': total_attachments,
            'total_size_mb': round(total_size / (1024 * 1024), 2),
            'type_distribution': type_stats,
            'news_with_attachments': [
                {
                    'title': news.get('title', ''),
                    'source': news.get('source', ''),
                    'attachments': news.get('attachments', [])
                }
                for news in attachment_news
            ]
        }
    
    def _format_output(self, report_content: Dict[str, Any]):
        """格式化输出"""
        if self._param.output_format == "markdown":
            return self._format_markdown(report_content)
        elif self._param.output_format == "json":
            return json.dumps(report_content, ensure_ascii=False, indent=2)
        elif self._param.output_format == "html":
            return self._format_html(report_content)
        else:  # text
            return self._format_text(report_content)
    
    def _format_markdown(self, report_content: Dict[str, Any]):
        """格式化为Markdown"""
        md_parts = []
        
        # 标题
        md_parts.append(f"# {report_content['title']}")
        md_parts.append(f"**生成时间:** {report_content['generated_time']}")
        md_parts.append(f"**新闻数量:** {report_content['news_count']} 条")
        md_parts.append("")
        
        # 摘要
        if 'summary' in report_content['sections'] and report_content['sections']['summary']:
            md_parts.append("## 摘要")
            md_parts.append(report_content['sections']['summary'])
            md_parts.append("")
        
        # 关键事件
        if 'key_events' in report_content['sections']:
            md_parts.append("## 关键事件")
            for i, event in enumerate(report_content['sections']['key_events'], 1):
                md_parts.append(f"### {i}. {event['title']}")
                md_parts.append(f"**来源:** {event['source']}")
                if event['time']:
                    md_parts.append(f"**时间:** {event['time']}")
                if event['summary']:
                    md_parts.append(f"**摘要:** {event['summary']}")
                if event['link']:
                    md_parts.append(f"**链接:** [{event['link']}]({event['link']})")
                if event['has_attachments']:
                    md_parts.append("**包含附件:** 是")
                    if event.get('attachment_summary'):
                        md_parts.append(f"**附件摘要:** {event['attachment_summary']}")
                md_parts.append("")
        
        # 行业趋势
        if 'industry_trends' in report_content['sections']:
            trends = report_content['sections']['industry_trends']
            md_parts.append("## 行业趋势")
            
            if trends.get('hot_topics'):
                md_parts.append("### 热门话题")
                md_parts.append(", ".join(trends['hot_topics']))
                md_parts.append("")
            
            if trends.get('source_distribution'):
                md_parts.append("### 来源分布")
                for source, count in trends['source_distribution'].items():
                    md_parts.append(f"- {source}: {count} 条")
                md_parts.append("")
            
            if trends.get('attachment_analysis'):
                analysis = trends['attachment_analysis']
                md_parts.append("### 附件分析")
                md_parts.append(f"- 包含附件的新闻: {analysis.get('news_with_attachments', 0)} 条")
                md_parts.append(f"- 附件占比: {analysis.get('attachment_ratio', 0)}%")
                md_parts.append("")
        
        # 附件详情
        if 'attachments' in report_content['sections'] and self._param.include_attachments:
            attachments_section = report_content['sections']['attachments']
            if attachments_section and 'message' not in attachments_section:
                md_parts.append("## 附件详情")
                md_parts.append(f"**总附件数:** {attachments_section['total_attachments']}")
                md_parts.append(f"**总大小:** {attachments_section['total_size_mb']} MB")
                md_parts.append("")
                
                if attachments_section.get('type_distribution'):
                    md_parts.append("### 类型分布")
                    for file_type, stats in attachments_section['type_distribution'].items():
                        size_mb = stats['size'] / (1024 * 1024)
                        md_parts.append(f"- {file_type}: {stats['count']} 个 ({size_mb:.1f} MB)")
                    md_parts.append("")
                
                if attachments_section.get('news_with_attachments'):
                    md_parts.append("### 包含附件的新闻")
                    for news in attachments_section['news_with_attachments']:
                        md_parts.append(f"#### {news['title']}")
                        md_parts.append(f"**来源:** {news['source']}")
                        md_parts.append("**附件:**")
                        for att in news['attachments']:
                            size_mb = att['size'] / (1024 * 1024)
                            md_parts.append(f"- {att['filename']} ({size_mb:.1f} MB)")
                        md_parts.append("")
        
        return "\n".join(md_parts)
    
    def _format_html(self, report_content: Dict[str, Any]):
        """格式化为HTML"""
        html_parts = [
            "<!DOCTYPE html>",
            "<html>",
            "<head>",
            "<meta charset='UTF-8'>",
            "<title>每日新闻简报</title>",
            "<style>",
            "body { font-family: Arial, sans-serif; margin: 20px; }",
            "h1 { color: #333; }",
            "h2 { color: #666; border-bottom: 1px solid #eee; }",
            "h3 { color: #888; }",
            ".meta { color: #999; font-size: 14px; }",
            ".summary { background: #f9f9f9; padding: 10px; border-radius: 5px; }",
            ".event { margin: 20px 0; padding: 15px; border-left: 4px solid #007cba; }",
            ".attachment { background: #f0f8ff; padding: 5px; margin: 5px 0; border-radius: 3px; }",
            "</style>",
            "</head>",
            "<body>"
        ]
        
        # 标题
        html_parts.append(f"<h1>{report_content['title']}</h1>")
        html_parts.append(f"<div class='meta'>生成时间: {report_content['generated_time']}</div>")
        html_parts.append(f"<div class='meta'>新闻数量: {report_content['news_count']} 条</div>")
        
        # 摘要
        if 'summary' in report_content['sections'] and report_content['sections']['summary']:
            html_parts.append("<h2>摘要</h2>")
            html_parts.append(f"<div class='summary'>{report_content['sections']['summary']}</div>")
        
        # 关键事件
        if 'key_events' in report_content['sections']:
            html_parts.append("<h2>关键事件</h2>")
            for i, event in enumerate(report_content['sections']['key_events'], 1):
                html_parts.append(f"<div class='event'>")
                html_parts.append(f"<h3>{i}. {event['title']}</h3>")
                html_parts.append(f"<div class='meta'>来源: {event['source']}</div>")
                if event['time']:
                    html_parts.append(f"<div class='meta'>时间: {event['time']}</div>")
                if event['summary']:
                    html_parts.append(f"<p>{event['summary']}</p>")
                if event['link']:
                    html_parts.append(f"<div class='meta'>链接: <a href='{event['link']}'>{event['link']}</a></div>")
                if event['has_attachments']:
                    html_parts.append("<div class='meta'>包含附件: 是</div>")
                    if event.get('attachment_summary'):
                        html_parts.append(f"<div class='attachment'>{event['attachment_summary']}</div>")
                html_parts.append("</div>")
        
        # 行业趋势
        if 'industry_trends' in report_content['sections']:
            trends = report_content['sections']['industry_trends']
            html_parts.append("<h2>行业趋势</h2>")
            
            if trends.get('hot_topics'):
                html_parts.append("<h3>热门话题</h3>")
                html_parts.append(f"<p>{', '.join(trends['hot_topics'])}</p>")
            
            if trends.get('source_distribution'):
                html_parts.append("<h3>来源分布</h3>")
                html_parts.append("<ul>")
                for source, count in trends['source_distribution'].items():
                    html_parts.append(f"<li>{source}: {count} 条</li>")
                html_parts.append("</ul>")
        
        # 附件详情
        if 'attachments' in report_content['sections'] and self._param.include_attachments:
            attachments_section = report_content['sections']['attachments']
            if attachments_section and 'message' not in attachments_section:
                html_parts.append("<h2>附件详情</h2>")
                html_parts.append(f"<div class='meta'>总附件数: {attachments_section['total_attachments']}</div>")
                html_parts.append(f"<div class='meta'>总大小: {attachments_section['total_size_mb']} MB</div>")
        
        html_parts.extend([
            "</body>",
            "</html>"
        ])
        
        return "\n".join(html_parts)
    
    def _format_text(self, report_content: Dict[str, Any]):
        """格式化为纯文本"""
        text_parts = []
        
        # 标题
        text_parts.append(report_content['title'])
        text_parts.append(f"生成时间: {report_content['generated_time']}")
        text_parts.append(f"新闻数量: {report_content['news_count']} 条")
        text_parts.append("")
        
        # 摘要
        if 'summary' in report_content['sections'] and report_content['sections']['summary']:
            text_parts.append("摘要:")
            text_parts.append(report_content['sections']['summary'])
            text_parts.append("")
        
        # 关键事件
        if 'key_events' in report_content['sections']:
            text_parts.append("关键事件:")
            for i, event in enumerate(report_content['sections']['key_events'], 1):
                text_parts.append(f"{i}. {event['title']}")
                text_parts.append(f"   来源: {event['source']}")
                if event['time']:
                    text_parts.append(f"   时间: {event['time']}")
                if event['summary']:
                    text_parts.append(f"   摘要: {event['summary']}")
                if event['link']:
                    text_parts.append(f"   链接: {event['link']}")
                if event['has_attachments']:
                    text_parts.append("   包含附件: 是")
                    if event.get('attachment_summary'):
                        text_parts.append(f"   附件摘要: {event['attachment_summary']}")
                text_parts.append("")
        
        # 行业趋势
        if 'industry_trends' in report_content['sections']:
            trends = report_content['sections']['industry_trends']
            text_parts.append("行业趋势:")
            
            if trends.get('hot_topics'):
                text_parts.append("热门话题:")
                text_parts.append(", ".join(trends['hot_topics']))
                text_parts.append("")
            
            if trends.get('source_distribution'):
                text_parts.append("来源分布:")
                for source, count in trends['source_distribution'].items():
                    text_parts.append(f"  {source}: {count} 条")
                text_parts.append("")
        
        # 附件详情
        if 'attachments' in report_content['sections'] and self._param.include_attachments:
            attachments_section = report_content['sections']['attachments']
            if attachments_section and 'message' not in attachments_section:
                text_parts.append("附件详情:")
                text_parts.append(f"总附件数: {attachments_section['total_attachments']}")
                text_parts.append(f"总大小: {attachments_section['total_size_mb']} MB")
                text_parts.append("")
        
        return "\n".join(text_parts) 