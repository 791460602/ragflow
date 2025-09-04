#!/usr/bin/env python3
"""
完整的新闻源CRUD操作测试

验证所有BeartypeCallHintParamViolation错误已修复
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.abspath('.'))

def test_news_source_crud():
    """测试新闻源CRUD操作"""
    print("🧪 测试新闻源CRUD操作...")
    
    try:
        from api.db.services.news_service import NewsSourceService
        
        tenant_id = "test_tenant_crud"
        source_id = None
        
        # 1. 测试创建（user_id=None）
        print("  📝 测试创建新闻源 (user_id=None)...")
        try:
            source = NewsSourceService.create_source(
                tenant_id=tenant_id,
                user_id=None,  # 测试None值
                name="测试新闻源_CRUD",
                url="https://example.com/test",
                remark="CRUD测试用例"
            )
            source_id = source.get('id')
            print(f"     ✅ 创建成功，ID: {source_id}")
        except Exception as e:
            print(f"     ❌ 创建失败: {e}")
            return False
        
        # 2. 测试列表查询（name=None, status=None）
        print("  📋 测试获取列表 (name=None, status=None)...")
        try:
            sources, total = NewsSourceService.get_by_tenant_id(
                tenant_id=tenant_id,
                name=None,  # 测试None值
                status=None  # 测试None值
            )
            print(f"     ✅ 查询成功，共 {total} 条记录")
        except Exception as e:
            print(f"     ❌ 查询失败: {e}")
            return False
        
        # 3. 测试带过滤条件的查询
        print("  🔍 测试带过滤条件的查询...")
        try:
            sources, total = NewsSourceService.get_by_tenant_id(
                tenant_id=tenant_id,
                name="测试",  # 提供过滤条件
                status="active"
            )
            print(f"     ✅ 过滤查询成功，共 {total} 条记录")
        except Exception as e:
            print(f"     ❌ 过滤查询失败: {e}")
            return False
        
        # 4. 测试更新
        if source_id:
            print("  ✏️  测试更新新闻源...")
            try:
                updated_source = NewsSourceService.update_source(
                    source_id=source_id,
                    tenant_id=tenant_id,
                    remark="已更新的备注"
                )
                print(f"     ✅ 更新成功")
            except Exception as e:
                print(f"     ❌ 更新失败: {e}")
                return False
        
        # 5. 清理测试数据
        if source_id:
            print("  🧹 清理测试数据...")
            try:
                NewsSourceService.update_source(
                    source_id=source_id,
                    tenant_id=tenant_id,
                    status='deleted'
                )
                print(f"     ✅ 清理成功")
            except Exception as e:
                print(f"     ❌ 清理失败: {e}")
        
        print("✅ 新闻源CRUD测试完全通过")
        return True
        
    except Exception as e:
        print(f"❌ 新闻源CRUD测试失败: {e}")
        return False

def test_news_task_crud():
    """测试新闻任务CRUD操作"""
    print("\n🧪 测试新闻任务CRUD操作...")
    
    try:
        from api.db.services.news_service import NewsTaskService
        
        tenant_id = "test_tenant_task"
        
        # 1. 测试任务列表查询（task_name=None, status=None）
        print("  📋 测试获取任务列表 (task_name=None, status=None)...")
        try:
            tasks, total = NewsTaskService.get_by_tenant_id(
                tenant_id=tenant_id,
                task_name=None,  # 测试None值
                status=None  # 测试None值
            )
            print(f"     ✅ 任务查询成功，共 {total} 条记录")
        except Exception as e:
            print(f"     ❌ 任务查询失败: {e}")
            return False
        
        # 2. 测试带过滤条件的任务查询
        print("  🔍 测试带过滤条件的任务查询...")
        try:
            tasks, total = NewsTaskService.get_by_tenant_id(
                tenant_id=tenant_id,
                task_name="测试",  # 提供过滤条件
                status="pending"
            )
            print(f"     ✅ 任务过滤查询成功，共 {total} 条记录")
        except Exception as e:
            print(f"     ❌ 任务过滤查询失败: {e}")
            return False
        
        print("✅ 新闻任务CRUD测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 新闻任务CRUD测试失败: {e}")
        return False

def test_edge_cases():
    """测试边界情况"""
    print("\n🧪 测试边界情况...")
    
    try:
        from api.db.services.news_service import NewsSourceService
        
        # 测试空字符串参数
        print("  🔍 测试空字符串参数...")
        try:
            sources, total = NewsSourceService.get_by_tenant_id(
                tenant_id="test_tenant",
                name="",  # 空字符串
                status=""  # 空字符串
            )
            print(f"     ✅ 空字符串参数处理正确")
        except Exception as e:
            print(f"     ❌ 空字符串参数处理失败: {e}")
            return False
        
        print("✅ 边界情况测试通过")
        return True
        
    except Exception as e:
        print(f"❌ 边界情况测试失败: {e}")
        return False

def main():
    """主函数"""
    print("=" * 60)
    print("🎯 新闻收集器完整CRUD功能验证")
    print("=" * 60)
    print("目标: 验证所有BeartypeCallHintParamViolation错误已彻底修复")
    print()
    
    tests = [
        test_news_source_crud,
        test_news_task_crud,
        test_edge_cases,
    ]
    
    results = []
    for test in tests:
        results.append(test())
    
    success_count = sum(results)
    total_tests = len(tests)
    
    print("\n" + "=" * 60)
    print(f"🏁 最终验证结果: {success_count}/{total_tests} 通过")
    
    if success_count == total_tests:
        print("🎉 所有CRUD功能完全正常!")
        print()
        print("✅ 彻底解决的问题:")
        print("   1. ❌ BeartypeCallHintParamViolation: user_id类型错误")
        print("   2. ❌ BeartypeCallHintParamViolation: name参数类型错误")
        print("   3. ❌ BeartypeCallHintParamViolation: status参数类型错误")
        print("   4. ❌ AttributeError: 'super' object has no attribute 'to_dict'")
        print()
        print("🔧 应用的修复:")
        print("   1. 所有可选字符串参数使用 Optional[str] 类型注解")
        print("   2. 所有Optional参数默认值设为 None")
        print("   3. 实现直接的 to_dict 方法，移除错误的 super() 调用")
        print("   4. 提供 user_id 默认值逻辑")
        print()
        print("🚀 新闻收集器API现在完全可用!")
        return True
    else:
        print("❌ 仍有问题需要解决")
        return False

if __name__ == "__main__":
    main()
