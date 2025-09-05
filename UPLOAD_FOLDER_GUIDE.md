# RAGFlow 文件夹上传功能使用指南

## 概述

新增的功能允许您将本地文件夹上传到 RAGFlow 并保持原有的目录结构，同时自动将文件关联到指定的知识库。

## 功能特点

- ✅ **保持目录结构**: 完整保留本地文件夹的层级关系
- ✅ **批量上传**: 一次性上传整个文件夹及其子目录
- ✅ **自动关联**: 上传后自动转换为文档并关联到指定知识库
- ✅ **错误处理**: 完善的异常处理和资源清理

## 使用方法

### 方法1: 使用 RAGFlow 客户端方法

```python
from ragflow_sdk import RAGFlow

# 初始化客户端
rag = RAGFlow(api_key="your_api_key", base_url="http://localhost:9380")

# 获取或创建数据集
dataset = rag.get_dataset("知识库名称")  # 或 rag.create_dataset(...)

# 上传文件夹到知识库
result = rag.upload_folder_to_dataset(
    folder_path="/path/to/your/folder",
    dataset_id=dataset.id,
    parent_id=""  # 空字符串表示上传到根目录
)
```

### 方法2: 使用 DataSet 对象方法（推荐）

```python
from ragflow_sdk import RAGFlow

# 初始化客户端
rag = RAGFlow(api_key="your_api_key", base_url="http://localhost:9380")

# 获取数据集
dataset = rag.get_dataset("知识库名称")

# 直接从数据集对象上传文件夹
result = dataset.upload_folder(
    folder_path="/path/to/your/folder",
    parent_id=""  # 可选，指定上传到的父目录
)
```

## 参数说明

| 参数 | 类型 | 说明 | 必填 |
|------|------|------|------|
| `folder_path` | str | 本地文件夹的绝对路径 | ✅ |
| `dataset_id` | str | 目标知识库的ID | ✅ |
| `parent_id` | str | 在RAGFlow中的父目录ID，空字符串表示根目录 | ❌ |

## 返回值

```python
{
    "message": "Successfully uploaded folder and linked to dataset",
    "upload_result": {
        "code": 0,
        "data": [
            {
                "id": "file_id_1",
                "name": "subfolder/document.pdf",
                "size": 1024,
                "type": "document"
            },
            # ... 更多文件信息
        ]
    },
    "convert_result": {
        "code": 0,
        "data": [
            {
                "id": "file2doc_id_1",
                "file_id": "file_id_1",
                "document_id": "doc_id_1"
            },
            # ... 更多转换信息
        ]
    }
}
```

## 完整示例

```python
import os
from ragflow_sdk import RAGFlow

def upload_folder_example():
    # 配置
    API_KEY = "your_api_key"
    BASE_URL = "http://localhost:9380"
    LOCAL_FOLDER = "/path/to/your/documents"
    DATASET_NAME = "我的知识库"
    
    try:
        # 初始化客户端
        rag = RAGFlow(api_key=API_KEY, base_url=BASE_URL)
        
        # 获取或创建数据集
        try:
            dataset = rag.get_dataset(DATASET_NAME)
            print(f"使用已存在的数据集: {DATASET_NAME}")
        except Exception:
            dataset = rag.create_dataset(
                name=DATASET_NAME,
                description="通过文件夹上传创建的知识库"
            )
            print(f"创建新数据集: {DATASET_NAME}")
        
        # 检查文件夹是否存在
        if not os.path.exists(LOCAL_FOLDER):
            print(f"错误: 文件夹不存在 {LOCAL_FOLDER}")
            return
        
        # 上传文件夹
        print(f"开始上传文件夹: {LOCAL_FOLDER}")
        result = dataset.upload_folder(LOCAL_FOLDER)
        
        # 显示结果
        upload_data = result.get('upload_result', {}).get('data', [])
        print(f"成功上传 {len(upload_data)} 个文件")
        
        convert_data = result.get('convert_result', {}).get('data', [])
        print(f"成功转换 {len(convert_data)} 个文档到知识库")
        
        print("上传完成！文件已保持原有目录结构并关联到知识库。")
        
    except Exception as e:
        print(f"上传失败: {str(e)}")

if __name__ == "__main__":
    upload_folder_example()
```

## 注意事项

1. **权限要求**: 确保您的 API 密钥有文件上传和知识库操作权限
2. **文件大小**: 单个文件不能超过系统设置的大小限制
3. **支持格式**: 支持 RAGFlow 能处理的所有文档格式（PDF、Word、Markdown等）
4. **网络稳定**: 大文件夹上传需要稳定的网络连接
5. **资源清理**: 代码已包含文件句柄的自动清理机制

## 错误处理

常见错误及解决方案：

- **导入错误**: 确保已安装 `requests-toolbelt` 依赖
- **路径错误**: 使用绝对路径，确保文件夹存在
- **权限错误**: 检查 API 密钥和数据集访问权限
- **网络错误**: 检查 RAGFlow 服务是否正常运行

## 依赖要求

```bash
pip install requests-toolbelt
```

这个功能结合了 RAGFlow 的文件管理系统和知识库系统，为您提供了一个完整的文件夹上传解决方案。
