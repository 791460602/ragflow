#!/usr/bin/env python3
"""
RAGFlow 文件夹上传并自动解析示例
上传本地文件夹到知识库，保持目录结构，并自动开始解析
"""

import os
from ragflow_sdk import RAGFlow

# 配置参数
API_KEY = "ragflow-M3NDJjZmEyNjYwZDExZjBhMTAwYjlkOD"  # 你的API密钥
BASE_URL = "http://localhost:9380"  # RAGFlow服务地址
LOCAL_FOLDER_PATH = r"/mnt/e/下载/讲义/01基础篇"  # 要上传的本地文件夹路径
DATASET_NAME = "讲义知识库"  # 目标知识库名称
PARENT_ID = ""  # 上传到的父目录ID，空字符串表示根目录


def main():
    try:
        # 初始化RAGFlow客户端
        rag = RAGFlow(api_key=API_KEY, base_url=BASE_URL)
        print("✅ RAGFlow客户端初始化成功")
        
        # 获取或创建数据集
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
        
        # 检查本地文件夹是否存在
        if not os.path.exists(LOCAL_FOLDER_PATH):
            print(f"❌ 本地文件夹不存在: {LOCAL_FOLDER_PATH}")
            return
        
        print(f"📂 开始上传文件夹: {LOCAL_FOLDER_PATH}")
        print(f"🎯 目标数据集: {DATASET_NAME} (ID: {dataset.id})")
        
        # 上传文件夹并自动开始解析
        print("🔄 上传并自动解析...")
        result = dataset.upload_folder(LOCAL_FOLDER_PATH, PARENT_ID, auto_parse=True)
        
        print("🎉 上传完成!")
        print(f"📊 上传结果: {result.get('message', '成功')}")
        
        # 显示上传的文件信息
        upload_data = result.get('upload_result', {}).get('data', [])
        if upload_data:
            print(f"📁 成功上传 {len(upload_data)} 个文件:")
            for file_info in upload_data[:5]:  # 只显示前5个
                print(f"  - {file_info.get('name', 'Unknown')} (ID: {file_info.get('id', 'Unknown')})")
            if len(upload_data) > 5:
                print(f"  ... 还有 {len(upload_data) - 5} 个文件")
        
        # 显示转换结果
        convert_data = result.get('convert_result', {}).get('data', [])
        if convert_data:
            print(f"📚 成功转换 {len(convert_data)} 个文档到知识库")
        
        # 显示解析结果
        parse_result = result.get('parse_result')
        if parse_result:
            if parse_result.get('status') == 'started':
                print(f"✅ 文档解析已开始！")
                print(f"📊 解析文档数量: {parse_result.get('document_count', 0)}")
                print("💡 解析是异步进行的，您可以在 RAGFlow 界面中查看解析进度")
                print("📋 解析完成后，文档将可用于检索和问答")
            else:
                print(f"⚠️  解析启动失败: {parse_result.get('error', '未知错误')}")
                print("💡 您可以稍后在 RAGFlow 界面中手动启动解析")
        
        print("\n🔗 文件已成功上传并关联到知识库，保持了原有的目录结构！")
        print("🚀 文档解析正在后台进行中...")
        
    except Exception as e:
        print(f"❌ 上传失败: {str(e)}")
        import traceback
        traceback.print_exc()


def demo_methods():
    """
    演示不同的上传和解析方法
    """
    print("\n" + "="*60)
    print("📖 上传和解析方法说明:")
    print("="*60)
    
    print("""
    方法1: 保持目录结构 + 自动解析
    result = dataset.upload_folder(folder_path, parent_id, auto_parse=True)
    - ✅ 保持完整的文件夹层级结构
    - ✅ 自动开始文档解析
    - ✅ 完整的权限控制
    - 🎯 适合: 需要完整文档管理和自动化处理的场景
    
    方法2: 简单上传 + 自动解析
    documents = dataset.upload_folder_direct(folder_path, auto_parse=True)
    - ✅ 简单快速
    - ✅ 自动开始文档解析
    - ✅ 文件名中保留路径信息
    - 🎯 适合: 快速导入和处理文档的场景
    
    方法3: 手动控制解析
    result = dataset.upload_folder(folder_path)  # auto_parse=False (默认)
    # 稍后手动开始解析
    dataset.async_parse_documents(document_ids)
    - ✅ 完全控制解析时机
    - ✅ 可以批量处理多个上传后再解析
    - 🎯 适合: 需要精确控制解析流程的场景
    
    💡 解析说明:
    - 解析是异步进行的，不会阻塞程序执行
    - 解析进度可以在 RAGFlow Web 界面中查看
    - 解析完成后，文档才能用于检索和问答
    - 大文件解析可能需要较长时间
    """)


if __name__ == "__main__":
    main()
    demo_methods()
