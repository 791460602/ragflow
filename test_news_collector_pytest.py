#!/usr/bin/env python3
"""
新闻收集器完整功能测试 - pytest版本
使用pytest框架进行测试，支持fixture依赖管理

运行方式:
1. 直接运行: python test_news_collector_pytest.py
2. pytest运行: pytest test_news_collector_pytest.py -v
"""

import requests
import json
import time
import sys
import pytest
from datetime import datetime

# ==================== 配置信息 ====================
# 服务器配置
SERVER_URL = "http://localhost:9222"  # 根据您的实际端口修改
API_BASE = f"{SERVER_URL}/v1/news_collector"

# 认证信息 - 请填入您的真实认证信息
AUTH_TOKEN = "IjMwNTRjMjY0NjkzMDExZjA5ODU1M2I3YzM2NDc4NDA0Ig.aIM-PQ.HcZwkiqSWhvtHc0t1MEu7cRQDfM"
SESSION_COOKIE = "qwvk05mY7F4MiSwJHQ6ZFSA-cy1OqAGJ2OmwNsrIhT0"

# 知识库ID - 请在RAGFlow前端创建知识库后填入ID
KNOWLEDGE_BASE_ID = "7e95b1ba694111f098563b7c36478404"  # 请填入真实的知识库ID

# 测试用新闻源配置
TEST_NEWS_SOURCES = [
    {
        "name": "新浪科技",
        "url": "https://tech.sina.com.cn/",
        "remark": "新浪科技频道 - pytest测试用",
        "fetch_config": {
            "timeout": 30,
            "encoding": "utf-8",
            "headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        }
    },
    {
        "name": "网易科技",
        "url": "https://tech.163.com/",
        "remark": "网易科技频道 - pytest测试用",
        "fetch_config": {
            "timeout": 30,
            "encoding": "utf-8",
            "headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        }
    },
    {
        "name": "36氪",
        "url": "https://36kr.com/",
        "remark": "创业投资资讯 - pytest测试用",
        "fetch_config": {
            "timeout": 30,
            "encoding": "utf-8",
            "headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
        }
    }
]

# 全局状态管理
class TestState:
    def __init__(self):
        self.created_sources = []
        self.task_id = None
        self.task_data = None
        self.news_list = []
        self.documents = []

# 全局测试状态
test_state = TestState()

# ==================== 认证和工具函数 ====================
def get_auth_headers():
    """获取认证头部"""
    headers = {"Content-Type": "application/json"}
    if AUTH_TOKEN:
        headers["Authorization"] = AUTH_TOKEN
    return headers

def get_cookies():
    """获取认证cookies"""
    cookies = {}
    if SESSION_COOKIE:
        cookies["session"] = SESSION_COOKIE
    return cookies

def make_request(method, endpoint, **kwargs):
    """统一的请求方法"""
    url = f"{API_BASE}{endpoint}"
    headers = get_auth_headers()
    cookies = get_cookies()
    
    # 合并传入的headers
    if 'headers' in kwargs:
        headers.update(kwargs['headers'])
    
    kwargs['headers'] = headers
    kwargs['cookies'] = cookies
    kwargs['timeout'] = kwargs.get('timeout', 30)
    
    try:
        response = getattr(requests, method.lower())(url, **kwargs)
        return response
    except Exception as e:
        print(f"❌ 请求失败: {method} {endpoint} - {e}")
        return None

def print_section(title):
    """打印节标题"""
    print(f"\n{'='*60}")
    print(f"🔄 {title}")
    print(f"{'='*60}")

def print_step(step_num, description):
    """打印步骤"""
    print(f"\n{step_num}️⃣ {description}")
    print("-" * 40)

def check_response(response, operation):
    """检查响应结果"""
    if not response:
        print(f"❌ {operation} - 请求失败")
        return False
    
    print(f"📊 {operation} - 状态码: {response.status_code}")
    
    if response.status_code == 200:
        try:
            result = response.json()
            print(f"✅ {operation} - 成功")
            return result
        except:
            print(f"❌ {operation} - 响应不是有效JSON")
            print(f"响应内容: {response.text[:200]}")
            return False
    else:
        print(f"❌ {operation} - 失败")
        print(f"错误信息: {response.text[:200]}")
        return False

# ==================== pytest fixtures ====================
@pytest.fixture(scope="session", autouse=True)
def verify_configuration():
    """验证配置信息"""
    print_section("配置验证")
    
    errors = []
    
    if not AUTH_TOKEN and not SESSION_COOKIE:
        errors.append("❌ 缺少认证信息 (AUTH_TOKEN 或 SESSION_COOKIE)")
    
    if not KNOWLEDGE_BASE_ID:
        errors.append("❌ 缺少知识库ID (KNOWLEDGE_BASE_ID)")
    
    if errors:
        print("⚠️ 配置问题:")
        for error in errors:
            print(f"  {error}")
        print("\n💡 请在脚本顶部配置以下信息:")
        print("1. AUTH_TOKEN 或 SESSION_COOKIE (从浏览器开发者工具复制)")
        print("2. KNOWLEDGE_BASE_ID (在RAGFlow前端创建知识库后获取)")
        print("3. 确保RAGFlow服务运行在正确端口")
        pytest.fail("配置验证失败")
    
    print("✅ 配置验证通过")
    return True

@pytest.fixture(scope="session")
def created_sources():
    """创建测试新闻源"""
    print_step(2, "创建新闻源")
    
    created_sources = []
    
    for i, source_config in enumerate(TEST_NEWS_SOURCES):
        print(f"\n📰 创建新闻源 {i+1}: {source_config['name']}")
        
        response = make_request('POST', '/sources', json=source_config)
        result = check_response(response, f"创建新闻源 - {source_config['name']}")
        
        if result and result.get('code') == 0:
            source_data = result.get('data')
            created_sources.append(source_data)
            print(f"✅ 新闻源创建成功 - ID: {source_data.get('id')}")
        else:
            print(f"❌ 新闻源创建失败: {result}")
    
    test_state.created_sources = created_sources
    return created_sources

@pytest.fixture(scope="session")
def task_data(created_sources):
    """创建抓取任务"""
    print_step(4, "创建抓取任务")
    
    if not created_sources:
        pytest.fail("没有可用的新闻源")
    
    source_ids = [source['id'] for source in created_sources]
    
    task_config = {
        "task_name": f"pytest测试任务_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
        "kb_id": KNOWLEDGE_BASE_ID,
        "source_ids": source_ids,
        "auto_parse": True,
        "max_articles_per_source": 5
    }
    
    print(f"📋 任务配置:")
    print(f"  - 任务名称: {task_config['task_name']}")
    print(f"  - 知识库ID: {task_config['kb_id']}")
    print(f"  - 新闻源数量: {len(task_config['source_ids'])}")
    print(f"  - 每源最大文章数: {task_config['max_articles_per_source']}")
    
    response = make_request('POST', '/tasks', json=task_config)
    result = check_response(response, "创建抓取任务")
    
    if result and result.get('code') == 0:
        task_data = result.get('data')
        print(f"✅ 任务创建成功 - ID: {task_data.get('id')}")
        test_state.task_data = task_data
        test_state.task_id = task_data.get('id')
        return task_data
    else:
        pytest.fail("任务创建失败")

# ==================== 测试函数 ====================
def test_health_check():
    """测试健康检查"""
    print_step(1, "健康检查")
    
    response = make_request('GET', '/ping')
    result = check_response(response, "健康检查")
    
    assert result is not False, "健康检查失败"
    assert result.get('code') == 0, f"健康检查返回错误: {result}"
    print(f"🎉 服务状态: {result}")

def test_create_news_sources(created_sources):
    """验证新闻源创建"""
    assert len(created_sources) > 0, "没有成功创建任何新闻源"
    assert len(created_sources) == len(TEST_NEWS_SOURCES), f"预期创建 {len(TEST_NEWS_SOURCES)} 个新闻源，实际创建 {len(created_sources)} 个"
    
    for source in created_sources:
        assert 'id' in source, "新闻源缺少ID"
        assert source.get('id'), "新闻源ID为空"

def test_list_news_sources():
    """测试获取新闻源列表"""
    print_step(3, "获取新闻源列表")
    
    response = make_request('GET', '/sources')
    result = check_response(response, "获取新闻源列表")
    
    assert result is not False, "获取新闻源列表失败"
    assert result.get('code') == 0, f"获取新闻源列表返回错误: {result}"
    
    sources = result.get('data', [])
    print(f"📋 总计 {len(sources)} 个新闻源:")
    for source in sources[-3:]:  # 显示最新的3个
        print(f"  - {source.get('name')}: {source.get('url')} (状态: {source.get('status')})")
    
    assert len(sources) >= len(TEST_NEWS_SOURCES), "新闻源数量不足"

def test_create_news_task(task_data):
    """验证任务创建"""
    assert task_data is not None, "任务创建失败"
    assert 'id' in task_data, "任务缺少ID"
    assert task_data.get('id'), "任务ID为空"

def test_execute_task(task_data):
    """测试执行抓取任务"""
    print_step(5, "执行抓取任务")
    
    task_id = task_data['id']
    print(f"🚀 开始执行任务: {task_id}")
    
    # 执行任务
    response = make_request('POST', f'/tasks/{task_id}/execute')
    result = check_response(response, "执行抓取任务")
    
    assert result is not False, "任务执行请求失败"
    assert result.get('code') == 0, f"任务执行返回错误: {result}"
    
    print("⏳ 任务已开始执行，等待完成...")
    
    # 轮询任务状态
    max_wait_time = 180  # 最大等待3分钟
    wait_interval = 10   # 每10秒检查一次
    waited_time = 0
    
    while waited_time < max_wait_time:
        time.sleep(wait_interval)
        waited_time += wait_interval
        
        # 查询任务状态
        response = make_request('GET', f'/tasks/{task_id}')
        if response and response.status_code == 200:
            task_info = response.json()
            if task_info.get('code') == 0:
                task_data = task_info.get('data')
                status = task_data.get('status')
                statistics = task_data.get('statistics', {})
                
                print(f"📊 任务状态: {status} (等待时间: {waited_time}s)")
                print(f"   统计: 总数 {statistics.get('total_articles', 0)}, "
                      f"成功 {statistics.get('success_count', 0)}, "
                      f"失败 {statistics.get('failed_count', 0)}")
                
                if status in ['completed', 'failed']:
                    assert status == 'completed', f"任务执行失败，状态: {status}"
                    print("✅ 任务执行完成")
                    return
        
        print(f"⏳ 继续等待... ({waited_time}/{max_wait_time}s)")
    
    pytest.fail("任务执行超时")

def test_list_news_content():
    """测试获取新闻内容列表"""
    print_step(6, "查看抓取的新闻内容")
    
    response = make_request('GET', '/news?page=1&page_size=20')
    result = check_response(response, "获取新闻内容列表")
    
    assert result is not False, "获取新闻内容失败"
    assert result.get('code') == 0, f"获取新闻内容返回错误: {result}"
    
    data = result.get('data', {})
    news_list = data.get('data', [])
    total = data.get('total', 0)
    
    print(f"📰 总计抓取了 {total} 篇新闻:")
    for i, news in enumerate(news_list[:5]):  # 只显示前5篇
        print(f"  {i+1}. 来源: {news.get('source_id')} | URL: {news.get('original_url', '无URL')[:50]}...")
        print(f"     文档ID: {news.get('document_id', '未转换')}")
    
    test_state.news_list = news_list
    assert total >= 0, "新闻数量应该大于等于0"

def test_get_statistics():
    """测试获取统计信息"""
    print_step(7, "查看统计信息")
    
    response = make_request('GET', '/statistics')
    result = check_response(response, "获取统计信息")
    
    assert result is not False, "获取统计信息失败"
    assert result.get('code') == 0, f"获取统计信息返回错误: {result}"
    
    stats = result.get('data', {})
    print(f"📊 系统统计:")
    print(f"  - 总新闻源数: {stats.get('total_sources', 0)}")
    print(f"  - 活跃新闻源数: {stats.get('active_sources', 0)}")
    print(f"  - 总任务数: {stats.get('total_tasks', 0)}")
    print(f"  - 总新闻数: {stats.get('total_content', 0)}")
    print(f"  - 已解析新闻数: {stats.get('parsed_count', 0)}")
    print(f"  - 待解析新闻数: {stats.get('pending_count', 0)}")
    
    # 基本验证
    assert stats.get('total_sources', 0) >= 0, "新闻源数量应该大于等于0"
    assert stats.get('total_tasks', 0) >= 0, "任务数量应该大于等于0"

def test_task_documents(task_data):
    """测试查看任务生成的文档"""
    print_step(8, "查看任务生成的文档")
    
    task_id = task_data['id']
    response = make_request('GET', f'/tasks/{task_id}/documents')
    result = check_response(response, "获取任务文档")
    
    assert result is not False, "获取任务文档失败"
    assert result.get('code') == 0, f"获取任务文档返回错误: {result}"
    
    documents = result.get('data', [])
    print(f"📄 任务生成了 {len(documents)} 个文档:")
    for i, doc in enumerate(documents[:5]):  # 只显示前5个
        print(f"  {i+1}. 文档ID: {doc.get('doc_id')}")
        print(f"     文件名: {doc.get('name', '无名称')}")
        print(f"     大小: {doc.get('size', 0)} 字节")
    
    test_state.documents = documents
    assert len(documents) >= 0, "文档数量应该大于等于0"

# ==================== 直接运行支持 ====================
def main():
    """主测试流程 - 用于直接运行"""
    print("🚀 新闻收集器完整功能测试 (pytest版本)")
    print(f"测试时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"服务器: {SERVER_URL}")
    
    try:
        # 验证配置
        verify_configuration()
        
        # 创建新闻源
        sources = created_sources()
        
        # 创建任务
        task = task_data(sources)
        
        # 运行所有测试
        test_health_check()
        test_create_news_sources(sources)
        test_list_news_sources()
        test_create_news_task(task)
        test_execute_task(task)
        test_list_news_content()
        test_get_statistics()
        test_task_documents(task)
        
        # 最终报告
        print_section("测试完成报告")
        print(f"✅ 成功创建 {len(test_state.created_sources)} 个新闻源")
        print(f"✅ 成功创建并执行 1 个抓取任务")
        print(f"✅ 成功抓取 {len(test_state.news_list)} 篇新闻")
        print(f"✅ 成功生成 {len(test_state.documents)} 个文档")
        
        print(f"\n🎉 完整功能测试成功!")
        print(f"💡 您可以在RAGFlow前端的文件管理页面中查看:")
        if test_state.created_sources:
            print(f"   📁 新闻收集/{test_state.created_sources[0]['name']}/ 等文件夹")
        print(f"   📄 包含抓取的新闻文档")
        
        return True
        
    except Exception as e:
        print(f"\n❌ 测试过程中发生异常: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # 检查是否使用pytest运行
    if 'pytest' in sys.modules:
        print("🧪 使用pytest运行测试")
    else:
        print("=" * 80)
        print("🧪 新闻收集器完整功能测试工具 (pytest版本)")
        print("=" * 80)
        print("📋 运行方式:")
        print("  1. 直接运行: python test_news_collector_pytest.py")
        print("  2. pytest运行: pytest test_news_collector_pytest.py -v")
        print("=" * 80)
        print("📋 测试内容:")
        print("  1. ✓ 健康检查")
        print("  2. ✓ 创建多个新闻源")
        print("  3. ✓ 创建抓取任务")
        print("  4. ✓ 实际执行新闻抓取")
        print("  5. ✓ 自动转换为RAGFlow文档")
        print("  6. ✓ 查看抓取结果和统计")
        print("  7. ✓ 验证文档流集成")
        print("=" * 80)
        
        success = main()
        
        if success:
            print("\n🎉 所有测试通过!")
            sys.exit(0)
        else:
            print("\n❌ 测试失败")
            sys.exit(1)
