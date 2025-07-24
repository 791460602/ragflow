# RAGFlow SDK 增强功能：文件夹上传与自动解析

## 功能概述

我们成功为 RAGFlow SDK 添加了增强的文件夹上传功能，现在支持：

1. **保持目录结构上传** - 完整保留原始文件夹的层级结构
2. **自动文档解析** - 上传完成后立即开始解析文档
3. **灵活的上传选项** - 支持多种上传和解析组合

## 核心功能

### 1. 带自动解析的文件夹上传

```python
from ragflow_sdk import RAGFlow

# 初始化客户端
rag = RAGFlow(api_key="your-api-key", base_url="http://localhost:9380")

# 获取数据集
dataset = rag.get_dataset("知识库名称")

# 上传文件夹并自动开始解析
result = dataset.upload_folder(
    folder_path="/path/to/your/folder",
    parent_id="",  # 上传到根目录
    auto_parse=True  # 自动开始解析
)
```

### 2. 简化的直接上传方法

```python
# 直接上传文件夹到数据集（文件名包含路径信息）
documents = dataset.upload_folder_direct(
    folder_path="/path/to/your/folder",
    auto_parse=True
)
```

### 3. 手动控制解析时机

```python
# 仅上传，不自动解析
result = dataset.upload_folder(folder_path, parent_id)

# 稍后手动开始解析（如果需要）
document_ids = [doc['id'] for doc in result['convert_result']['data']]
parse_result = dataset.async_parse_documents(document_ids)
```

## 实现细节

### 文件结构

我们修改了以下核心文件：

1. **`sdk/python/ragflow_sdk/ragflow.py`**
   - 添加了 `upload_folder_to_dataset` 方法
   - 实现完整的上传→转换→解析工作流程

2. **`sdk/python/ragflow_sdk/modules/dataset.py`**
   - 增强了 `upload_folder` 和 `upload_folder_direct` 方法
   - 添加了 `auto_parse` 参数支持

3. **`api/db/services/file_service.py`**
   - 修复了多级目录创建的权限问题
   - 添加了 `create_folder_with_tenant` 方法

### 核心工作流程

1. **文件上传阶段**
   ```
   本地文件夹 → API上传 → 服务器文件系统
   - 保持目录结构
   - 设置正确的文件权限
   ```

2. **文档转换阶段**
   ```
   服务器文件 → 知识库文档
   - 链接文件到指定知识库
   - 创建文档记录
   ```

3. **自动解析阶段**（可选）
   ```
   知识库文档 → 解析处理
   - 异步启动解析任务
   - 生成可检索的内容块
   ```

## 使用示例

### 完整示例：上传讲义文件夹

```python
#!/usr/bin/env python3
import os
from ragflow_sdk import RAGFlow

# 配置
API_KEY = "your-api-key"
BASE_URL = "http://localhost:9380"
FOLDER_PATH = r"/path/to/your/documents"
DATASET_NAME = "我的知识库"

def main():
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
    
    # 上传文件夹并自动解析
    print("开始上传文件夹...")
    result = dataset.upload_folder(FOLDER_PATH, "", auto_parse=True)
    
    # 处理结果
    print("上传完成！")
    
    # 显示上传的文件
    upload_data = result.get('upload_result', {}).get('data', [])
    print(f"成功上传 {len(upload_data)} 个文件")
    
    # 显示解析状态
    parse_result = result.get('parse_result')
    if parse_result and parse_result.get('status') == 'started':
        print("文档解析已开始，请在 RAGFlow 界面查看进度")
    
if __name__ == "__main__":
    main()
```

### 快速测试示例

```python
# 简单测试
from ragflow_sdk import RAGFlow

rag = RAGFlow(api_key="your-key", base_url="http://localhost:9380")
dataset = rag.get_dataset("测试数据集")

# 上传当前目录的文档文件并自动解析
documents = dataset.upload_folder_direct(".", auto_parse=True)
print(f"上传了 {len(documents)} 个文档并开始解析")
```

## 参数说明

### `upload_folder` 方法参数

- **`folder_path`** (str): 本地文件夹路径
- **`parent_id`** (str): 上传到的父目录ID，空字符串表示根目录
- **`auto_parse`** (bool): 是否自动开始解析，默认为 `False`

### `upload_folder_direct` 方法参数

- **`folder_path`** (str): 本地文件夹路径
- **`auto_parse`** (bool): 是否自动开始解析，默认为 `False`

### 返回值结构

```python
{
    'upload_result': {
        'data': [  # 上传的文件列表
            {'id': 'file_id', 'name': 'filename', ...}
        ]
    },
    'convert_result': {
        'data': [  # 转换的文档列表
            {'id': 'doc_id', 'name': 'docname', ...}
        ]
    },
    'parse_result': {  # 仅当 auto_parse=True 时存在
        'status': 'started',  # 解析状态
        'document_count': 5,  # 解析的文档数量
        'error': None         # 错误信息（如果有）
    }
}
```

## 错误处理

### 常见错误和解决方案

1. **文件夹不存在**
   ```python
   if not os.path.exists(folder_path):
       print(f"错误：文件夹 {folder_path} 不存在")
       return
   ```

2. **API认证失败**
   ```python
   try:
       rag = RAGFlow(api_key=API_KEY, base_url=BASE_URL)
   except Exception as e:
       print(f"认证失败：{e}")
   ```

3. **数据集不存在**
   ```python
   try:
       dataset = rag.get_dataset(dataset_name)
   except Exception:
       dataset = rag.create_dataset(name=dataset_name)
   ```

## 最佳实践

1. **批量上传大文件夹**
   - 考虑分批处理避免超时
   - 使用 `auto_parse=False` 先上传，再批量解析

2. **解析监控**
   - 解析是异步的，在 RAGFlow Web 界面查看进度
   - 大文件解析可能需要较长时间

3. **错误恢复**
   - 上传失败时可以重试
   - 部分文件失败不影响其他文件

4. **目录结构规划**
   - 合理组织文件夹结构
   - 使用有意义的文件夹和文件名

## 技术架构

### API路径修正

我们修复了以下API路径问题：
- 原错误路径：`/api/v1/file2document/convert`
- 正确路径：`/api/file2document/convert`

### 认证机制

- Web界面使用：`@login_required` 装饰器
- SDK使用：`@token_required` 装饰器
- 自动处理认证差异

### 多级目录支持

- 修复了 `AnonymousUserMixin` 错误
- 支持任意层级的目录结构创建
- 正确处理文件权限和所有者信息

## 测试验证

运行测试脚本验证功能：

```bash
cd /path/to/ragflow
python test_enhanced_sdk.py
```

测试包括：
1. 带自动解析的文件夹上传
2. 不带自动解析的文件夹上传  
3. 直接上传方法测试

## 总结

这次增强为 RAGFlow SDK 提供了完整的文件夹上传和自动解析功能，支持：

✅ **完整的目录结构保持**
✅ **自动文档解析**
✅ **灵活的配置选项**
✅ **强大的错误处理**
✅ **向后兼容性**

现在您可以轻松地将本地文件夹批量上传到知识库，并立即开始使用这些文档进行检索和问答！
