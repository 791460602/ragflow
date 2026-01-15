# -*- coding: utf-8 -*-
"""
附件下载器模块
"""

import os
import re
from datetime import datetime
from typing import List
from urllib.parse import urljoin, urlparse

import aiofiles
import aiohttp
from bs4 import BeautifulSoup

from common.misc_utils import get_uuid


class AttachmentDownloader:
    """检测和下载政策附件"""

    # 支持的附件格式
    ATTACHMENT_EXTENSIONS = [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".zip", ".rar"]

    # 附件链接关键词
    ATTACHMENT_LINK_KEYWORDS = ["附件", "下载", "文件", "政策", "原文", "全文"]

    def __init__(self):
        pass

    async def find_attachments(self, html: str, base_url: str) -> List[dict]:
        """从HTML中查找附件链接

        返回: [
            {
                'url': str,
                'filename': str,
                'extension': str,
                'link_text': str
            }
        ]
        """
        if not html:
            return []

        try:
            soup = BeautifulSoup(html, "html.parser")
            attachments = []

            # 查找所有链接
            for link in soup.find_all("a", href=True):
                href = link.get("href", "")
                link_text = link.get_text(strip=True)

                if not href:
                    continue

                # 转换为绝对URL
                absolute_url = urljoin(base_url, href)

                # 检查是否为附件链接
                is_attachment = False
                extension = None

                # 方法1: 检查URL扩展名
                for ext in self.ATTACHMENT_EXTENSIONS:
                    if absolute_url.lower().endswith(ext):
                        is_attachment = True
                        extension = ext
                        break

                # 方法2: 检查链接文本
                if not is_attachment:
                    for keyword in self.ATTACHMENT_LINK_KEYWORDS:
                        if keyword in link_text:
                            # 进一步检查URL中是否包含文件扩展名
                            for ext in self.ATTACHMENT_EXTENSIONS:
                                if ext in absolute_url.lower():
                                    is_attachment = True
                                    extension = ext
                                    break
                            if is_attachment:
                                break

                if is_attachment:
                    # 生成文件名
                    filename = self._extract_filename(absolute_url, link_text, extension)

                    attachments.append({"url": absolute_url, "filename": filename, "extension": extension, "link_text": link_text})

            return attachments

        except Exception as e:
            print(f"[AttachmentDownloader] 查找附件时出错: {e}")
            return []

    def _extract_filename(self, url: str, link_text: str, extension: str) -> str:
        """从URL或链接文本中提取文件名"""
        # 尝试从URL中提取文件名
        try:
            parsed_url = urlparse(url)
            path = parsed_url.path
            if path:
                filename = os.path.basename(path)
                if filename and extension in filename:
                    return filename
        except Exception:
            pass

        # 使用链接文本作为文件名
        if link_text:
            safe_name = re.sub(r'[\\/*?:"<>|]', "", link_text)
            safe_name = re.sub(r"\s+", "_", safe_name)
            safe_name = safe_name[:50]  # 限制长度
            if extension:
                return f"{safe_name}{extension}"
            return safe_name

        # 生成默认文件名
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        return f"attachment_{timestamp}{extension or ''}"

    async def download_attachment(self, url: str, save_dir: str, filename: str = None) -> dict:
        """下载附件到本地

        返回: {
            'success': bool,
            'filename': str,
            'filepath': str,
            'size': int,
            'url': str,
            'error': str or None
        }
        """
        try:
            # 确保保存目录存在
            os.makedirs(save_dir, exist_ok=True)

            # 如果未指定文件名，从URL中提取
            if not filename:
                filename = os.path.basename(urlparse(url).path) or f"attachment_{get_uuid()[:8]}"

            filepath = os.path.join(save_dir, filename)

            # 下载文件
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=25)) as response:  # 25秒超时（大规模爬取优化）
                    if response.status == 200:
                        content = await response.read()

                        # 保存文件
                        async with aiofiles.open(filepath, "wb") as f:
                            await f.write(content)

                        file_size = len(content)
                        print(f"[AttachmentDownloader] 成功下载附件: {filename} ({file_size} bytes)")

                        return {"success": True, "filename": filename, "filepath": filepath, "size": file_size, "url": url, "error": None}
                    else:
                        error_msg = f"HTTP {response.status}"
                        print(f"[AttachmentDownloader] 下载失败: {url} ({error_msg})")
                        return {"success": False, "filename": filename, "filepath": None, "size": 0, "url": url, "error": error_msg}

        except Exception as e:
            print(f"[AttachmentDownloader] 下载附件时出错: {url} - {e}")
            return {"success": False, "filename": filename, "filepath": None, "size": 0, "url": url, "error": str(e)}
