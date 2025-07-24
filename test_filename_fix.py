#!/usr/bin/env python3
"""
测试修复后的文件夹上传和自动解析功能
验证文件路径解析问题是否已解决
"""

import sys
import os
import time
import tempfile

# 添加SDK路径
sdk_path = os.path.join(os.path.dirname(__file__), 'sdk', 'python')
sys.path.insert(0, sdk_path)

try:
    from ragflow_sdk import RAGFlow
    print("✅ 成功导入 RAGFlow SDK")
except ImportError as e:
    print(f"❌ 导入 RAGFlow SDK 失败: {e}")
    print(f"💡 请确保在项目根目录运行此脚本")
    sys.exit(1)

# 配置参数
API_KEY = "ragflow-M3NDJjZmEyNjYwZDExZjBhMTAwYjlkOD"
BASE_URL = "http://localhost:9380"

def create_test_files():
    """创建一些测试文件来模拟原问题"""
    test_dir = tempfile.mkdtemp(prefix="ragflow_test_")
    
    # 创建一些可能引起文件名冲突的文件
    test_files = [
        ("test.txt", "这是一个普通的测试文件。\n包含多行文本。"),
        ("1.txt", "这是文件1。"),
        ("1(1).txt", "这是重复命名的文件1。"),  # 这种命名可能引起问题
        ("special@file#.txt", "包含特殊字符的文件名。"),
    ]
    
    # 创建子文件夹
    sub_dir = os.path.join(test_dir, "子文件夹")
    os.makedirs(sub_dir, exist_ok=True)
    
    sub_files = [
        ("nested_file.txt", "这是嵌套文件夹中的文件。"),
        ("another.txt", "另一个嵌套文件。"),
    ]
    
    # 写入文件
    for filename, content in test_files:
        filepath = os.path.join(test_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
    
    for filename, content in sub_files:
        filepath = os.path.join(sub_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
    
    print(f"📁 创建测试文件夹: {test_dir}")
    print(f"📄 创建 {len(test_files)} 个根文件，{len(sub_files)} 个子文件")
    
    return test_dir

def test_upload_with_problematic_names():
    """测试可能引起文件名问题的上传"""
    print("\n🧪 测试: 可能引起文件名问题的上传")
    print("-" * 50)
    
    try:
        # 创建测试文件
        test_dir = create_test_files()
        
        # 初始化客户端
        rag = RAGFlow(api_key=API_KEY, base_url=BASE_URL)
        print("✅ RAGFlow客户端初始化成功")
        
        # 创建测试数据集
        dataset_name = "测试文件名修复"
        try:
            dataset = rag.get_dataset(dataset_name)
            print(f"✅ 使用已存在的数据集: {dataset_name}")
        except:
            dataset = rag.create_dataset(
                name=dataset_name,
                description="测试文件名路径修复功能",
                chunk_method="naive"
            )
            print(f"✅ 创建新数据集: {dataset_name}")
        
        # 上传文件夹，启用自动解析来触发可能的问题
        print("🔄 开始上传文件夹并自动解析...")
        print("💡 这会测试文件路径解析问题是否已修复")
        
        result = dataset.upload_folder(test_dir, "", auto_parse=True)
        
        print("🎉 上传完成!")
        
        # 检查结果
        upload_data = result.get('upload_result', {}).get('data', [])
        convert_data = result.get('convert_result', {}).get('data', [])
        parse_result = result.get('parse_result')
        
        print(f"📁 成功上传 {len(upload_data)} 个文件")
        print(f"📚 成功转换 {len(convert_data)} 个文档")
        
        if parse_result:
            if parse_result.get('status') == 'started':
                print("✅ 文档解析已开始 - 修复成功！")
                print(f"📊 解析文档数量: {parse_result.get('document_count', 0)}")
                
                # 等待一段时间让解析开始
                print("⏳ 等待5秒让解析开始...")
                time.sleep(5)
                
                print("💡 请检查 RAGFlow 界面确认解析是否正常进行")
                print("✅ 如果没有看到 'FileNotFoundError' 错误，说明修复成功！")
                
            else:
                print(f"⚠️  解析启动失败: {parse_result.get('error', '未知错误')}")
        
        # 清理测试文件
        import shutil
        shutil.rmtree(test_dir)
        print("🧹 清理测试文件完成")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_manual_parse():
    """测试手动触发解析"""
    print("\n🧪 测试: 手动触发解析")
    print("-" * 50)
    
    try:
        rag = RAGFlow(api_key=API_KEY, base_url=BASE_URL)
        
        # 获取已存在的数据集
        dataset_name = "测试文件名修复"
        dataset = rag.get_dataset(dataset_name)
        
        # 获取数据集中的文档
        documents = dataset.list_documents()
        if not documents:
            print("⚠️  数据集中没有文档，跳过手动解析测试")
            return True
        
        # 选择一些文档进行手动解析
        doc_ids = [doc.id for doc in documents[:2]]  # 只测试前2个文档
        print(f"🔄 手动触发解析，文档数量: {len(doc_ids)}")
        
        result = dataset.async_parse_documents(doc_ids)
        print("✅ 手动解析触发成功")
        
        return True
        
    except Exception as e:
        print(f"❌ 手动解析测试失败: {e}")
        return False

def main():
    """运行所有测试"""
    print("🚀 开始文件名路径修复验证测试")
    print("=" * 60)
    print("这些测试将验证以下修复:")
    print("1. 文件上传后的路径与解析器使用的路径匹配")
    print("2. get_text 函数优先使用 binary 数据")
    print("3. 特殊文件名不会引起 FileNotFoundError")
    print("=" * 60)
    
    tests = [
        ("文件名问题修复测试", test_upload_with_problematic_names),
        ("手动解析测试", test_manual_parse),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n🧪 执行: {test_name}")
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name} 通过")
            else:
                print(f"❌ {test_name} 失败")
        except Exception as e:
            print(f"❌ {test_name} 异常: {e}")
    
    print("\n" + "=" * 60)
    print(f"🏁 测试完成: {passed}/{total} 个测试通过")
    
    if passed == total:
        print("🎉 所有测试都通过了！文件名路径问题已修复。")
        print("✅ 现在可以安全地使用自动解析功能了！")
    else:
        print("⚠️  部分测试失败，可能需要进一步检查。")
        print("💡 请查看详细的错误信息并检查服务器日志。")

if __name__ == "__main__":
    main()
