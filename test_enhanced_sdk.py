#!/usr/bin/env python3
"""
测试增强的 RAGFlow SDK 文件夹上传和自动解析功能
"""

import sys
import os

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

def test_upload_with_auto_parse():
    """测试带自动解析的文件夹上传功能"""
    print("\n🧪 测试 1: 带自动解析的文件夹上传")
    print("-" * 50)
    
    try:
        # 初始化客户端
        rag = RAGFlow(api_key=API_KEY, base_url=BASE_URL)
        
        # 创建测试数据集
        dataset_name = "测试自动解析数据集"
        try:
            dataset = rag.get_dataset(dataset_name)
            print(f"✅ 使用已存在的数据集: {dataset_name}")
        except:
            dataset = rag.create_dataset(
                name=dataset_name,
                description="测试自动解析功能",
                chunk_method="naive"
            )
            print(f"✅ 创建新数据集: {dataset_name}")
        
        # 创建一个测试文件夹
        test_folder = "test_upload"
        os.makedirs(test_folder, exist_ok=True)
        
        # 创建子文件夹和测试文件
        sub_folder = os.path.join(test_folder, "subfolder")
        os.makedirs(sub_folder, exist_ok=True)
        
        # 创建测试文件
        test_files = [
            (os.path.join(test_folder, "test1.txt"), "这是测试文件1的内容。\n包含一些中文文本。"),
            (os.path.join(sub_folder, "test2.txt"), "这是子文件夹中的测试文件2。\n用于测试目录结构保持。"),
            (os.path.join(test_folder, "readme.md"), "# 测试文档\n\n这是一个 Markdown 格式的测试文档。")
        ]
        
        for file_path, content in test_files:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
        
        print(f"📁 创建测试文件夹: {test_folder}")
        print(f"📄 创建 {len(test_files)} 个测试文件")
        
        # 测试带自动解析的上传
        print("\n🔄 开始上传文件夹并自动解析...")
        result = dataset.upload_folder(test_folder, "", auto_parse=True)
        
        print("🎉 上传并解析请求完成!")
        print(f"📊 结果: {result}")
        
        # 清理测试文件
        import shutil
        shutil.rmtree(test_folder)
        print("🧹 清理测试文件完成")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_upload_without_auto_parse():
    """测试不带自动解析的文件夹上传功能"""
    print("\n🧪 测试 2: 不带自动解析的文件夹上传")
    print("-" * 50)
    
    try:
        rag = RAGFlow(api_key=API_KEY, base_url=BASE_URL)
        
        dataset_name = "测试手动解析数据集"
        try:
            dataset = rag.get_dataset(dataset_name)
        except:
            dataset = rag.create_dataset(
                name=dataset_name,
                description="测试手动解析功能",
                chunk_method="naive"
            )
        
        # 创建简单测试文件
        test_file = "single_test.txt"
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write("这是一个简单的测试文件。")
        
        print(f"📄 创建测试文件: {test_file}")
        
        # 测试不带自动解析的上传
        print("🔄 开始上传文件夹（不自动解析）...")
        result = dataset.upload_folder(".", "", auto_parse=False)
        
        print("✅ 上传完成（未自动解析）")
        print(f"📊 结果: {result}")
        
        # 清理
        os.remove(test_file)
        print("🧹 清理测试文件完成")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

def test_direct_upload():
    """测试直接上传方法"""
    print("\n🧪 测试 3: 直接上传方法")
    print("-" * 50)
    
    try:
        rag = RAGFlow(api_key=API_KEY, base_url=BASE_URL)
        
        dataset_name = "测试直接上传数据集"
        try:
            dataset = rag.get_dataset(dataset_name)
        except:
            dataset = rag.create_dataset(
                name=dataset_name,
                description="测试直接上传功能",
                chunk_method="naive"
            )
        
        # 创建测试文件
        test_file = "direct_test.txt"
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write("这是直接上传测试文件。")
        
        print(f"📄 创建测试文件: {test_file}")
        
        # 测试直接上传
        print("🔄 开始直接上传...")
        documents = dataset.upload_folder_direct(".", auto_parse=True)
        
        print("✅ 直接上传完成")
        print(f"📚 上传的文档: {documents}")
        
        # 清理
        os.remove(test_file)
        print("🧹 清理测试文件完成")
        
        return True
        
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        return False

def main():
    """运行所有测试"""
    print("🚀 开始 RAGFlow SDK 增强功能测试")
    print("=" * 60)
    
    tests = [
        test_upload_with_auto_parse,
        test_upload_without_auto_parse,
        test_direct_upload
    ]
    
    passed = 0
    total = len(tests)
    
    for test_func in tests:
        try:
            if test_func():
                passed += 1
                print("✅ 测试通过\n")
            else:
                print("❌ 测试失败\n")
        except Exception as e:
            print(f"❌ 测试异常: {e}\n")
    
    print("=" * 60)
    print(f"🏁 测试完成: {passed}/{total} 个测试通过")
    
    if passed == total:
        print("🎉 所有测试都通过了！SDK 增强功能工作正常。")
    else:
        print("⚠️  部分测试失败，请检查配置和网络连接。")

if __name__ == "__main__":
    main()
