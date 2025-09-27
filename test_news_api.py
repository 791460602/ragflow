#!/usr/bin/env python3
"""
新闻收集器API测试脚本
"""

import requests
import json
import time

def test_news_collector_api():
    print('🧪 测试新闻收集器API修复')
    print('=' * 60)
    
    # 测试配置
    access_token = '4ebd448a9a2011f080f2e334638b0605'
    base_url = 'http://localhost:9222'
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {access_token}',
        'User-Agent': 'Mozilla/5.0 (compatible; NewsCollector-Test/1.0)'
    }
    
    # 测试1: 健康检查
    print('\n🏥 测试1: API健康检查')
    try:
        response = requests.get(f'{base_url}/v1/news_collector/ping', 
                              headers=headers, timeout=10)
        print(f'URL: {base_url}/v1/news_collector/ping')
        print(f'状态码: {response.status_code}')
        if response.status_code == 200:
            data = response.json()
            if data.get('code') == 0:
                print('✅ API服务正常')
            else:
                print(f'⚠️ API返回: {data.get("message")}')
        else:
            print(f'❌ HTTP错误: {response.text[:100]}...')
    except Exception as e:
        print(f'❌ 连接失败: {e}')
        print('💡 请确保RAGFlow服务器正在运行')
        return False
    
    # 测试2: 获取新闻源列表
    print('\n📋 测试2: 获取新闻源列表')
    try:
        response = requests.get(f'{base_url}/v1/news_collector/sources', 
                              headers=headers, timeout=10)
        print(f'URL: {base_url}/v1/news_collector/sources')
        print(f'状态码: {response.status_code}')
        
        if response.status_code == 200:
            data = response.json()
            print(f'响应数据: {json.dumps(data, indent=2, ensure_ascii=False)}')
            
            if data.get('code') == 0:
                sources = data.get('data', {}).get('sources', [])
                total = data.get('data', {}).get('total', 0)
                print(f'\n✅ 成功！获取到 {total} 个新闻源:')
                for i, source in enumerate(sources[:5], 1):
                    name = source.get('name', '未知')
                    url = source.get('url', '')
                    status = source.get('status', '')
                    print(f'  {i}. {name} ({status})')
                    print(f'     {url[:60]}...' if len(url) > 60 else f'     {url}')
                return True
            else:
                print(f'❌ API返回错误: code={data.get("code")}, message={data.get("message")}')
                return False
        else:
            print(f'❌ HTTP错误: {response.text[:200]}...')
            return False
            
    except Exception as e:
        print(f'❌ 请求失败: {e}')
        return False
    
    # 测试3: 创建新闻源（可选）
    print('\n➕ 测试3: 创建新闻源')
    try:
        test_source = {
            'name': '测试新闻源',
            'url': 'https://example.com/news',
            'remark': '这是一个测试新闻源'
        }
        
        response = requests.post(f'{base_url}/v1/news_collector/sources',
                               headers=headers,
                               json=test_source,
                               timeout=10)
        
        print(f'状态码: {response.status_code}')
        if response.status_code == 200:
            data = response.json()
            if data.get('code') == 0:
                print('✅ 新闻源创建成功!')
                source_id = data.get('data', {}).get('source', {}).get('id')
                print(f'   新闻源ID: {source_id}')
            else:
                print(f'⚠️ 创建失败: {data.get("message")}')
        else:
            print(f'❌ HTTP错误: {response.text[:100]}...')
            
    except Exception as e:
        print(f'❌ 创建请求失败: {e}')

if __name__ == '__main__':
    print('等待3秒确保服务器启动...')
    time.sleep(3)
    
    success = test_news_collector_api()
    
    print('\n' + '=' * 60)
    if success:
        print('🎉 API测试成功！新闻收集器功能正常工作！')
        print('\n📝 接下来你可以:')
        print('1. 在浏览器中打开RAGFlow前端')
        print('2. 导航到新闻收集页面')
        print('3. 设置API Key: 4ebd448a9a2011f080f2e334638b0605')
        print('4. 刷新页面查看新闻源列表')
    else:
        print('❌ API测试失败，请检查服务器状态和配置')
        print('\n🔧 故障排除:')
        print('1. 确保RAGFlow服务器正在运行')
        print('2. 检查端口9222是否可访问')
        print('3. 验证access_token是否正确')
    print('=' * 60)