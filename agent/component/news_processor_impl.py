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
import asyncio
import logging
import json
import os
import re
import mimetypes
from abc import ABC
from datetime import datetime
from typing import List, Dict, Any, Optional
import pandas as pd
import requests
from urllib.parse import urljoin, urlparse
from agent.component.base import ComponentBase, ComponentParamBase
from agent.component.crawler import Crawler
from api.db.services.knowledgebase_service import KnowledgebaseService
from api.db.services.document_service import DocumentService
from api.db.services.file_service import FileService
from api.db import StatusEnum, FileType, FileSource
from api.utils import get_uuid
from rag.utils.storage_factory import STORAGE_IMPL


class NewsProcessorParam(ComponentParamBase):
    """
    定义新闻处理组件的参数
    """
    
    def __init__(self):
        super().__init__()
        self.kb_id = ""  # 知识库ID
        self.process_content = True  # 是否处理新闻内容
        self.max_content_length = 5000  # 最大内容长度
        self.save_to_kb = True  # 是否保存到知识库
        self.format_output = "markdown"  # 输出格式
        self.download_attachments = True  # 是否下载附件
        self.attachment_types = ["pdf", "doc", "docx", "ppt", "pptx"]  # 支持的附件类型
        self.max_attachment_size = 50 * 1024 * 1024  # 最大附件大小（50MB）
        self.attachment_timeout = 60  # 附件下载超时时间
    
    def check(self):
        self.check_empty(self.kb_id, "知识库ID")
        self.check_boolean(self.process_content, "是否处理新闻内容")
        self.check_positive_integer(self.max_content_length, "最大内容长度")
        self.check_boolean(self.save_to_kb, "是否保存到知识库")
        self.check_valid_value(self.format_output, "输出格式", ['markdown', 'json', 'text'])
        self.check_boolean(self.download_attachments, "是否下载附件")
        self.check_positive_integer(self.max_attachment_size, "最大附件大小")
        self.check_positive_integer(self.attachment_timeout, "附件下载超时时间")


class NewsProcessor(ComponentBase, ABC):
    component_name = "NewsProcessor"
    
    def _run(self, history, **kwargs):
        """执行新闻处理"""
        try:
            # 获取输入数据
            input_data = self.get_input()
            
            # 解析新闻数据
            news_list = self._parse_news_data(input_data)
            
            if not news_list:
                return NewsProcessor.be_output("没有找到新闻数据")
            
            # 处理新闻内容
            if self._param.process_content:
                processed_news = asyncio.run(self._process_news_content(news_list))
            else:
                processed_news = news_list
            
            # 保存到知识库
            if self._param.save_to_kb:
                self._save_news_to_kb(processed_news)
            
            # 格式化输出
            output = self._format_output(processed_news)
            
            return NewsProcessor.be_output(output)
            
        except Exception as e:
            logging.error(f"新闻处理失败: {str(e)}")
            return NewsProcessor.be_output(f"新闻处理失败: {str(e)}")
    
    def _parse_news_data(self, input_data):
        """解析新闻数据"""
        news_list = []
        
        if "content" in input_data:
            content = input_data["content"]
            
            if isinstance(content, list):
                # 直接是新闻列表
                news_list = content
            elif isinstance(content, str):
                # 尝试解析JSON
                try:
                    parsed = json.loads(content)
                    if isinstance(parsed, list):
                        news_list = parsed
                    elif isinstance(parsed, dict) and "content" in parsed:
                        # 可能是DataFrame格式
                        if isinstance(parsed["content"], list):
                            news_list = parsed["content"]
                except:
                    logging.warning("无法解析新闻数据格式")
            elif hasattr(content, 'to_dict'):
                # DataFrame格式
                df = content
                if isinstance(df, pd.DataFrame):
                    news_list = df.to_dict('records')
        
        return news_list
    
    async def _process_news_content(self, news_list: List[Dict[str, Any]]):
        """处理新闻内容"""
        processed_news = []
        
        for news in news_list:
            try:
                # 获取新闻详细内容
                if news.get("link") and not news.get("full_content"):
                    full_content = await self._fetch_news_content(news["link"])
                    news["full_content"] = full_content
                
                # 查找和处理附件
                if self._param.download_attachments and news.get("link"):
                    attachments = await self._find_and_download_attachments(news["link"])
                    news["attachments"] = attachments
                
                # 生成结构化内容
                structured_content = self._generate_structured_content(news)
                news["structured_content"] = structured_content
                
                processed_news.append(news)
                
            except Exception as e:
                logging.error(f"处理新闻失败: {str(e)}")
                continue
        
        return processed_news
    
    async def _fetch_news_content(self, url: str):
        """获取新闻详细内容"""
        try:
            # 使用现有的Crawler组件获取内容
            crawler = Crawler()
            crawler._param.extract_type = "content"
            
            # 模拟输入
            mock_input = {"content": [url]}
            crawler._input = mock_input
            
            result = crawler._run([])
            
            if isinstance(result, pd.DataFrame) and not result.empty:
                return result.iloc[0]["content"]
            elif isinstance(result, str):
                return result
            
            return ""
            
        except Exception as e:
            logging.error(f"获取新闻内容失败: {str(e)}")
            return ""
    
    async def _find_and_download_attachments(self, news_url: str) -> List[Dict[str, Any]]:
        """查找并下载附件"""
        attachments = []
        
        try:
            # 获取新闻页面内容
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            }
            
            response = requests.get(news_url, headers=headers, timeout=self._param.attachment_timeout)
            response.raise_for_status()
            
            # 查找附件链接
            attachment_links = self._find_attachment_links(response.text, news_url)
            
            # 下载附件
            for link_info in attachment_links:
                try:
                    attachment = await self._download_attachment(link_info)
                    if attachment:
                        attachments.append(attachment)
                except Exception as e:
                    logging.error(f"下载附件失败 {link_info['url']}: {str(e)}")
                    continue
            
            logging.info(f"从 {news_url} 找到 {len(attachments)} 个附件")
            
        except Exception as e:
            logging.error(f"查找附件失败 {news_url}: {str(e)}")
        
        return attachments
    
    def _find_attachment_links(self, html_content: str, base_url: str) -> List[Dict[str, Any]]:
        """从HTML内容中查找附件链接"""
        attachment_links = []
        
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # 查找所有链接
            links = soup.find_all('a', href=True)
            
            for link in links:
                href = link.get('href', '')
                link_text = link.get_text(strip=True)
                
                # 构建完整URL
                full_url = urljoin(base_url, href)
                
                # 检查是否是附件链接
                if self._is_attachment_link(full_url, link_text):
                    attachment_links.append({
                        'url': full_url,
                        'text': link_text,
                        'filename': self._extract_filename(full_url, link_text)
                    })
            
            # 去重
            seen_urls = set()
            unique_links = []
            for link in attachment_links:
                if link['url'] not in seen_urls:
                    seen_urls.add(link['url'])
                    unique_links.append(link)
            
            return unique_links
            
        except Exception as e:
            logging.error(f"解析附件链接失败: {str(e)}")
            return []
    
    def _is_attachment_link(self, url: str, link_text: str) -> bool:
        """判断是否是附件链接"""
        # 检查文件扩展名
        parsed_url = urlparse(url)
        path = parsed_url.path.lower()
        
        # 检查URL中的文件扩展名
        for ext in self._param.attachment_types:
            if path.endswith(f'.{ext}'):
                return True
        
        # 检查链接文本中的关键词
        attachment_keywords = ['pdf', '附件', '下载', '文档', '报告', '文件']
        link_text_lower = link_text.lower()
        
        for keyword in attachment_keywords:
            if keyword in link_text_lower:
                return True
        
        # 检查URL中的关键词
        url_lower = url.lower()
        for keyword in attachment_keywords:
            if keyword in url_lower:
                return True
        
        return False
    
    def _extract_filename(self, url: str, link_text: str) -> str:
        """提取文件名"""
        # 从URL中提取文件名
        parsed_url = urlparse(url)
        path = parsed_url.path
        
        if path and '/' in path:
            filename = path.split('/')[-1]
            if filename and '.' in filename:
                return filename
        
        # 从链接文本中提取
        if link_text and len(link_text) < 100:  # 避免过长的文本
            # 清理文本，移除特殊字符
            clean_text = re.sub(r'[<>:"/\\|?*]', '', link_text)
            if clean_text:
                return clean_text
        
        # 生成默认文件名
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f"attachment_{timestamp}"
    
    async def _download_attachment(self, link_info: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """下载附件"""
        try:
            url = link_info['url']
            filename = link_info['filename']
            
            logging.info(f"开始下载附件: {filename} from {url}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': '*/*',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            }
            
            # 下载文件
            response = requests.get(
                url, 
                headers=headers, 
                timeout=self._param.attachment_timeout,
                stream=True
            )
            response.raise_for_status()
            
            # 检查文件大小
            content_length = response.headers.get('content-length')
            if content_length and int(content_length) > self._param.max_attachment_size:
                logging.warning(f"附件过大，跳过: {filename} ({content_length} bytes)")
                return None
            
            # 检查Content-Type
            content_type = response.headers.get('content-type', '')
            if not self._is_valid_attachment_type(content_type):
                logging.warning(f"不支持的附件类型: {content_type} for {filename}")
                return None
            
            # 读取文件内容
            content = b''
            for chunk in response.iter_content(chunk_size=8192):
                content += chunk
                if len(content) > self._param.max_attachment_size:
                    logging.warning(f"附件过大，停止下载: {filename}")
                    return None
            
            # 确定文件类型
            file_type = self._determine_file_type(filename, content_type)
            
            return {
                'filename': filename,
                'url': url,
                'content': content,
                'size': len(content),
                'content_type': content_type,
                'file_type': file_type,
                'download_time': datetime.now().isoformat()
            }
            
        except Exception as e:
            logging.error(f"下载附件失败 {url}: {str(e)}")
            return None
    
    def _is_valid_attachment_type(self, content_type: str) -> bool:
        """检查是否是有效的附件类型"""
        if not content_type:
            return True  # 如果没有Content-Type，让文件扩展名判断
        
        content_type_lower = content_type.lower()
        
        # 检查MIME类型
        valid_mime_types = [
            'application/pdf',
            'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            'application/vnd.ms-powerpoint',
            'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            'application/octet-stream',  # 通用二进制文件
        ]
        
        for mime_type in valid_mime_types:
            if mime_type in content_type_lower:
                return True
        
        return False
    
    def _determine_file_type(self, filename: str, content_type: str) -> str:
        """确定文件类型"""
        # 从文件名扩展名判断
        if filename.lower().endswith('.pdf'):
            return FileType.PDF.value
        elif filename.lower().endswith(('.doc', '.docx')):
            return FileType.WORD.value
        elif filename.lower().endswith(('.ppt', '.pptx')):
            return FileType.PRESENTATION.value
        elif filename.lower().endswith(('.xls', '.xlsx')):
            return FileType.EXCEL.value
        else:
            # 从Content-Type判断
            content_type_lower = content_type.lower()
            if 'pdf' in content_type_lower:
                return FileType.PDF.value
            elif 'word' in content_type_lower or 'document' in content_type_lower:
                return FileType.WORD.value
            elif 'powerpoint' in content_type_lower or 'presentation' in content_type_lower:
                return FileType.PRESENTATION.value
            elif 'excel' in content_type_lower or 'spreadsheet' in content_type_lower:
                return FileType.EXCEL.value
            else:
                return FileType.OTHER.value
    
    def _generate_structured_content(self, news: Dict[str, Any]):
        """生成结构化的新闻内容"""
        content_parts = []
        
        # 标题
        if news.get("title"):
            content_parts.append(f"# {news['title']}")
        
        # 元信息
        meta_info = []
        if news.get("source"):
            meta_info.append(f"来源: {news['source']}")
        if news.get("time"):
            meta_info.append(f"时间: {news['time']}")
        if news.get("link"):
            meta_info.append(f"链接: {news['link']}")
        
        if meta_info:
            content_parts.append("**元信息:** " + " | ".join(meta_info))
        
        # 摘要
        if news.get("summary"):
            content_parts.append(f"\n**摘要:** {news['summary']}")
        
        # 详细内容
        if news.get("full_content"):
            # 截断内容
            full_content = news["full_content"]
            if len(full_content) > self._param.max_content_length:
                full_content = full_content[:self._param.max_content_length] + "..."
            content_parts.append(f"\n**详细内容:**\n{full_content}")
        
        # 附件信息
        if news.get("attachments"):
            content_parts.append(f"\n**附件:**")
            for i, attachment in enumerate(news["attachments"], 1):
                content_parts.append(f"{i}. {attachment['filename']} ({attachment['size']} bytes)")
        
        return "\n\n".join(content_parts)
    
    def _save_news_to_kb(self, news_list: List[Dict[str, Any]]):
        """保存新闻到知识库"""
        try:
            # 验证知识库
            e, kb = KnowledgebaseService.get_by_id(self._param.kb_id)
            if not e:
                raise Exception(f"知识库不存在: {self._param.kb_id}")
            
            # 获取根文件夹
            root_folder = FileService.get_root_folder(self._canvas.get_tenant_id())
            kb_root_folder = FileService.get_kb_folder(self._canvas.get_tenant_id())
            kb_folder = FileService.new_a_file_from_kb(
                kb.tenant_id, 
                kb.name, 
                kb_root_folder["id"]
            )
            
            # 保存每条新闻
            for news in news_list:
                self._save_single_news(news, kb, kb_folder)
                
        except Exception as e:
            logging.error(f"保存新闻到知识库失败: {str(e)}")
            raise
    
    def _save_single_news(self, news: Dict[str, Any], kb, kb_folder):
        """保存单条新闻"""
        try:
            # 生成文件名
            title = news.get("title", "未知新闻")
            safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).rstrip()
            filename = f"{safe_title[:50]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            
            # 生成内容
            content = news.get("structured_content", "")
            if not content:
                content = f"标题: {news.get('title', '')}\n"
                content += f"来源: {news.get('source', '')}\n"
                content += f"时间: {news.get('time', '')}\n"
                content += f"链接: {news.get('link', '')}\n"
                content += f"摘要: {news.get('summary', '')}\n"
                content += f"详细内容: {news.get('full_content', '')}"
            
            # 转换为字节
            content_bytes = content.encode('utf-8')
            
            # 保存到存储
            location = filename
            while STORAGE_IMPL.obj_exist(kb.id, location):
                location += "_"
            STORAGE_IMPL.put(kb.id, location, content_bytes)
            
            # 创建文档记录
            doc = {
                "id": get_uuid(),
                "kb_id": kb.id,
                "parser_id": kb.parser_id,
                "parser_config": kb.parser_config,
                "created_by": self._canvas.get_tenant_id(),
                "type": FileType.TEXT.value,
                "name": filename,
                "location": location,
                "size": len(content_bytes),
                "thumbnail": "",
            }
            
            DocumentService.insert(doc)
            FileService.add_file_from_kb(doc, kb_folder["id"], kb.tenant_id)
            
            logging.info(f"成功保存新闻: {filename}")
            
            # 保存附件
            if news.get("attachments"):
                self._save_attachments(news["attachments"], kb, kb_folder, news.get("title", "未知新闻"))
            
        except Exception as e:
            logging.error(f"保存单条新闻失败: {str(e)}")
    
    def _save_attachments(self, attachments: List[Dict[str, Any]], kb, kb_folder, news_title: str):
        """保存附件"""
        for attachment in attachments:
            try:
                filename = attachment['filename']
                content = attachment['content']
                file_type = attachment['file_type']
                
                # 生成唯一文件名
                safe_filename = "".join(c for c in filename if c.isalnum() or c in (' ', '-', '_', '.')).rstrip()
                unique_filename = f"{news_title[:30]}_{safe_filename}"
                
                # 保存到存储
                location = unique_filename
                while STORAGE_IMPL.obj_exist(kb.id, location):
                    location += "_"
                STORAGE_IMPL.put(kb.id, location, content)
                
                # 创建文档记录
                doc = {
                    "id": get_uuid(),
                    "kb_id": kb.id,
                    "parser_id": self._get_parser_id_for_file_type(file_type),
                    "parser_config": kb.parser_config,
                    "created_by": self._canvas.get_tenant_id(),
                    "type": file_type,
                    "name": unique_filename,
                    "location": location,
                    "size": len(content),
                    "thumbnail": "",
                }
                
                DocumentService.insert(doc)
                FileService.add_file_from_kb(doc, kb_folder["id"], kb.tenant_id)
                
                logging.info(f"成功保存附件: {unique_filename}")
                
            except Exception as e:
                logging.error(f"保存附件失败 {filename}: {str(e)}")
                continue
    
    def _get_parser_id_for_file_type(self, file_type: str) -> str:
        """根据文件类型获取解析器ID"""
        from api.db import ParserType
        
        if file_type == FileType.PDF.value:
            return ParserType.PDF.value
        elif file_type == FileType.WORD.value:
            return ParserType.WORD.value
        elif file_type == FileType.PRESENTATION.value:
            return ParserType.PRESENTATION.value
        elif file_type == FileType.EXCEL.value:
            return ParserType.EXCEL.value
        else:
            return ParserType.NAIVE.value
    
    def _format_output(self, news_list: List[Dict[str, Any]]):
        """格式化输出"""
        if self._param.format_output == "markdown":
            return self._format_markdown(news_list)
        elif self._param.format_output == "json":
            return json.dumps(news_list, ensure_ascii=False, indent=2)
        else:  # text
            return self._format_text(news_list)
    
    def _format_markdown(self, news_list: List[Dict[str, Any]]):
        """格式化为Markdown"""
        markdown_parts = []
        
        for i, news in enumerate(news_list, 1):
            markdown_parts.append(f"## {i}. {news.get('title', '未知标题')}")
            
            if news.get("source"):
                markdown_parts.append(f"**来源:** {news['source']}")
            if news.get("time"):
                markdown_parts.append(f"**时间:** {news['time']}")
            if news.get("link"):
                markdown_parts.append(f"**链接:** [{news['link']}]({news['link']})")
            if news.get("summary"):
                markdown_parts.append(f"**摘要:** {news['summary']}")
            
            # 添加附件信息
            if news.get("attachments"):
                markdown_parts.append(f"**附件:**")
                for j, attachment in enumerate(news["attachments"], 1):
                    markdown_parts.append(f"  {j}. {attachment['filename']} ({attachment['size']} bytes)")
            
            markdown_parts.append("")  # 空行分隔
        
        return "\n".join(markdown_parts)
    
    def _format_text(self, news_list: List[Dict[str, Any]]):
        """格式化为纯文本"""
        text_parts = []
        
        for i, news in enumerate(news_list, 1):
            text_parts.append(f"{i}. {news.get('title', '未知标题')}")
            
            if news.get("source"):
                text_parts.append(f"   来源: {news['source']}")
            if news.get("time"):
                text_parts.append(f"   时间: {news['time']}")
            if news.get("link"):
                text_parts.append(f"   链接: {news['link']}")
            if news.get("summary"):
                text_parts.append(f"   摘要: {news['summary']}")
            
            # 添加附件信息
            if news.get("attachments"):
                text_parts.append(f"   附件:")
                for j, attachment in enumerate(news["attachments"], 1):
                    text_parts.append(f"     {j}. {attachment['filename']} ({attachment['size']} bytes)")
            
            text_parts.append("")  # 空行分隔
        
        return "\n".join(text_parts) 