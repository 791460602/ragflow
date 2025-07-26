#!/usr/bin/env python3
"""
新闻收集器完整测试流程
按顺序执行所有测试，验证系统功能
"""

import subprocess
import sys
import os

def run_command(cmd, description):
    """运行命令并显示结果"""
    print(f"\n{'='*60}")
    print(f"🔄 {description}")
    print(f"{'='*60}")
    print(f"执行命令: {cmd}")
    print("-" * 40)
    
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=os.getcwd())
        
        if result.stdout:
            print("✅ 输出:")
            print(result.stdout)
        
        if result.stderr:
            print("⚠️ 错误/警告:")
            print(result.stderr)
        
        if result.returncode == 0:
            print(f"✅ {description} - 成功完成")
            return True
        else:
            print(f"❌ {description} - 执行失败 (返回码: {result.returncode})")
            return False
            
    except Exception as e:
        print(f"❌ {description} - 异常: {e}")
        return False

def main():
    """完整测试流程"""
    print("🚀 新闻收集器完整测试流程")
    print("=" * 60)
    
    # 测试步骤
    tests = [
        {
            "cmd": "python setup_news_collector.py",
            "desc": "步骤1: 系统初始化",
            "required": True
        },
        {
            "cmd": "python test_news_collector.py", 
            "desc": "步骤2: 功能测试",
            "required": True
        },
        {
            "cmd": "python test_news_collector_api.py",
            "desc": "步骤3: API测试",
            "required": False  # 需要认证信息
        },
        {
            "cmd": "python quick_auth_test.py",
            "desc": "步骤4: 认证测试",
            "required": False  # 需要认证信息
        }
    ]
    
    passed = 0
    total = 0
    
    for test in tests:
        total += 1
        
        if run_command(test["cmd"], test["desc"]):
            passed += 1
        elif test["required"]:
            print(f"\n❌ 必需的测试失败: {test['desc']}")
            print("🛑 停止后续测试")
            break
        else:
            print(f"\n⚠️ 可选测试失败: {test['desc']} (可能需要配置认证信息)")
    
    # 最终报告
    print("\n" + "=" * 60)
    print("📊 测试结果汇总")
    print("=" * 60)
    print(f"总测试数: {total}")
    print(f"通过测试: {passed}")
    print(f"通过率: {passed/total*100:.1f}%")
    
    if passed >= 2:  # 至少通过前两个必需测试
        print("\n🎉 核心功能测试通过！新闻收集器可以使用了")
        
        print("\n📋 后续步骤:")
        print("1. 🔑 配置API认证信息 (编辑 test_news_collector_api.py)")
        print("2. 🌐 在RAGFlow前端创建知识库")
        print("3. 📰 创建新闻源和抓取任务")
        print("4. 📁 在文件管理页面查看抓取结果")
        
    else:
        print("\n❌ 核心功能测试失败")
        print("💡 请检查:")
        print("- RAGFlow环境是否正确配置")
        print("- 数据库连接是否正常")
        print("- 依赖包是否完整安装")

if __name__ == "__main__":
    main()
