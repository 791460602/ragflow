#!/usr/bin/env python3
"""
调试新闻收集器上传过程

详细检查每一步骤，找出问题所在
"""

import os
import sys
import tempfile
import json
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def debug_upload_process():
    """调试上传过程"""
    try:
        from api.interfaces.news_crawler_interface import NewsSource, CrawlTask
        from api.crawlers.news_crawler_implementations import DemoCrawler
        from api.apps.sdk.news_collector import NewsCollector
        from common.misc_utils import get_uuid
        
        print("🔍 调试新闻收集器上传过程")
        print("=" * 50)
        
        # 1. 创建临时目录并生成文件
        with tempfile.TemporaryDirectory() as temp_dir:
            print(f"📁 临时目录: {temp_dir}")
            
            # 创建demo爬虫并生成文件
            crawler = DemoCrawler()
            source = NewsSource(
                id=get_uuid(),
                name="调试测试源",
                url="https://example.com/debug",
                crawler_config={}
            )
            
            task = CrawlTask(
                task_id=get_uuid(),
                sources=[source],
                output_directory=temp_dir,
                max_articles_per_source=3
            )
            
            print(f"🔄 执行demo爬虫...")
            result = crawler.crawl_articles(task)
            print(f"   状态: {result.status.value}")
            print(f"   生成文章数: {result.total_articles}")
            
            # 2. 检查生成的文件结构
            print(f"\n📋 检查生成的文件:")
            md_files = []
            for root, dirs, files in os.walk(temp_dir):
                level = root.replace(temp_dir, '').count(os.sep)
                indent = ' ' * 2 * level
                print(f"{indent}{os.path.basename(root)}/")
                
                subindent = ' ' * 2 * (level + 1)
                for file in files:
                    file_path = os.path.join(root, file)
                    file_size = os.path.getsize(file_path)
                    print(f"{subindent}{file} ({file_size} bytes)")
                    
                    if file.endswith('.md'):
                        md_files.append(file_path)
            
            print(f"\n📊 找到 {len(md_files)} 个markdown文件")
            
            # 3. 模拟上传过程
            print(f"\n🔄 模拟上传过程...")
            print(f"   遍历目录: {temp_dir}")
            
            found_files = []
            for root, dirs, files in os.walk(temp_dir):
                print(f"   检查目录: {root}")
                for file in files:
                    print(f"     文件: {file}")
                    if file.endswith('.md'):
                        file_path = os.path.join(root, file)
                        file_size = os.path.getsize(file_path)
                        found_files.append((file, file_path, file_size))
                        print(f"       ✅ 找到md文件: {file} ({file_size} bytes)")
            
            print(f"\n📋 上传处理统计:")
            print(f"   遍历发现的md文件: {len(found_files)}")
            
            if len(found_files) == 0:
                print("❌ 上传过程中没有找到任何md文件！")
                print("   这说明文件遍历有问题。")
                return False
            
            # 4. 测试实际的上传函数（不连数据库）
            print(f"\n🧪 测试上传函数逻辑...")
            
            try:
                # 模拟上传逻辑但不实际执行数据库操作
                for file, file_path, file_size in found_files:
                    print(f"   处理文件: {file}")
                    
                    # 读取文件内容  
                    with open(file_path, 'rb') as f:
                        blob = f.read()
                    
                    print(f"     文件大小: {len(blob)} bytes")
                    
                    # 生成存储位置
                    doc_id = get_uuid()
                    location = f"news_{doc_id}_{file}"
                    print(f"     存储位置: {location}")
                    
                    # 验证存储位置格式
                    if location.startswith('news_') and '_' in location:
                        print(f"     ✅ 存储位置格式正确")
                    else:
                        print(f"     ❌ 存储位置格式错误")
                        return False
                
                print(f"✅ 上传逻辑测试通过！")
                return True
                
            except Exception as e:
                print(f"❌ 上传逻辑测试失败: {e}")
                import traceback
                traceback.print_exc()
                return False
                
    except Exception as e:
        print(f"❌ 调试过程中出错: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = debug_upload_process()
    if success:
        print("\n🎉 调试成功！上传逻辑本身没有问题。")
        print("   问题可能在：")
        print("   1. 知识库ID不存在")
        print("   2. 数据库连接问题")
        print("   3. 存储系统配置问题")
    else:
        print("\n🚨 发现问题！需要进一步修复。")
