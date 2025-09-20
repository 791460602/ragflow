import React, { useState, useEffect } from 'react';
import { Button, Card, Empty, message, Spin, Space, Select, Input, Alert, Tabs, Modal } from 'antd';
import { PlusOutlined, ReloadOutlined, SyncOutlined, KeyOutlined } from '@ant-design/icons';
// 恢复表单组件
import NewsCollectorForm from './NewsCollectorForm';
// 恢复API调用
import { 
  getDatasets, 
  getNewsSources, 
  createNewsSource, 
  updateNewsSource, 
  deleteNewsSource,
  crawlFromPost,
  checkApiHealth 
} from './NewsCollectorService';

const { TabPane } = Tabs;
const { Search } = Input;

// 简化的接口定义
interface NewsSource {
  id?: string;
  name: string;
  url: string;
  status?: string;
  remark?: string;
  fetch_config?: Record<string, any>;
}

const getApiKey = () => {
  try {
    return localStorage.getItem('apiKey') || '';
  } catch (error) {
    console.warn('无法访问localStorage:', error);
    return '';
  }
};

const NewsCollector: React.FC = () => {
  // 基础状态
  const [sources, setSources] = useState<NewsSource[]>([]);
  const [datasets, setDatasets] = useState<{ id: string; name: string }[]>([]);
  const [loading, setLoading] = useState(false);
  const [sourcesLoading, setSourcesLoading] = useState(false);
  const [formModalVisible, setFormModalVisible] = useState(false);
  const [searchKeyword, setSearchKeyword] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [pagination, setPagination] = useState({ page: 1, pageSize: 10, total: 0 });
  const [apiStatus, setApiStatus] = useState<'checking' | 'ok' | 'error'>('checking');
  
  const [apiKey, setApiKey] = useState(getApiKey());
  const [apiKeyModalVisible, setApiKeyModalVisible] = useState(false);
  const [tempApiKey, setTempApiKey] = useState('');
  
  // API Key 保存函数
  const saveApiKey = (newApiKey: string) => {
    try {
      localStorage.setItem('apiKey', newApiKey);
      setApiKey(newApiKey);
      message.success('API Key 保存成功');
    } catch (error) {
      console.error('保存API Key失败:', error);
      message.error('保存API Key失败');
    }
  };
  
  // 打开API Key配置弹窗
  const openApiKeyModal = () => {
    setTempApiKey(apiKey);
    setApiKeyModalVisible(true);
  };
  
  // 关闭API Key配置弹窗
  const closeApiKeyModal = () => {
    setApiKeyModalVisible(false);
    setTempApiKey('');
  };
  
  // 确认保存API Key
  const handleSaveApiKey = async () => {
    if (!tempApiKey.trim()) {
      message.warning('请输入有效的API Key');
      return;
    }
    
    const cleanApiKey = tempApiKey.trim();
    console.log('=== 保存API Key ===');
    console.log('原始长度:', tempApiKey.length);
    console.log('清理后长度:', cleanApiKey.length);
    console.log('格式检查:', /^[a-zA-Z0-9\-_]{20,}$/.test(cleanApiKey) ? '正常' : '异常');
    
    // 保存API Key
    saveApiKey(cleanApiKey);
    
    // 关闭弹窗
    closeApiKeyModal();
    
    // 等待稍微后测试连接
    setTimeout(() => {
      console.log('开始测试API连接...');
      checkApiStatus();
    }, 500);
  };
  
  // 数据加载函数 - 添加更多错误防护
  const loadDatasets = async () => {
    if (!apiKey) {
      console.warn('没有API Key，跳过加载知识库');
      setDatasets([]);
      return;
    }
    
    try {
      console.log('开始加载知识库列表...');
      const res = await getDatasets(apiKey);
      
      // 安全检查响应数据
      if (res && res.data) {
        const datasets = Array.isArray(res.data.data) ? res.data.data : [];
        setDatasets(datasets);
        console.log('加载知识库列表成功:', datasets.length);
      } else {
        console.warn('知识库API响应格式异常:', res);
        setDatasets([]);
      }
    } catch (error: any) {
      console.error('加载知识库列表失败:', error);
      setDatasets([]);
      // 只在非404错误时记录警告
      if (error.response?.status !== 404) {
        console.warn('知识库API调用失败，但不影响核心功能');
      }
    }
  };

  const loadSources = async (params?: {
    page?: number;
    pageSize?: number;
    name?: string;
    status?: string;
  }, forceRefresh = false) => {
    if (!apiKey) {
      console.warn('没有API Key，显示空列表');
      setSources([]);
      setPagination({ page: 1, pageSize: 10, total: 0 });
      setSourcesLoading(false);
      return;
    }
    
    console.log(`${forceRefresh ? '强制' : ''}加载新闻源列表...`, params);
    setSourcesLoading(true);
    
    try {
      // 强制刷新时重置到第一页
      const requestParams = {
        page: forceRefresh ? 1 : (params?.page || pagination.page || 1),
        page_size: params?.pageSize || pagination.pageSize || 10,
        name: params?.name || searchKeyword || '',
        status: params?.status || statusFilter || ''
      };
      
      // 清理空参数
      const cleanParams = Object.fromEntries(
        Object.entries(requestParams).filter(([_, v]) => v !== '' && v !== undefined)
      );
      
      console.log('API请求参数:', cleanParams);
      const response = await getNewsSources(apiKey, cleanParams);
      console.log('API响应原始数据:', response);
      
      // 安全检查响应数据
      if (response && response.data) {
        const { data, total, page, page_size } = response.data;
        const sourcesList = Array.isArray(data) ? data : [];
        const totalCount = typeof total === 'number' ? total : 0;
        const currentPage = typeof page === 'number' ? page : 1;
        const pageSize = typeof page_size === 'number' ? page_size : 10;
        
        console.log('解析后的数据:', { sourcesList: sourcesList.length, totalCount, currentPage, pageSize });
        
        setSources(sourcesList);
        setPagination({ page: currentPage, pageSize, total: totalCount });
        console.log(`加载新闻源成功: ${sourcesList.length} 个，总计: ${totalCount}`);
        
        // 显示前几个新闻源的详细信息
        if (sourcesList.length > 0) {
          console.log('前 3 个新闻源:', sourcesList.slice(0, 3).map(s => ({ id: s.id, name: s.name, url: s.url })));
        }
        
        // 如果是强制刷新且没有数据，给出提示
        if (forceRefresh && sourcesList.length === 0) {
          console.warn('强制刷新后仍然没有数据');
          console.warn('可能原因: 1.数据库事务延迟 2.用户权限隔离 3.查询条件问题');
          
          // 不立即显示警告，等待重试机制完成
          if (!forceRefresh) {
            message.warning('数据可能还在同步中，请稍后再试或手动刷新');
          }
        }
      } else {
        console.warn('新闻源API响应格式异常:', response);
        setSources([]);
        setPagination({ page: 1, pageSize: 10, total: 0 });
      }
      
    } catch (error: any) {
      console.error('加载新闻源失败:', error);
      
      // 更友好的错误处理
      let errorMessage = '加载新闻源列表失败';
      if (error.response?.status === 404) {
        errorMessage = 'API接口不存在，请检查后端服务';
      } else if (error.response?.data?.message) {
        errorMessage = error.response.data.message;
      } else if (error.message) {
        errorMessage = error.message;
      }
      
      // 只在非404错误时显示错误消息
      if (error.response?.status === 404) {
        console.warn('新闻收集器API接口不存在，请检查后端服务是否启动');
      } else {
        message.error(errorMessage);
      }
      
      // 错误时设置空数据，防止页面崩溃
      setSources([]);
      setPagination({ page: 1, pageSize: 10, total: 0 });
    } finally {
      setSourcesLoading(false);
    }
  };

  // 事件处理函数
  const [editingSource, setEditingSource] = useState<NewsSource | null>(null);
  
  const openAddModal = () => {
    setEditingSource(null);
    setFormModalVisible(true);
  };

  const openEditModal = (source: NewsSource) => {
    setEditingSource(source);
    setFormModalVisible(true);
  };

  const closeModal = () => {
    setFormModalVisible(false);
    setEditingSource(null);
  };

  const handleCrawlNews = async () => {
    const activeSourceIds = sources.filter(s => s.status === 'active' && s.id).map(s => s.id!);
    
    if (activeSourceIds.length === 0) {
      message.warning('没有可抓取的活跃新闻源');
      return;
    }
    
    if (!apiKey) {
      message.warning('请先配置API Key');
      return;
    }
    
    setLoading(true);
    try {
      await crawlFromPost(apiKey, {
        source_ids: activeSourceIds,
        depth: 2,
        max_pages_per_source: 10
      });
      message.success(`已启动后台抓取任务，正在处理 ${activeSourceIds.length} 个新闻源`);
      console.log('启动抓取任务成功:', activeSourceIds);
    } catch (error: any) {
      console.error('抓取失败:', error);
      
      let errorMessage = '抓取失败';
      if (error.response?.status === 404) {
        errorMessage = '抓取API接口不存在，请检查后端服务';
      } else if (error.response?.data?.message) {
        errorMessage = error.response.data.message;
      } else if (error.message) {
        errorMessage = error.message;
      }
      
      message.error(errorMessage);
    } finally {
      setLoading(false);
    }
  };

  const handleAddSource = async (data: NewsSource) => {
    if (!apiKey) {
      message.warning('请先配置API Key');
      return;
    }
    
    if (!data.name || !data.url) {
      message.error('新闻源名称和URL不能为空');
      return;
    }
    
    setLoading(true);
    try {
      console.log('=== 开始创建新闻源 ===');
      console.log('创建数据:', data);
      console.log('当前列表数量:', sources.length);
      
      const response = await createNewsSource(apiKey, data);
      console.log('创建响应完整数据:', response);
      console.log('创建响应状态:', response.status);
      console.log('创建响应内容:', response.data);
      
      if (response.status === 200 || response.status === 201) {
        message.success('新闻源创建成功');
        closeModal(); // 关闭弹窗
        
        // 多次尝试刷新，解决数据库事务延迟问题
        const tryRefreshData = async (attempt = 1, maxAttempts = 3) => {
          console.log(`=== 第 ${attempt} 次尝试刷新数据 ===`);
          
          try {
            await loadSources(undefined, true); // 强制刷新
            
            // 检查是否有数据
            if (sources.length > 0 || pagination.total > 0) {
              console.log(`刷新成功！获取到 ${sources.length} 条数据`);
              return true;
            } else if (attempt < maxAttempts) {
              console.log(`第 ${attempt} 次尝试仍无数据，${2 * attempt} 秒后重试...`);
              setTimeout(() => tryRefreshData(attempt + 1, maxAttempts), 2000 * attempt);
              return false;
            } else {
              console.warn('多次尝试后仍无数据，可能需要手动刷新或检查数据库');
              message.warning('数据加载延迟，请稍后手动刷新或检查后台日志');
              return false;
            }
          } catch (refreshError) {
            console.error(`第 ${attempt} 次刷新失败:`, refreshError);
            if (attempt < maxAttempts) {
              console.log(`${2 * attempt} 秒后重试...`);
              setTimeout(() => tryRefreshData(attempt + 1, maxAttempts), 2000 * attempt);
            }
            return false;
          }
        };
        
        // 等待 1 秒后开始第一次尝试
        console.log('等待 1 秒后开始刷新...');
        setTimeout(() => tryRefreshData(1, 3), 1000);
      } else {
        console.warn('创建响应状态异常:', response.status);
        message.error('创建响应状态异常');
      }
      
    } catch (error: any) {
      console.error('=== 创建新闻源失败 ===');
      console.error('错误详情:', error);
      console.error('错误响应:', error.response);
      
      let errorMessage = '创建失败';
      if (error.response?.data?.message) {
        errorMessage = error.response.data.message;
      } else if (error.message) {
        errorMessage = error.message;
      }
      
      message.error(errorMessage);
    } finally {
      setLoading(false);
    }
  };
  
  const handleEditSource = async (data: NewsSource) => {
    if (!apiKey || !editingSource?.id) {
      message.warning('无法获取必要信息');
      return;
    }
    
    if (!data.name || !data.url) {
      message.error('新闻源名称和URL不能为空');
      return;
    }
    
    setLoading(true);
    try {
      console.log('更新新闻源:', editingSource.id, data);
      const response = await updateNewsSource(apiKey, editingSource.id, data);
      console.log('更新响应:', response);
      
      message.success('新闻源更新成功');
      closeModal(); // 关闭弹窗
      
      // 立即刷新列表
      console.log('开始刷新新闻源列表...');
      await loadSources(undefined, true); // 强制刷新
      console.log('新闻源列表刷新完成');
      
    } catch (error: any) {
      console.error('更新新闻源失败:', error);
      
      let errorMessage = '更新失败';
      if (error.response?.data?.message) {
        errorMessage = error.response.data.message;
      } else if (error.message) {
        errorMessage = error.message;
      }
      
      message.error(errorMessage);
    } finally {
      setLoading(false);
    }
  };
  
  const handleDeleteSource = async (id: string) => {
    if (!apiKey) {
      message.warning('请先配置API Key');
      return;
    }
    
    if (!id) {
      message.error('无效的新闻源ID');
      return;
    }
    
    try {
      console.log('删除新闻源:', id);
      const response = await deleteNewsSource(apiKey, id);
      console.log('删除响应:', response);
      
      message.success('新闻源删除成功');
      
      // 立即刷新列表
      console.log('开始刷新新闻源列表...');
      await loadSources(undefined, true); // 强制刷新
      console.log('新闻源列表刷新完成');
      
    } catch (error: any) {
      console.error('删除新闻源失败:', error);
      
      let errorMessage = '删除失败';
      if (error.response?.data?.message) {
        errorMessage = error.response.data.message;
      } else if (error.message) {
        errorMessage = error.message;
      }
      
      message.error(errorMessage);
    }
  };
  
  // API状态检查 - 增强调试信息
  const checkApiStatus = async () => {
    if (!apiKey) {
      console.log('API Key 未配置');
      setApiStatus('error');
      return;
    }
    
    console.log('=== API 状态检查开始 ===');
    console.log('API Key 长度:', apiKey.length);
    console.log('API Key 前10位:', apiKey.substring(0, 10) + '...');
    console.log('API Key 格式检查:', /^[a-zA-Z0-9\-_]{20,}$/.test(apiKey) ? '格式正常' : '格式可能异常');
    
    setApiStatus('checking');
    try {
      console.log('调用 checkApiHealth...');
      const result = await checkApiHealth(apiKey);
      console.log('checkApiHealth 结果:', result);
      
      if (result.status === 'ok') {
        setApiStatus('ok');
        console.log('✅ API状态正常');
        message.success('API 连接成功');
      } else {
        setApiStatus('error');
        console.warn('❌ API状态异常:', result.error);
        message.error('API 连接异常: ' + result.error);
      }
    } catch (error: any) {
      setApiStatus('error');
      console.error('❌ API状态检查失败:', error);
      
      let errorMsg = 'API 连接失败';
      if (error.response?.status === 401) {
        errorMsg = 'API Key 无效或已过期';
      } else if (error.response?.status === 404) {
        errorMsg = 'API 接口不存在';
      } else if (error.message) {
        errorMsg = error.message;
      }
      
      message.error(errorMsg);
    }
    console.log('=== API 状态检查结束 ===');
  };

  // 生命周期 - 修复数据加载逻辑
  useEffect(() => {
    console.log('组件加载，API Key状态:', apiKey ? '已配置' : '未配置');
    
    if (apiKey) {
      // 先检查API状态
      checkApiStatus();
    } else {
      console.warn('API Key 未配置，跳过数据加载');
      setApiStatus('error');
      setSources([]);
      setDatasets([]);
      setPagination({ page: 1, pageSize: 10, total: 0 });
    }
  }, [apiKey]);

  // 监听API状态变化，当API变为正常时加载数据
  useEffect(() => {
    if (apiStatus === 'ok' && apiKey) {
      console.log('API状态正常，开始加载数据');
      Promise.allSettled([
        loadDatasets(),
        loadSources()
      ]).then(results => {
        results.forEach((result, index) => {
          if (result.status === 'rejected') {
            console.error(`初始API调用${index}失败:`, result.reason);
          }
        });
      });
    }
  }, [apiStatus, apiKey]);

  useEffect(() => {
    if (apiKey && (searchKeyword !== '' || statusFilter !== '')) {
      console.log('搜索条件变化:', { searchKeyword, statusFilter });
      const timeoutId = setTimeout(() => {
        loadSources({ name: searchKeyword, status: statusFilter }).catch(err => {
          console.error('搜索加载失败:', err);
        });
      }, 300); // 防抖
      
      return () => clearTimeout(timeoutId);
    }
  }, [searchKeyword, statusFilter]);

  try {
    return (
      <div style={{ padding: '32px 16px', maxWidth: '1200px', margin: '0 auto' }}>
        {/* API状态警告 */}
        {!apiKey && (
          <Alert
            type="warning"
            showIcon
            message="请先配置 API Key"
            description="在使用新闻源管理功能之前，您需要配置有效的 API Key。"
            style={{ marginBottom: 16 }}
            action={
              <Button size="small" type="primary" onClick={openApiKeyModal}>
                配置 API Key
              </Button>
            }
          />
        )}
        
        {apiKey && apiStatus === 'error' && (
          <Alert
            type="error"
            showIcon
            message="API Key 认证失败或服务连接异常"
            description="可能是API Key无效、过期，或者新闻收集器API接口不可用。"
            action={
              <Space>
                <Button size="small" onClick={openApiKeyModal}>
                  重新配置 API Key
                </Button>
                <Button size="small" onClick={checkApiStatus}>
                  重新检查
                </Button>
              </Space>
            }
            style={{ marginBottom: 16 }}
          />
        )}
        
        {apiKey && apiStatus === 'checking' && (
          <Alert
            type="info"
            showIcon
            message="正在检查服务状态..."
            style={{ marginBottom: 16 }}
          />
        )}
        
        {/* 头部区域 */}
        <div style={{ 
          display: 'flex', 
          justifyContent: 'space-between', 
          alignItems: 'center', 
          marginBottom: 16 
        }}>
          <div>
            <h2 style={{ margin: 0 }}>新闻收集器</h2>
            <p style={{ color: '#666', margin: '8px 0 0 0' }}>
              配置新闻源，智能抓取网页内容。支持自动模式和精确模式。
            </p>
            {apiKey && (
              <p style={{ color: '#52c41a', margin: '4px 0 0 0', fontSize: '12px' }}>
                ✅ API Key 已配置 ({apiKey.substring(0, 8)}...)
              </p>
            )}
          </div>
          <Space>
            <Button 
              icon={<KeyOutlined />}
              onClick={openApiKeyModal}
              title="配置API Key"
            >
              API Key
            </Button>
            <Button 
              icon={<ReloadOutlined />}
              onClick={async () => {
                if (!apiKey) {
                  message.warning('API Key 未配置');
                  return;
                }
                
                console.log('=== 强制数据刷新 ===');
                setSourcesLoading(true);
                
                try {
                  const response = await fetch('/api/v1/news_collector/sources?page=1&page_size=50', {
                    headers: { 'Authorization': `Bearer ${apiKey}` }
                  });
                  
                  const data = await response.json();
                  console.log('API响应:', data);
                  
                  if (data.code === 0 && data.data) {
                    const { sources = [], total = 0 } = data.data;
                    console.log(`获取到 ${sources.length} 个新闻源`);
                    
                    setSources(sources);
                    setPagination({ page: 1, pageSize: 50, total });
                    
                    message.success(`数据刷新成功！获取到 ${sources.length} 个新闻源`);
                  } else {
                    message.error(data.message || '获取数据失败');
                  }
                } catch (error) {
                  console.error('刷新失败:', error);
                  message.error('刷新失败');
                } finally {
                  setSourcesLoading(false);
                }
              }}
              loading={sourcesLoading}
              disabled={!apiKey}
            >
              强制刷新
            </Button>
            <Button 
              type="primary" 
              icon={<PlusOutlined />}
              onClick={openAddModal}
              disabled={!apiKey}
            >
              添加新闻源
            </Button>
            <Button 
              type="primary" 
              icon={<SyncOutlined />}
              onClick={handleCrawlNews}
              loading={loading}
              disabled={!apiKey}
            >
              即时抓取
            </Button>
          </Space>
        </div>

        {/* 主要内容区域 */}
        <Card style={{ marginTop: 16 }}>
          <Tabs defaultActiveKey="sources">
            <TabPane tab="新闻源管理" key="sources">
              {/* 搜索过滤区域 */}
              <div style={{ marginBottom: 16 }}>
                <Space>
                  <Search
                    placeholder="搜索新闻源名称"
                    value={searchKeyword}
                    onChange={(e) => setSearchKeyword(e.target.value)}
                    style={{ width: 200 }}
                    allowClear
                  />
                  <Select
                    placeholder="选择状态"
                    value={statusFilter}
                    onChange={setStatusFilter}
                    style={{ width: 120 }}
                    allowClear
                  >
                    <Select.Option value="active">启用</Select.Option>
                    <Select.Option value="inactive">禁用</Select.Option>
                  </Select>
                  <span style={{ color: '#666', fontSize: '14px' }}>
                    共 {pagination.total} 个新闻源 (当前显示: {sources.length})
                  </span>
                  <Button 
                    size="small" 
                    type="text" 
                    onClick={() => {
                      console.log('当前状态调试信息:');
                      console.log('- sources.length:', sources.length);
                      console.log('- pagination:', pagination);
                      console.log('- sourcesLoading:', sourcesLoading);
                      console.log('- apiStatus:', apiStatus);
                      console.log('- searchKeyword:', searchKeyword);
                      console.log('- statusFilter:', statusFilter);
                      console.log('- apiKey 前8位:', apiKey?.substring(0, 8) + '...');
                      
                      // 获取当前用户信息并对比tenant_id
                      if (apiKey) {
                        console.log('=== TENANT_ID 对比调试 ===');
                        console.log('数据库中的 tenant_id: b6931dc26e7511f0979feeeb2f257f...');
                        
                        fetch('/v1/user/info', {
                          headers: { 'Authorization': `Bearer ${apiKey}` }
                        })
                        .then(res => res.json())
                        .then(data => {
                          console.log('当前用户信息:', data);
                          if (data.data) {
                            const currentTenantId = data.data.tenant_id;
                            const dbTenantId = 'b6931dc26e7511f0979feeeb2f257f';
                            
                            console.log('- 前端 user_id:', data.data.id);
                            console.log('- 前端 tenant_id:', currentTenantId);
                            console.log('- 数据库 tenant_id:', dbTenantId + '...');
                            console.log('- email:', data.data.email);
                            
                            if (currentTenantId && currentTenantId.startsWith(dbTenantId)) {
                              console.log('✅ tenant_id 匹配！');
                            } else {
                              console.log('❌ tenant_id 不匹配！这就是问题所在！');
                              console.log('解决方案: 需要检查用户登录状态或API Key权限');
                            }
                          }
                        })
                        .catch(err => console.error('获取用户信息失败:', err));
                      }
                    }}
                  >
                    调试信息
                  </Button>
                  <Button 
                    size="small" 
                    type="primary" 
                    onClick={() => {
                      console.log('=== 全面API调试检查 ===');
                      console.log('当前 API Key:', apiKey ? (apiKey.substring(0, 30) + '...') : '未配置');
                      
                      if (!apiKey) {
                        console.log('❌ API Key 未配置');
                        return;
                      }
                      
                      // 1. 测试用户信息接口
                      console.log('1. 测试用户信息接口...');
                      fetch('/v1/user/info', {
                        headers: { 'Authorization': `Bearer ${apiKey}` }
                      })
                      .then(res => {
                        console.log('用户信息接口状态:', res.status);
                        return res.json();
                      })
                      .then(userData => {
                        console.log('用户信息:', userData);
                        
                        if (userData.data) {
                          const userTenantId = userData.data.id;  // 使用user.id作为tenant_id
                          const dbTenantId = 'b6931dc26e7511f0979feeeb2f257f152';  // 完整ID
                          console.log(`用户ID: ${userTenantId}`);
                          console.log(`目标ID: ${dbTenantId}`);
                          console.log(`ID匹配: ${userTenantId === dbTenantId ? '✅ 匹配' : '❌ 不匹配'}`);
                        }
                        
                        // 2. 测试新闻源API
                        console.log('2. 测试新闻源API...');
                        return fetch('/api/sdk/news_collector/sources?page=1&page_size=20', {
                          headers: { 'Authorization': `Bearer ${apiKey}` }
                        });
                      })
                      .then(res => {
                        console.log('新闻源API状态:', res.status);
                        if (res.status === 404) {
                          console.log('❌ API路径不存在，检查后端路由配置');
                        }
                        return res.json();
                      })
                      .then(sourcesData => {
                        console.log('新闻源API响应:', sourcesData);
                        
                        if (sourcesData.data && sourcesData.data.sources) {
                          console.log(`✅ 成功获取 ${sourcesData.data.sources.length} 个新闻源`);
                          sourcesData.data.sources.forEach((s: any, i: number) => {
                            console.log(`${i+1}. ${s.name} - ${s.status}`);
                          });
                        } else {
                          console.log('❌ 新闻源API返回数据为空');
                          console.log('可能原因:');
                          console.log('- API路径错误');
                          console.log('- 后端服务未正确运行');
                          console.log('- 数据库查询逻辑错误');
                        }
                        
                        // 3. 检查前端状态
                        console.log('3. 检查前端状态...');
                        console.log('- sources.length:', sources.length);
                        console.log('- sourcesLoading:', sourcesLoading);
                        console.log('- pagination:', pagination);
                        
                        if (sourcesData.data && sourcesData.data.sources && sourcesData.data.sources.length > 0) {
                          console.log('✅ API有数据，但前端没显示，尝试更新前端状态...');
                          
                          // 直接更新前端状态
                          const apiSources = sourcesData.data.sources;
                          setSources(apiSources);
                          setPagination({
                            page: sourcesData.data.page || 1,
                            pageSize: sourcesData.data.page_size || 10,
                            total: sourcesData.data.total || 0
                          });
                          
                          console.log(`✅ 已更新前端状态，现在应该显示 ${apiSources.length} 个新闻源`);
                          message.success(`数据已更新！现在显示 ${apiSources.length} 个新闻源`);
                        }
                        
                        // 4. 测试统计API
                        console.log('4. 测试统计API...');
                        return fetch('/v1/news_collector/statistics', {
                          headers: { 'Authorization': `Bearer ${apiKey}` }
                        });
                      })
                      .then(res => {
                        console.log('统计API状态:', res.status);
                        return res.json();
                      })
                      .then(statsData => {
                        console.log('统计API响应:', statsData);
                      })
                      .catch(err => {
                        console.error('❌ API测试失败:', err);
                        if (err.message.includes('401')) {
                          console.log('原因: API Key无效或过期');
                        } else if (err.message.includes('404')) {
                          console.log('原因: API路径不存在');
                        }
                      });
                    }}
                  >
                    全面API调试
                  </Button>
                  <Button 
                    size="small" 
                    type="primary" 
                    onClick={async () => {
                      if (!apiKey) {
                        message.warning('API Key 未配置');
                        return;
                      }
                      
                      console.log('=== 强制数据刷新 ===');
                      setSourcesLoading(true);
                      
                      try {
                        const response = await fetch('/v1/news_collector/sources?page=1&page_size=50', {
                          headers: { 'Authorization': `Bearer ${apiKey}` }
                        });
                        
                        const data = await response.json();
                        console.log('API响应:', data);
                        
                        if (data.code === 0 && data.data) {
                          const { sources = [], total = 0 } = data.data;
                          console.log(`获取到 ${sources.length} 个新闻源`);
                          
                          setSources(sources);
                          setPagination({ page: 1, pageSize: 50, total });
                          
                          message.success(`数据刷新成功！获取到 ${sources.length} 个新闻源`);
                        } else {
                          message.error(data.message || '获取数据失败');
                        }
                      } catch (error) {
                        console.error('刷新失败:', error);
                        message.error('刷新失败');
                      } finally {
                        setSourcesLoading(false);
                      }
                    }}
                  >
                    强制刷新数据
                  </Button>
                </Space>
              </div>
              
              {/* 新闻源列表 */}
              <Spin spinning={sourcesLoading}>
                {sources.length === 0 && !sourcesLoading ? (
                  <Empty 
                    description="暂无新闻源" 
                    style={{ margin: '40px 0' }}
                  >
                    <Button type="primary" onClick={openAddModal}>
                      添加第一个新闻源
                    </Button>
                  </Empty>
                ) : (
                  <div>
                    {sources.map((source, index) => (
                      <Card 
                        key={source.id || index} 
                        size="small" 
                        style={{ marginBottom: 8 }}
                        title={
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <span>{source.name}</span>
                            <Space>
                              <Button 
                                size="small" 
                                icon={<EditOutlined />}
                                onClick={() => openEditModal(source)}
                              >
                                编辑
                              </Button>
                              <Popconfirm
                                title="删除新闻源"
                                description={`确定要删除新闻源「${source.name}」吗？`}
                                onConfirm={() => source.id && handleDeleteSource(source.id)}
                                okText="确定"
                                cancelText="取消"
                              >
                                <Button 
                                  size="small" 
                                  danger
                                  icon={<DeleteOutlined />}
                                >
                                  删除
                                </Button>
                              </Popconfirm>
                            </Space>
                          </div>
                        }
                      >
                        <p><strong>URL:</strong> <a href={source.url} target="_blank" rel="noopener noreferrer">{source.url}</a></p>
                        <p><strong>状态:</strong> {source.status === 'active' ? '启用' : '禁用'}</p>
                        <p><strong>模式:</strong> {source.remark === '1' ? '精确模式' : '自动模式'}</p>
                        {source.fetch_config && Object.keys(source.fetch_config).length > 0 && (
                          <div>
                            <p><strong>CSS选择器配置:</strong></p>
                            <ul style={{ fontSize: '12px', color: '#666' }}>
                              {Object.entries(source.fetch_config).map(([key, value]) => (
                                <li key={key}>{key}: {value}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </Card>
                    ))}
                  </div>
                )}
              </Spin>
            </TabPane>
            
            <TabPane tab="抓取历史" key="history">
              <Alert
                type="error"
                message="API Key 认证失败"
                description={
                  <div>
                    <p>当前 API Key 无效或已过期，无法访问新闻源数据。</p>
                    <p><strong>解决方案</strong>：</p>
                    <ol style={{ paddingLeft: '20px', margin: 0 }}>
                      <li>访问 <a href="http://localhost:9380" target="_blank" rel="noopener noreferrer">RAGFlow 登录页面</a></li>
                      <li>重新登录您的账户</li>
                      <li>在设置中重新生成 API Key</li>
                      <li>复制新的 API Key 到此页面</li>
                    </ol>
                  </div>
                }
                showIcon
                style={{ marginBottom: 16 }}
                action={
                  <Button 
                    size="small" 
                    type="primary"
                    onClick={() => window.open('http://localhost:9380', '_blank')}
                  >
                    去登录
                  </Button>
                }
              />
              <Alert
                type="info"
                message="抓取结果存储位置"
                description={
                  <div>
                    <p>抓取结果会存储在以下位置：</p>
                    <ul style={{ marginBottom: 0 }}>
                      <li><strong>文件系统</strong>：项目根目录下的 <code>crawl4ai_data</code> 文件夹</li>
                      <li><strong>数据库</strong>：内容表和哈希表，用于去重和查询</li>
                      <li><strong>后台日志</strong>：抓取进度和结果信息</li>
                    </ul>
                  </div>
                }
                style={{ marginBottom: 16 }}
              />
              
              <Space direction="vertical" style={{ width: '100%' }}>
                <div>
                  <h4>查看抓取结果</h4>
                  <Space>
                    <Button 
                      icon={<SyncOutlined />}
                      onClick={() => {
                        if (apiKey) {
                          // 直接调用查询数据库的API
                          console.log('开始查询数据库内容...');
                          
                          console.log('=== 直接API查询调试 ===');
                          
                          // 同时获取用户信息和新闻源数据
                          Promise.all([
                            fetch('/v1/user/info', { headers: { 'Authorization': `Bearer ${apiKey}` } }),
                            fetch('/v1/news_collector/sources?page=1&page_size=100', { headers: { 'Authorization': `Bearer ${apiKey}` } })
                          ])
                          .then(([userRes, sourcesRes]) => Promise.all([userRes.json(), sourcesRes.json()]))
                          .then(([userData, sourcesData]) => {
                            console.log('用户信息:', userData);
                            console.log('新闻源查询结果:', sourcesData);
                            
                            const currentTenantId = userData.data?.tenant_id;
                            const dbTenantId = 'b6931dc26e7511f0979feeeb2f257f';
                            
                            console.log(`前端 tenant_id: ${currentTenantId}`);
                            console.log(`数据库 tenant_id: ${dbTenantId}...`);
                            
                            if (sourcesData.data && sourcesData.data.sources) {
                              console.log(`✅ 查询成功！发现 ${sourcesData.data.sources.length} 个新闻源`);
                              sourcesData.data.sources.forEach((s: any, i: number) => {
                                console.log(`${i + 1}. ${s.name} - ${s.url} (${s.status})`);
                              });
                            } else {
                              console.log('❌ 查询结果为空');
                              if (currentTenantId && !currentTenantId.startsWith(dbTenantId)) {
                                console.log('原因: tenant_id 不匹配');
                                console.log('解决方案: 需要使用正确的用户账户或API Key');
                              }
                            }
                          })
                          .catch(err => console.error('查询失败:', err));
                        } else {
                          message.warning('请先配置API Key');
                        }
                      }}
                    >
                      直接查询数据库
                    </Button>
                    <Button 
                      danger
                      onClick={() => {
                        if (apiKey) {
                          // 这里可以调用 deleteAllContents API
                          message.warning('清空功能开发中...');
                          console.log('可调用 API: DELETE /v1/news_collector/contents');
                        } else {
                          message.warning('请先配置API Key');
                        }
                      }}
                    >
                      清空抓取历史
                    </Button>
                  </Space>
                </div>
                
                <div>
                  <h4>抓取结果文件位置</h4>
                  <Alert
                    type="success"
                    message={
                      <div>
                        <p><strong>文件存储路径</strong>：<code>/home/zyx/ragflow0909/ragflow/crawl4ai_data/</code></p>
                        <p><strong>后端日志</strong>：可在后台服务控制台查看抓取进度</p>
                      </div>
                    }
                  />
                </div>
                
                <div>
                  <h4>API 调用示例</h4>
                  <div style={{ background: '#f6f8fa', padding: '12px', borderRadius: '6px', fontFamily: 'monospace', fontSize: '12px' }}>
                    <div># 查询抓取记录</div>
                    <div>GET /v1/news_collector/contents/hashes?page=1&page_size=10</div>
                    <br />
                    <div># 清空抓取历史</div>
                    <div>DELETE /v1/news_collector/contents</div>
                  </div>
                </div>
              </Space>
            </TabPane>
          </Tabs>
        </Card>

        {/* 添加/编辑模态框 */}
        <Modal
          title={editingSource ? '编辑新闻源' : '添加新闻源'}
          open={formModalVisible}
          onCancel={closeModal}
          footer={null}
          width={600}
        >
          <NewsCollectorForm
            initialValues={editingSource || {}}
            datasets={datasets}
            onSubmit={editingSource ? handleEditSource : handleAddSource}
            onCancel={closeModal}
            loading={loading}
          />
        </Modal>
        
        {/* API Key 配置模态框 */}
        <Modal
          title="配置 API Key"
          open={apiKeyModalVisible}
          onOk={handleSaveApiKey}
          onCancel={closeApiKeyModal}
          okText="保存并测试"
          cancelText="取消"
          width={600}
        >
          <div style={{ marginBottom: 16 }}>
            <p style={{ marginBottom: 8, color: '#666' }}>
              请输入您的 RAGFlow API Key：
            </p>
            <Input.TextArea
              placeholder="例如: ragflow-ZmY3OTEzMzZmNGVkMTExZWZh..."
              value={tempApiKey}
              onChange={(e) => setTempApiKey(e.target.value)}
              rows={3}
              style={{ resize: 'none' }}
            />
            {tempApiKey && (
              <div style={{ marginTop: 8, fontSize: '12px', color: '#666' }}>
                <p>长度: {tempApiKey.length} 字符</p>
                <p>格式: {/^[a-zA-Z0-9\-_]{20,}$/.test(tempApiKey) ? '✅ 正常' : '❌ 可能异常'}</p>
              </div>
            )}
          </div>
          
          <Space direction="vertical" style={{ width: '100%' }}>
            <Alert
              type="info"
              message="获取 API Key 的方法"
              description={
                <div>
                  <p>1. 访问 <a href="http://localhost:9380" target="_blank" rel="noopener noreferrer">RAGFlow 系统</a></p>
                  <p>2. 登录您的账户</p>
                  <p>3. 在设置页面生成或查看 API Key</p>
                  <p>4. 复制完整的 API Key 到此处</p>
                </div>
              }
            />
            
            <Alert
              type="warning"
              message="注意事项"
              description={
                <div>
                  <p>• 确保 API Key 没有多余的空格或换行符</p>
                  <p>• API Key 通常以 "ragflow-" 开头</p>
                  <p>• 长度一般在 40-100 字符之间</p>
                  <p>• 保存后会自动测试连接</p>
                </div>
              }
            />
          </Space>
        </Modal>
      </div>
    );
  } catch (error) {
    console.error('组件渲染错误:', error);
    return (
      <div style={{ padding: '32px 16px' }}>
        <Alert
          type="error"
          message="组件加载失败"
          description="请刷新页面或联系管理员"
        />
      </div>
    );
  }
};

export default NewsCollector;