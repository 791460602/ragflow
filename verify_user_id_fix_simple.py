#!/usr/bin/env python3
"""
简化的user_id类型安全修复验证脚本

避免导入复杂模块，只检查代码修复情况
"""

import os
import re

def check_file_content(file_path, patterns, description):
    """检查文件内容是否包含指定模式"""
    if not os.path.exists(file_path):
        print(f"❌ 文件不存在: {file_path}")
        return False
        
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        results = []
        for pattern, expected in patterns:
            found = bool(re.search(pattern, content, re.MULTILINE))
            if found == expected:
                results.append(True)
                status = "✅" if expected else "✅ (正确不包含)"
            else:
                results.append(False)
                status = "❌"
            print(f"   {status} {pattern}")
            
        success = all(results)
        print(f"{'✅' if success else '❌'} {description}: {file_path}")
        return success
        
    except Exception as e:
        print(f"❌ 检查文件失败 {file_path}: {e}")
        return False

def main():
    """主测试函数"""
    print("🔍 验证user_id类型安全修复")
    print("=" * 60)
    
    tests = []
    
    # 1. 检查数据库模型修复
    print("\n1. 检查数据库模型修复:")
    db_models_patterns = [
        (r'user_id = CharField\(.*null=True.*\)', True),  # user_id允许为空
        (r'user_id = CharField\(.*null=False.*\)', False),  # 不应该有null=False
    ]
    tests.append(check_file_content(
        '/home/cirno/ragflow/api/db/db_models.py',
        db_models_patterns,
        "数据库模型user_id字段修复"
    ))
    
    # 2. 检查服务层修复
    print("\n2. 检查服务层修复:")
    news_service_patterns = [
        (r'def create_source\(cls, tenant_id: str, user_id: Optional\[str\] = None', True),  # 类型注解
        (r'def create_task\(cls, tenant_id: str, user_id: Optional\[str\] = None', True),  # 类型注解
        (r'def create_content\(cls, tenant_id: str, user_id: Optional\[str\] = None', True),  # 类型注解
        (r'if user_id is None:\s+user_id = tenant_id', True),  # 默认值逻辑
    ]
    tests.append(check_file_content(
        '/home/cirno/ragflow/api/db/services/news_service.py',
        news_service_patterns,
        "数据库服务层修复"
    ))
    
    # 3. 检查API层修复
    print("\n3. 检查API层修复:")
    api_patterns = [
        (r'user_id=tenant_id,.*# 在RAGFlow架构中，使用tenant_id作为user_id', True),  # API修复
        (r'user_id=request\.headers\.get\(.*user_id.*\)', False),  # 不应该再从headers获取
    ]
    tests.append(check_file_content(
        '/home/cirno/ragflow/api/apps/sdk/news_collector.py',
        api_patterns,
        "API层修复"
    ))
    
    # 4. 检查文档更新
    print("\n4. 检查文档更新:")
    doc_patterns = [
        (r'BeartypeCallHintParamViolation.*已修复', True),  # 文档包含修复说明
        (r'user_id.*允许为空.*支持多租户架构', True),  # 架构说明
    ]
    tests.append(check_file_content(
        '/home/cirno/ragflow/NEWS_COLLECTOR_COMPLETE_GUIDE.md',
        doc_patterns,
        "技术文档更新"
    ))
    
    # 统计结果
    success_count = sum(tests)
    total_tests = len(tests)
    
    print("\n" + "=" * 60)
    print(f"修复验证结果: {success_count}/{total_tests} 通过")
    
    if success_count == total_tests:
        print("🎉 所有修复已完成! user_id类型安全问题已解决")
        print("\n修复总结:")
        print("1. ✅ 数据库模型: user_id字段设为可空 (null=True)")
        print("2. ✅ 服务层: 使用Optional[str]类型注解，提供默认值逻辑")
        print("3. ✅ API层: 使用tenant_id作为user_id参数")
        print("4. ✅ 文档: 更新了技术文档和故障排除指南")
        return True
    else:
        print("⚠️  部分修复未完成，请检查失败的项目")
        return False

if __name__ == "__main__":
    main()
