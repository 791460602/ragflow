#!/usr/bin/env python3
"""
RAGFlow 文件夹上传独立脚本
不依赖SDK修改，直接调用API实现文件夹上传并保持目录结构
"""

import os
import requests
from requests_toolbelt.multipart.encoder import MultipartEncoder
from ragflow_sdk import RAGFlow

# 配置参数
API_KEY = "ragflow-M3NDJjZmEyNjYwZDExZjBhMTAwYjlkOD"  # 你的API密钥
BASE_URL = "http://localhost:9380"  # RAGFlow服务地址
LOCAL_FOLDER_PATH = r"/mnt/e/下载/讲义/02实战篇"  # 要上传的本地文件夹路径
DATASET_NAME = "讲义知识库"  # 目标知识库名称
PARENT_ID = ""  # 上传到的父目录ID，空字符串表示根目录


def upload_folder_preserve_structure(folder_path, api_key, base_url, parent_id=""):
    """
    上传文件夹并保持目录结构
    """
    parts = []
    if parent_id:
        parts.append(('parent_id', parent_id))

    # 遍历本地文件夹
    file_handles = []  # 用于最后关闭文件句柄
    try:
        for root, _, files in os.walk(folder_path):
            for filename in files:
                local_path = os.path.join(root, filename)
                # 计算文件相对于被上传文件夹的路径
                relative_path = os.path.relpath(local_path, folder_path).replace('\\', '/')
                
                print(f"准备上传: {relative_path}")
                
                # 关键：将相对路径作为 multipart 中的文件名
                file_handle = open(local_path, 'rb')
                file_handles.append(file_handle)
                parts.append(('file', (relative_path, file_handle, 'application/octet-stream')))

        if len(parts) <= (1 if parent_id else 0):
            print("文件夹为空，无需上传。")
            return {"code": 0, "data": []}

        encoder = MultipartEncoder(fields=parts)

        headers = {
            'Authorization': f'Bearer {api_key}',
            'Content-Type': encoder.content_type
        }

        # 发送请求
        response = requests.post(
            f"{base_url}/api/v1/file/upload",
            data=encoder,
            headers=headers
        )
        response.raise_for_status()
        
        result = response.json()
        if result.get("code") != 0:
            raise Exception(result.get("message", "Upload failed"))
            
        print(f"✅ 成功上传 {len(result.get('data', []))} 个文件")
        return result
        
    except requests.exceptions.RequestException as e:
        print(f"❌ 上传失败: {e}")
        if hasattr(e, 'response') and e.response:
            print(f"响应内容: {e.response.text}")
        raise
    finally:
        # 关闭所有文件句柄
        for file_handle in file_handles:
            file_handle.close()


def convert_files_to_dataset(file_ids, dataset_ids, api_key, base_url):
    """
    将文件转换为文档并关联到数据集
    """
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        "file_ids": file_ids,
        "kb_ids": dataset_ids
    }
    
    # 尝试不同的 API 路径
    api_paths = [
        f"{base_url}/api/v1/file2document/convert",   # SDK API 路径（支持 API Key）
        f"{base_url}/api/file2document/convert",      # 前端使用的路径（需要登录）
        f"{base_url}/v1/file2document/convert",       # 简化的路径
        f"{base_url}/file2document/convert"           # 最简路径
    ]
    
    last_error = None
    
    for api_path in api_paths:
        try:
            print(f"🔄 尝试 API 路径: {api_path}")
            response = requests.post(
                api_path,
                json=payload,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 404:
                print(f"   ❌ 404 - 路径不存在")
                continue
                
            response.raise_for_status()
            
            result = response.json()
            if result.get("code") != 0:
                raise Exception(result.get("message", "File to document conversion failed"))
                
            print(f"   ✅ 成功！使用路径: {api_path}")
            print(f"✅ 成功转换 {len(result.get('data', []))} 个文档到知识库")
            return result
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                print(f"   ❌ 404 - 路径不存在")
                continue
            else:
                print(f"   ❌ HTTP错误 {e.response.status_code}: {e}")
                last_error = e
        except Exception as e:
            print(f"   ❌ 错误: {str(e)}")
            last_error = e
    
    # 如果所有路径都失败了
    raise Exception(f"所有 API 路径都失败了。最后一个错误: {last_error}")


def main():
    try:
        # 第一步：初始化RAGFlow客户端（用于数据集操作）
        rag = RAGFlow(api_key=API_KEY, base_url=BASE_URL)
        print("✅ RAGFlow客户端初始化成功")
        
        # 第二步：获取或创建数据集
        try:
            dataset = rag.get_dataset(DATASET_NAME)
            print(f"✅ 找到已存在的数据集: {DATASET_NAME}")
        except Exception:
            print(f"📝 数据集 '{DATASET_NAME}' 不存在，正在创建...")
            dataset = rag.create_dataset(
                name=DATASET_NAME,
                description="通过文件夹上传创建的知识库",
                chunk_method="naive"
            )
            print(f"✅ 数据集创建成功: {DATASET_NAME}")
        
        # 第三步：检查本地文件夹是否存在
        if not os.path.exists(LOCAL_FOLDER_PATH):
            print(f"❌ 本地文件夹不存在: {LOCAL_FOLDER_PATH}")
            return
        
        print(f"📂 开始上传文件夹: {LOCAL_FOLDER_PATH}")
        print(f"🎯 目标数据集: {DATASET_NAME} (ID: {dataset.id})")
        
        # 第四步：上传文件夹并保持目录结构
        upload_result = upload_folder_preserve_structure(
            folder_path=LOCAL_FOLDER_PATH,
            api_key=API_KEY,
            base_url=BASE_URL,
            parent_id=PARENT_ID
        )
        
        # 第五步：获取上传的文件ID
        file_ids = [file_info["id"] for file_info in upload_result.get("data", [])]
        
        if not file_ids:
            print("❌ 没有文件被上传")
            return
        
        # 第六步：将文件转换为文档并关联到数据集
        convert_result = convert_files_to_dataset(
            file_ids=file_ids,
            dataset_ids=[dataset.id],
            api_key=API_KEY,
            base_url=BASE_URL
        )
        
        print("🎉 上传完成!")
        
        # 显示上传的文件信息
        upload_data = upload_result.get("data", [])
        if upload_data:
            print(f"📁 成功上传 {len(upload_data)} 个文件:")
            for file_info in upload_data[:5]:  # 只显示前5个
                print(f"  - {file_info.get('name', 'Unknown')} (ID: {file_info.get('id', 'Unknown')})")
            if len(upload_data) > 5:
                print(f"  ... 还有 {len(upload_data) - 5} 个文件")
        
        # 显示转换结果
        convert_data = convert_result.get("data", [])
        document_ids = []
        if convert_data:
            print(f"📚 成功转换 {len(convert_data)} 个文档到知识库")
            
            # 提取文档ID用于解析
            for item in convert_data:
                if "document_id" in item:
                    document_ids.append(item["document_id"])
        
        # 第七步：自动开始解析文档
        if document_ids:
            print(f"\n🔄 开始解析 {len(document_ids)} 个文档...")
            try:
                dataset.async_parse_documents(document_ids)
                print("✅ 文档解析已开始！")
                print("💡 解析是异步进行的，您可以在 RAGFlow 界面中查看解析进度")
                print("📋 解析完成后，文档将可用于检索和问答")
            except Exception as e:
                print(f"⚠️  解析启动失败: {str(e)}")
                print("💡 您可以稍后在 RAGFlow 界面中手动启动解析")
        
        print("\n🔗 文件已成功上传并关联到知识库，保持了原有的目录结构！")
        
    except Exception as e:
        print(f"❌ 操作失败: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    # 检查依赖
    try:
        import requests_toolbelt
        print("✅ 依赖检查通过")
    except ImportError:
        print("❌ 缺少依赖，请安装: pip install requests-toolbelt")
        exit(1)
    
    main()
