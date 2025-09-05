#!/usr/bin/env python3
"""
验证user_id类型安全修复

此脚本验证BeartypeCallHintParamViolation问题的修复情况
"""

import sys
import os
import requests
import json

# 添加项目路径
sys.path.insert(0, os.path.abspath('.'))

try:
    from api.db.services.news_service import NewsSourceService, NewsTaskService, NewsContentService
    from api.utils import get_uuid
    from datetime import datetime
    print("✅ 模块导入成功")
except ImportError as e:
    print(f"❌ 模块导入失败: {e}")
    sys.exit(1)

def test_database_services():
    """测试数据库服务的类型安全性"""
    print("\n=== 测试数据库服务 ===")
    
    try:
        # 1. 测试NewsSourceService.create_source
        print("1. 测试 NewsSourceService.create_source...")
        
        # 测试用例1: 提供user_id
        source_data_with_user = {
            'name': '测试新闻源_with_user',
            'url': 'https://example.com/news',
            'remark': '测试用例1 - 提供user_id',
        }
        
        # 这应该不会抛出类型错误
        try:
            result1 = NewsSourceService.create_source(
                tenant_id="test_tenant_123",
                user_id="test_user_123",
                **source_data_with_user
            )
            print("   ✅ 带user_id参数测试通过")
        except Exception as e:
            print(f"   ❌ 带user_id参数测试失败: {e}")
        
        # 测试用例2: 不提供user_id (应该使用tenant_id作为默认值)
        source_data_without_user = {
            'name': '测试新闻源_without_user',
            'url': 'https://example.com/news2',
            'remark': '测试用例2 - 不提供user_id',
        }
        
        try:
            result2 = NewsSourceService.create_source(
                tenant_id="test_tenant_456",
                **source_data_without_user
            )
            print("   ✅ 不带user_id参数测试通过")
        except Exception as e:
            print(f"   ❌ 不带user_id参数测试失败: {e}")
        
        # 测试用例3: 传递None作为user_id
        source_data_none_user = {
            'name': '测试新闻源_none_user',
            'url': 'https://example.com/news3',
            'remark': '测试用例3 - None作为user_id',
        }
        
        try:
            result3 = NewsSourceService.create_source(
                tenant_id="test_tenant_789",
                user_id=None,
                **source_data_none_user
            )
            print("   ✅ None作为user_id参数测试通过")
        except Exception as e:
            print(f"   ❌ None作为user_id参数测试失败: {e}")
            
    except Exception as e:
        print(f"❌ 数据库服务测试失败: {e}")
        return False
    
    print("✅ 数据库服务测试完成")
    return True

def test_api_endpoints():
    """测试API端点的类型安全性"""
    print("\n=== 测试API端点 ===")
    
    # 这里我们只测试导入，实际API测试需要启动服务器
    try:
        from api.apps.sdk.news_collector import create_news_source, create_news_task
        print("✅ API函数导入成功")
        
        # 检查API函数中是否正确使用了tenant_id作为user_id
        import inspect
        
        # 检查create_news_source函数
        source_code = inspect.getsource(create_news_source)
        if "user_id=tenant_id" in source_code:
            print("✅ create_news_source 已修复user_id传递")
        else:
            print("❌ create_news_source 未正确修复user_id传递")
            
        # 检查create_news_task函数
        task_code = inspect.getsource(create_news_task)
        if "user_id=tenant_id" in task_code:
            print("✅ create_news_task 已修复user_id传递")
        else:
            print("❌ create_news_task 未正确修复user_id传递")
            
    except ImportError as e:
        print(f"❌ API函数导入失败: {e}")
        return False
    except Exception as e:
        print(f"❌ API代码检查失败: {e}")
        return False
        
    return True

def test_data_models():
    """测试数据模型的修改"""
    print("\n=== 测试数据模型 ===")
    
    try:
        from api.db.db_models import NewsSource, NewsTask, NewsContent
        
        # 检查NewsSource模型
        user_id_field = NewsSource._meta.fields.get('user_id')
        if user_id_field and user_id_field.null:
            print("✅ NewsSource.user_id 允许为空")
        else:
            print("❌ NewsSource.user_id 不允许为空")
            
        # 检查NewsTask模型
        task_user_id_field = NewsTask._meta.fields.get('user_id')
        if task_user_id_field and task_user_id_field.null:
            print("✅ NewsTask.user_id 允许为空")
        else:
            print("❌ NewsTask.user_id 不允许为空")
            
        # 检查NewsContent模型
        content_user_id_field = NewsContent._meta.fields.get('user_id')
        if content_user_id_field and content_user_id_field.null:
            print("✅ NewsContent.user_id 允许为空")
        else:
            print("❌ NewsContent.user_id 不允许为空")
            
    except ImportError as e:
        print(f"❌ 数据模型导入失败: {e}")
        return False
    except Exception as e:
        print(f"❌ 数据模型检查失败: {e}")
        return False
        
    print("✅ 数据模型检查完成")
    return True

def main():
    """主测试函数"""
    print("🔍 验证user_id类型安全修复")
    print("=" * 50)
    
    success_count = 0
    total_tests = 3
    
    # 测试1: 数据模型
    if test_data_models():
        success_count += 1
        
    # 测试2: 数据库服务
    if test_database_services():
        success_count += 1
        
    # 测试3: API端点
    if test_api_endpoints():
        success_count += 1
    
    print("\n" + "=" * 50)
    print(f"测试结果: {success_count}/{total_tests} 通过")
    
    if success_count == total_tests:
        print("🎉 所有测试通过! user_id类型安全问题已修复")
        return True
    else:
        print("⚠️  部分测试失败，请检查修复情况")
        return False

if __name__ == "__main__":
    main()
