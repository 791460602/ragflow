#!/usr/bin/env python3
"""
RAGFlow 文件夹上传示例
上传本地文件夹到知识库并保持目录结构
"""

import os
from ragflow_sdk import RAGFlow

# 配置参数
API_KEY = "ragflow-M3NDJjZmEyNjYwZDExZjBhMTAwYjlkOD"  # 你的API密钥
BASE_URL = "http://localhost:9380"  # RAGFlow服务地址
LOCAL_FOLDER_PATH = r"/mnt/e/下载/讲义/02实战篇"  # 要上传的本地文件夹路径
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
        
        # 方法1: 使用RAGFlow客户端的方法
        result = rag.upload_folder_to_dataset(
            folder_path=LOCAL_FOLDER_PATH,
            dataset_id=dataset.id,
            parent_id=PARENT_ID
        )
        
        # 方法2: 使用DataSet对象的便捷方法（推荐）
        # result = dataset.upload_folder(LOCAL_FOLDER_PATH, PARENT_ID)
        
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
        
        print("\n🔗 文件已成功上传并关联到知识库，保持了原有的目录结构！")
        
    except Exception as e:
        print(f"❌ 上传失败: {str(e)}")
        import traceback
        traceback.print_exc()


def method_comparison():
    """
    演示两种上传方法的区别
    """
    print("\n" + "="*60)
    print("📖 方法对比说明:")
    print("="*60)
    
    print("""
    方法1: 使用 upload_folder_preserve_structure (保持目录结构)
    - ✅ 保持完整的文件夹层级结构
    - ✅ 支持嵌套目录
    - ✅ 文件路径信息完整保留
    - 🎯 适合: 需要保持原始文档组织结构的场景
    
    方法2: 使用 dataset.upload_documents (平铺结构) 
    - ✅ 简单快速
    - ❌ 不保持目录结构，所有文件平铺
    - ❌ 仅保留文件名，丢失路径信息
    - 🎯 适合: 只关心文档内容，不关心文件组织的场景
    
    🏆 推荐使用方法1，特别是当您需要保持原始文档的组织结构时。
    """)


if __name__ == "__main__":
    main()
    method_comparison()
