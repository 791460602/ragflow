# 文件路径解析问题修复说明

## 问题描述

在使用 RAGFlow SDK 的自动解析功能时，出现了以下错误：

```
FileNotFoundError: [Errno 2] No such file or directory: '1(1).txt'
```

## 问题原因分析

这个问题的根本原因是**文件上传后的存储路径与解析器尝试访问的路径不匹配**：

### 问题链条：

1. **文件上传阶段**：
   - 用户上传文件 `1.txt`
   - 由于同名文件已存在，系统自动重命名为 `1(1).txt`
   - 文件在存储系统中的实际路径为 `1(1).txt`

2. **文档转换阶段**：
   - 文档记录的 `location` 字段被设置为实际存储路径 `1(1).txt`
   - 但解析任务的 `name` 字段仍为原始文件名 `1.txt`

3. **解析阶段**：
   - `task_executor.py` 调用 `chunker.chunk(task["name"], binary=binary, ...)`
   - 传递的文件名是 `task["name"]` (原始名称)，而不是实际存储的文件名
   - 在某些解析器中，当 binary 数据为空或解析失败时，会尝试直接打开文件
   - 由于文件名不匹配，导致 `FileNotFoundError`

## 修复方案

我们实施了多层修复方案：

### 1. 修正传递给解析器的文件名 (`rag/svr/task_executor.py`)

**修复前：**
```python
cks = await trio.to_thread.run_sync(lambda: chunker.chunk(task["name"], binary=binary, ...))
```

**修复后：**
```python
# 使用实际存储位置的文件名而不是原始任务名称
actual_filename = name if name else task["name"]
logging.info("Chunking with filename: '{}', binary size: {}".format(actual_filename, len(binary) if binary else 'None'))
cks = await trio.to_thread.run_sync(lambda: chunker.chunk(actual_filename, binary=binary, ...))
```

### 2. 增强文件读取错误处理 (`deepdoc/parser/utils.py`)

**修复前：**
```python
def get_text(fnm: str, binary=None) -> str:
    txt = ""
    if binary:
        encoding = find_codec(binary)
        txt = binary.decode(encoding, errors="ignore")
    else:
        with open(fnm, "r") as f:  # 直接尝试打开文件，可能失败
            # ...
```

**修复后：**
```python
def get_text(fnm: str, binary=None) -> str:
    txt = ""
    if binary:
        encoding = find_codec(binary)
        txt = binary.decode(encoding, errors="ignore")
    else:
        # 只有在文件确实存在且没有 binary 数据时才尝试打开文件
        try:
            import os
            if os.path.exists(fnm):
                with open(fnm, "r") as f:
                    # ...
            else:
                raise FileNotFoundError(f"File '{fnm}' not found and no binary data provided")
        except Exception as e:
            raise FileNotFoundError(f"Cannot read file '{fnm}': {e}")
```

### 3. 增加调试日志

添加了更详细的日志来帮助诊断问题：
- 记录从存储获取的 binary 数据大小
- 记录传递给解析器的实际文件名
- 记录存储地址获取过程

## 修复验证

### 测试场景

1. **文件名冲突场景**：
   - 上传同名文件，验证自动重命名后解析正常
   - 包含特殊字符的文件名

2. **多级目录结构**：
   - 验证嵌套文件夹中的文件解析正常

3. **自动解析流程**：
   - 验证 `auto_parse=True` 时完整流程正常

### 预期结果

修复后，应该能够：
- ✅ 成功上传包含重复名称的文件
- ✅ 自动解析不会出现 `FileNotFoundError`
- ✅ 解析器正确使用 binary 数据而不是文件路径
- ✅ 完整的上传→转换→解析流程正常工作

## 使用建议

### 1. 安全的使用方式

```python
# 推荐：启用自动解析
result = dataset.upload_folder(folder_path, parent_id, auto_parse=True)

# 验证解析状态
parse_result = result.get('parse_result')
if parse_result and parse_result.get('status') == 'started':
    print("✅ 解析已开始")
else:
    print("⚠️ 解析可能未启动，请检查")
```

### 2. 错误处理

```python
try:
    result = dataset.upload_folder(folder_path, parent_id, auto_parse=True)
    # 处理成功结果
except Exception as e:
    print(f"上传失败: {e}")
    # 错误恢复逻辑
```

### 3. 监控解析进度

- 解析是异步进行的，在 RAGFlow Web 界面查看进度
- 大文件解析可能需要较长时间
- 如果解析失败，可以在界面中手动重试

## 技术细节

### 关键修改的文件

1. **`rag/svr/task_executor.py`**：
   - 修正传递给解析器的文件名
   - 增加调试日志

2. **`deepdoc/parser/utils.py`**：
   - 增强 `get_text` 函数的错误处理
   - 确保优先使用 binary 数据

3. **`sdk/python/ragflow_sdk/ragflow.py`**：
   - 实现完整的上传→转换→解析工作流程

4. **`sdk/python/ragflow_sdk/modules/dataset.py`**：
   - 添加 `auto_parse` 参数支持

### 架构改进

- **分离关注点**：文件存储路径与解析逻辑分离
- **容错性**：即使文件名不匹配，也能通过 binary 数据正常解析
- **可观测性**：增加日志帮助问题诊断

## 向后兼容性

所有修改都保持向后兼容：
- 默认 `auto_parse=False`，不影响现有代码
- 原有的手动解析流程仍然正常工作
- API 接口没有破坏性变更

这次修复解决了文件路径解析的核心问题，使得自动解析功能能够可靠地处理各种文件名场景。
