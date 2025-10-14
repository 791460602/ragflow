import React, { useState, useEffect } from 'react';
import { Button, Card, Empty, message, Spin, Space, Select, Input, Alert, Tabs, Modal, Popconfirm, Form, InputNumber, Tooltip } from 'antd';
import { PlusOutlined, SyncOutlined, KeyOutlined, EditOutlined, DeleteOutlined, QuestionCircleOutlined } from '@ant-design/icons';
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
  checkApiHealth,
  hasAuthToken,
  getAuthType
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
  
  // 抓取配置模态框状态
  const [crawlConfigModalVisible, setCrawlConfigModalVisible] = useState(false);
  const [crawlConfigForm] = Form.useForm();
  
  // 获取认证头（优先使用登录态）
  const getAuthorizationHeader = () => {
    const authorization = localStorage.getItem('Authorization');
    if (authorization) return authorization;
    if (apiKey) return `Bearer ${apiKey}`;
    const storedApiKey = localStorage.getItem('apiKey');
    if (storedApiKey) return `Bearer ${storedApiKey}`;
    return '';
  };
  
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
    try {
      console.log('开始加载知识库列表...');
      const res = await getDatasets(apiKey);
      
      console.log('知识库API完整响应:', res);
      console.log('响应数据结构:', res?.data);
      
      // 安全检查响应数据 - 兼容多种响应格式
      if (res && res.data) {
        let datasets = [];
        
        // 格式1: { code: 0, data: [...] } - 新闻收集器专用API格式
        if (Array.isArray(res.data.data)) {
          datasets = res.data.data;
        } 
        // 格式2: { code: 0, data: {...} } - SDK API格式  
        else if (res.data.data && Array.isArray(res.data.data.data)) {
          datasets = res.data.data.data;
        }
        // 格式3: 直接是数组
        else if (Array.isArray(res.data)) {
          datasets = res.data;
        }
        
        setDatasets(datasets);
        console.log('加载知识库列表成功:', datasets.length, '个知识库');
        if (datasets.length > 0) {
          console.log('前3个知识库:', datasets.slice(0, 3));
        }
      } else {
        console.warn('知识库API响应格式异常:', res);
        setDatasets([]);
      }
    } catch (error: any) {
      console.error('加载知识库列表失败:', error);
      console.error('错误详情:', error.response);
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
      const response = await getNewsSources(cleanParams, apiKey);
      console.log('API响应原始数据:', response);
      
      // 安全检查响应数据
      if (response && response.data) {
        const { sources, total, page, page_size } = response.data.data;
        const sourcesList = Array.isArray(sources) ? sources : [];
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

  // 显示抓取配置对话框
  const handleCrawlNews = () => {
    const activeSourceIds = sources.filter(s => s.status === 'active' && s.id).map(s => s.id!);
    
    if (activeSourceIds.length === 0) {
      message.warning('没有可抓取的活跃新闻源');
      return;
    }
    
    // 重置表单为默认值并显示模态框
    crawlConfigForm.setFieldsValue({
      depth: 2,
      max_pages_per_source: 10
    });
    setCrawlConfigModalVisible(true);
  };

  // 执行实际的抓取操作
  const executeCrawl = async () => {
    try {
      const values = await crawlConfigForm.validateFields();
      const activeSourceIds = sources.filter(s => s.status === 'active' && s.id).map(s => s.id!);
      
      setCrawlConfigModalVisible(false);
      setLoading(true);
      
      await crawlFromPost({
        source_ids: activeSourceIds,
        depth: values.depth,
        max_pages_per_source: values.max_pages_per_source,
        kb_id: values.kb_id  // 添加知识库ID
      }, apiKey);
      
      const selectedDataset = datasets.find(ds => ds.id === values.kb_id);
      message.success(`已启动后台抓取任务，内容将上传到知识库「${selectedDataset?.name || values.kb_id}」`);
      console.log('启动抓取任务成功:', { 
        sourceIds: activeSourceIds, 
        depth: values.depth, 
        maxPages: values.max_pages_per_source,
        kbId: values.kb_id,
        kbName: selectedDataset?.name
      });
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
    if (!data.name || !data.url) {
      message.error('新闻源名称和URL不能为空');
      return;
    }
    
    setLoading(true);
    try {
      console.log('=== 开始创建新闻源 ===');
      console.log('创建数据:', data);
      console.log('当前列表数量:', sources.length);
      
      const response = await createNewsSource(data, apiKey);
      console.log('创建响应完整数据:', response);
      console.log('创建响应状态:', response.status);
      console.log('创建响应内容:', response.data);
      
      if (response.status === 200 || response.status === 201) {
        message.success('新闻源创建成功');
        closeModal(); // 关闭弹窗
        
        // 立即刷新列表
        console.log('刷新新闻源列表...');
        await loadSources(undefined, true);
        console.log('列表刷新完成');
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
    if (!editingSource?.id) {
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
      const response = await updateNewsSource(editingSource.id, data, apiKey);
      console.log('更新响应:', response);
      
      message.success('新闻源更新成功');
      closeModal(); // 关闭弹窗
      
      // 立即刷新列表
      console.log('刷新新闻源列表...');
      await loadSources(undefined, true);
      console.log('列表刷新完成');
      
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
    if (!id) {
      message.error('无效的新闻源ID');
      return;
    }
    
    try {
      console.log('删除新闻源:', id);
      const response = await deleteNewsSource(id, apiKey);
      console.log('删除响应:', response);
      
      message.success('新闻源删除成功');
      
      // 立即刷新列表
      console.log('刷新新闻源列表...');
      await loadSources(undefined, true);
      console.log('列表刷新完成');
      
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
    console.log('=== API 状态检查开始 ===');
    
    // 检查认证方式
    const authType = getAuthType();
    console.log('当前认证方式:', authType);
    
    if (authType === 'login') {
      console.log('✅ 使用主系统登录态');
    } else if (authType === 'apikey') {
      console.log('✅ 使用手动配置的 API Key');
      if (apiKey) {
        console.log('API Key 长度:', apiKey.length);
        console.log('API Key 前10位:', apiKey.substring(0, 10) + '...');
      }
    } else {
      console.log('❌ 未找到任何认证信息');
      setApiStatus('error');
      return;
    }
    
    setApiStatus('checking');
    try {
      console.log('调用 checkApiHealth...');
      const result = await checkApiHealth(apiKey);
      console.log('checkApiHealth 结果:', result);
      
      if (result.status === 'ok') {
        setApiStatus('ok');
        console.log('✅ API状态正常');
        message.success(`认证成功 (${authType === 'login' ? '登录态' : 'API Key'})`);
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
        errorMsg = '认证失败，请重新登录或配置 API Key';
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
    const authType = getAuthType();
    console.log('组件加载，认证方式:', authType);
    
    if (hasAuthToken()) {
      // 有认证信息（登录态或 API Key），检查API状态
      checkApiStatus();
    } else {
      console.warn('未找到认证信息，跳过数据加载');
      setApiStatus('error');
      setSources([]);
      setDatasets([]);
      setPagination({ page: 1, pageSize: 10, total: 0 });
    }
  }, [apiKey]); // 依赖 apiKey，当手动配置时重新检查

  // 监听API状态变化，当API变为正常时加载初始数据
  useEffect(() => {
    if (apiStatus === 'ok') {
      console.log('API状态正常，加载初始数据');
      loadDatasets().catch(err => {
        console.error('加载数据集失败:', err);
      });
      
      // 只在没有搜索条件时加载全部数据
      if (!searchKeyword && !statusFilter) {
        loadSources().catch(err => {
          console.error('加载新闻源失败:', err);
        });
      }
    }
  }, [apiStatus]);

  // 监听搜索条件变化 - 重要：清空搜索也会触发
  useEffect(() => {
    // 只有在API状态正常且有认证信息时才响应搜索
    if (hasAuthToken() && apiStatus === 'ok') {
      console.log('搜索条件变化，重新加载数据:', { searchKeyword, statusFilter });
      const timeoutId = setTimeout(() => {
        loadSources({ name: searchKeyword, status: statusFilter }).catch(err => {
          console.error('搜索加载失败:', err);
        });
      }, 300); // 防抖：延迟300ms执行，避免频繁请求
      
      return () => clearTimeout(timeoutId);
    }
  }, [searchKeyword, statusFilter]);

  try {
    return (
      <div className="mx-8">
        {/* API状态警告 */}
        {!hasAuthToken() && (
          <Alert
            type="warning"
            showIcon
            message="需要身份认证"
            description={
              <div>
                <p>使用新闻源管理功能需要身份认证，有两种方式：</p>
                <ul style={{ marginBottom: 0, paddingLeft: '20px' }}>
                  <li><strong>推荐</strong>：登录 RAGFlow 主系统后自动认证</li>
                  <li>手动配置 API Key（适用于独立部署场景）</li>
                </ul>
              </div>
            }
            style={{ marginBottom: 16 }}
            action={
              <Button size="small" type="primary" onClick={openApiKeyModal}>
                配置 API Key
              </Button>
            }
          />
        )}
        
        {hasAuthToken() && apiStatus === 'error' && (
          <Alert
            type="error"
            showIcon
            message="认证失败或服务连接异常"
            description={
              <div>
                <p>当前认证方式：<strong>{getAuthType() === 'login' ? '主系统登录态' : 'API Key'}</strong></p>
                <p>可能原因：认证信息无效、过期，或新闻收集器 API 接口不可用。</p>
              </div>
            }
            action={
              <Space>
                {getAuthType() === 'apikey' && (
                  <Button size="small" onClick={openApiKeyModal}>
                    重新配置 API Key
                  </Button>
                )}
                {getAuthType() === 'login' && (
                  <Button size="small" onClick={() => window.location.href = '/login'}>
                    重新登录
                  </Button>
                )}
                <Button size="small" onClick={checkApiStatus}>
                  重新检查
                </Button>
              </Space>
            }
            style={{ marginBottom: 16 }}
          />
        )}
        
        {hasAuthToken() && apiStatus === 'checking' && (
          <Alert
            type="info"
            showIcon
            message={`正在验证身份 (${getAuthType() === 'login' ? '登录态' : 'API Key'})...`}
            style={{ marginBottom: 16 }}
          />
        )}
        
        {/* 头部区域 */}
        <div className="flex justify-between items-center mb-6">
          <div>
            <h2 className="text-2xl font-bold mb-2">新闻收集器</h2>
            <p className="text-gray-600 mb-1">
              配置新闻源，智能抓取网页内容。支持自动模式和精确模式。
            </p>
            {hasAuthToken() && (
              <p className="text-green-600 text-xs">
                ✅ 已认证 ({getAuthType() === 'login' ? '主系统登录态' : `API Key: ${apiKey?.substring(0, 8)}...`})
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
              type="primary" 
              icon={<PlusOutlined />}
              onClick={openAddModal}
              disabled={!hasAuthToken()}
            >
              添加新闻源
            </Button>
            <Button 
              type="primary" 
              icon={<SyncOutlined />}
              onClick={handleCrawlNews}
              loading={loading}
              disabled={!hasAuthToken()}
            >
              即时抓取
            </Button>
          </Space>
        </div>

        {/* 主要内容区域 - 可滚动 */}
        <div className="h-[calc(100dvh-220px)] overflow-auto scrollbar-thin">
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
          </Tabs>
          </Card>
        </div>

        {/* 添加/编辑模态框 */}
        <Modal
          title={editingSource ? '编辑新闻源' : '添加新闻源'}
          open={formModalVisible}
          onCancel={closeModal}
          footer={null}
          width={600}
        >
          <NewsCollectorForm
            initialData={editingSource || undefined}
            onSubmit={editingSource ? handleEditSource : handleAddSource}
            onCancel={closeModal}
            loading={loading}
            isEditing={!!editingSource}
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
              type="success"
              message="推荐方式"
              description={
                <div>
                  <p><strong>如果您已登录 RAGFlow 主系统，无需配置 API Key</strong></p>
                  <p>系统会自动使用您的登录态进行认证。</p>
                </div>
              }
            />
            
            <Alert
              type="info"
              message="手动配置 API Key（适用于独立部署场景）"
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
                  <p>• 手动配置的 API Key 优先级低于登录态</p>
                </div>
              }
            />
          </Space>
        </Modal>

        {/* 抓取配置模态框 */}
        <Modal
          title="配置抓取参数"
          open={crawlConfigModalVisible}
          onOk={executeCrawl}
          onCancel={() => setCrawlConfigModalVisible(false)}
          okText="开始抓取"
          cancelText="取消"
          width={500}
        >
          <Form
            form={crawlConfigForm}
            layout="vertical"
            initialValues={{
              depth: 2,
              max_pages_per_source: 10,
              kb_id: datasets.length === 1 ? datasets[0].id : undefined
            }}
          >
            <Form.Item
              name="kb_id"
              label={
                <span>
                  目标知识库
                  <Tooltip title="抓取的新闻内容将自动上传到选定的知识库并解析">
                    <QuestionCircleOutlined style={{ marginLeft: 8, color: '#1890ff' }} />
                  </Tooltip>
                </span>
              }
              rules={[
                { required: true, message: '请选择目标知识库' }
              ]}
            >
              <Select
                placeholder="选择知识库"
                showSearch
                optionFilterProp="children"
                style={{ width: '100%' }}
              >
                {datasets.map(ds => (
                  <Select.Option key={ds.id} value={ds.id}>
                    {ds.name}
                  </Select.Option>
                ))}
              </Select>
            </Form.Item>

            <Form.Item
              name="depth"
              label={
                <span>
                  抓取深度
                  <Tooltip title="从新闻源首页开始，递归抓取的链接层级深度">
                    <QuestionCircleOutlined style={{ marginLeft: 8, color: '#1890ff' }} />
                  </Tooltip>
                </span>
              }
              rules={[
                { required: true, message: '请输入抓取深度' },
                { type: 'number', min: 1, max: 5, message: '抓取深度范围：1-5' }
              ]}
            >
              <InputNumber
                min={1}
                max={5}
                style={{ width: '100%' }}
                placeholder="建议：1-3层"
              />
            </Form.Item>

            <Form.Item
              name="max_pages_per_source"
              label={
                <span>
                  每源最大页数
                  <Tooltip title="每个新闻源最多抓取的页面数量">
                    <QuestionCircleOutlined style={{ marginLeft: 8, color: '#1890ff' }} />
                  </Tooltip>
                </span>
              }
              rules={[
                { required: true, message: '请输入最大页数' },
                { type: 'number', min: 1, max: 1000, message: '最大页数范围：1-1000' }
              ]}
            >
              <InputNumber
                min={1}
                max={1000}
                style={{ width: '100%' }}
                placeholder="建议：10-50页"
              />
            </Form.Item>

            <Alert
              type="info"
              message="抓取说明"
              description={
                <div>
                  <p><strong>目标知识库：</strong>抓取的新闻内容将自动上传到选定的知识库并解析，解析完成后可用于检索和问答</p>
                  <p style={{ marginTop: 8 }}><strong>抓取深度：</strong>控制从首页开始的链接递归层级</p>
                  <ul style={{ marginLeft: 20, marginTop: 4 }}>
                    <li>深度 1：仅抓取首页</li>
                    <li>深度 2：首页 + 首页链接的页面</li>
                    <li>深度 3：再深入一层</li>
                  </ul>
                  <p style={{ marginTop: 8 }}><strong>每源最大页数：</strong>限制单个新闻源的抓取数量，避免过度抓取</p>
                  <p style={{ marginTop: 8, color: '#ff9800' }}>⚠️ 深度和页数越大，抓取时间越长</p>
                </div>
              }
              style={{ marginTop: 16 }}
            />
          </Form>
        </Modal>
      </div>
    );
  } catch (error) {
    console.error('组件渲染错误:', error);
    return (
      <div className="mx-8">
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