import {
  BorderOutlined,
  CheckSquareOutlined,
  DeleteOutlined,
  DownOutlined,
  EditOutlined,
  ImportOutlined,
  KeyOutlined,
  PlusOutlined,
  RightOutlined,
  SyncOutlined,
} from '@ant-design/icons';
import {
  Alert,
  Button,
  Card,
  Checkbox,
  Collapse,
  Empty,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Select,
  Space,
  Spin,
  Switch,
  Tabs,
  Tag,
  message,
} from 'antd';
import React, { useEffect, useState } from 'react';
import NewsCollectorForm from './NewsCollectorForm';
import {
  SOURCE_TYPE_CONFIG,
  checkApiHealth,
  crawlFromPost,
  createNewsSource,
  createTarget,
  deleteNewsSource,
  getAuthType,
  getDatasets,
  getNewsSourceGroups,
  hasAuthToken,
  importNewsSources,
  topicSearchCrawl,
  updateNewsSource,
  updateTarget,
  type CrawlTarget,
} from './NewsCollectorService';
import TargetForm from './TargetForm';
import TargetList from './TargetList';
import TaskLogsList from './TaskLogsList';

const { TabPane } = Tabs;
const { Search, TextArea } = Input;
const { Panel } = Collapse;

type SourceType = 'policy' | 'news' | 'other';

interface NewsSource {
  id?: string;
  name: string;
  url: string;
  status?: string;
  remark?: string;
  fetch_config?: Record<string, any>;
  source_type?: SourceType;
  region?: string;
  issuer?: string;
  policy_theme?: string[];
}

interface GroupedSources {
  group: string;
  sources: NewsSource[];
}

const getApiKey = () => {
  try {
    return localStorage.getItem('apiKey') || '';
  } catch (error) {
    return '';
  }
};

const NewsCollector: React.FC = () => {
  // 分组数据状态
  const [groupedSources, setGroupedSources] = useState<GroupedSources[]>([]);
  const [expandedGroups, setExpandedGroups] = useState<string[]>([]);
  const [datasets, setDatasets] = useState<{ id: string; name: string }[]>([]);
  const [loading, setLoading] = useState(false);
  const [sourcesLoading, setSourcesLoading] = useState(false);
  const [formModalVisible, setFormModalVisible] = useState(false);
  const [searchKeyword, setSearchKeyword] = useState('');
  const [apiStatus, setApiStatus] = useState<'checking' | 'ok' | 'error'>(
    'checking',
  );
  const [apiKey, setApiKey] = useState(getApiKey());
  const [apiKeyModalVisible, setApiKeyModalVisible] = useState(false);
  const [tempApiKey, setTempApiKey] = useState('');
  const [crawlConfigModalVisible, setCrawlConfigModalVisible] = useState(false);
  const [crawlConfigForm] = Form.useForm();
  const [crawlMode, setCrawlMode] = useState<'instant' | 'topic'>('instant');
  const [importModalVisible, setImportModalVisible] = useState(false);
  const [importJsonText, setImportJsonText] = useState('');
  const [importLoading, setImportLoading] = useState(false);
  const [editingSource, setEditingSource] = useState<NewsSource | null>(null);
  const [selectedSourceIds, setSelectedSourceIds] = useState<string[]>([]);

  // Target 相关状态
  const [targetFormModalVisible, setTargetFormModalVisible] = useState(false);
  const [editingTarget, setEditingTarget] = useState<CrawlTarget | null>(null);
  const [activeTab, setActiveTab] = useState('sources');
  const [targetRefreshTrigger, setTargetRefreshTrigger] = useState(0); // 添加刷新触发器

  // 计算总数
  const totalSources = groupedSources.reduce(
    (sum, g) => sum + g.sources.length,
    0,
  );
  const activeSources = groupedSources.reduce(
    (sum, g) => sum + g.sources.filter((s) => s.status === 'active').length,
    0,
  );
  const selectedCount = selectedSourceIds.length;

  // API Key 相关函数
  const saveApiKey = (newApiKey: string) => {
    try {
      localStorage.setItem('apiKey', newApiKey);
      setApiKey(newApiKey);
      message.success('API Key 保存成功');
    } catch (error) {
      message.error('保存API Key失败');
    }
  };

  const openApiKeyModal = () => {
    setTempApiKey(apiKey);
    setApiKeyModalVisible(true);
  };

  const closeApiKeyModal = () => {
    setApiKeyModalVisible(false);
    setTempApiKey('');
  };

  const handleSaveApiKey = async () => {
    if (!tempApiKey.trim()) {
      message.warning('请输入有效的API Key');
      return;
    }
    saveApiKey(tempApiKey.trim());
    closeApiKeyModal();
    setTimeout(() => checkApiStatus(), 500);
  };

  // 加载知识库列表
  const loadDatasets = async () => {
    try {
      const res = await getDatasets(apiKey);
      if (res?.data) {
        let datasets = [];
        if (Array.isArray(res.data.data)) {
          datasets = res.data.data;
        } else if (res.data.data && Array.isArray(res.data.data.data)) {
          datasets = res.data.data.data;
        } else if (Array.isArray(res.data)) {
          datasets = res.data;
        }
        setDatasets(datasets);
      }
    } catch (error) {
      setDatasets([]);
    }
  };

  // 加载分组数据
  const loadGroupedSources = async () => {
    setSourcesLoading(true);
    try {
      const response = await getNewsSourceGroups(apiKey);
      if (response?.data?.data?.groups) {
        const groups = response.data.data.groups;
        setGroupedSources(groups);
        // 默认展开第一个分组
        if (groups.length > 0 && expandedGroups.length === 0) {
          setExpandedGroups([groups[0].group]);
        }
      } else {
        setGroupedSources([]);
      }
    } catch (error: any) {
      console.error('加载分组数据失败:', error);
      setGroupedSources([]);
    } finally {
      setSourcesLoading(false);
    }
  };

  // 事件处理
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

  // 新闻源选择相关函数
  const handleSelectSource = (sourceId: string, checked: boolean) => {
    if (checked) {
      setSelectedSourceIds((prev) => [...prev, sourceId]);
    } else {
      setSelectedSourceIds((prev) => prev.filter((id) => id !== sourceId));
    }
  };

  const handleSelectAll = () => {
    const allActiveSourceIds = groupedSources
      .flatMap((g) => g.sources)
      .filter((s) => s.status === 'active' && s.id)
      .map((s) => s.id!);
    setSelectedSourceIds(allActiveSourceIds);
  };

  const handleDeselectAll = () => {
    setSelectedSourceIds([]);
  };

  const handleSelectGroup = (group: GroupedSources, checked: boolean) => {
    const groupSourceIds = group.sources
      .filter((s) => s.status === 'active' && s.id)
      .map((s) => s.id!);

    if (checked) {
      setSelectedSourceIds((prev) => [
        ...new Set([...prev, ...groupSourceIds]),
      ]);
    } else {
      setSelectedSourceIds((prev) =>
        prev.filter((id) => !groupSourceIds.includes(id)),
      );
    }
  };

  const handleCrawlNews = async () => {
    if (selectedSourceIds.length === 0) {
      message.warning('请先选择要抓取的新闻源');
      return;
    }

    if (datasets.length === 0) {
      await loadDatasets();
    }

    crawlConfigForm.setFieldsValue({
      depth: 2,
      max_pages_per_source: 10,
      parse: false,
    });
    setCrawlConfigModalVisible(true);
  };

  const executeCrawl = async () => {
    try {
      const values = await crawlConfigForm.validateFields();

      if (selectedSourceIds.length === 0) {
        message.warning('请先选择要抓取的新闻源');
        return;
      }

      setCrawlConfigModalVisible(false);
      setLoading(true);

      const selectedDataset = datasets.find((ds) => ds.id === values.kb_id);

      if (crawlMode === 'instant') {
        await crawlFromPost(
          {
            source_ids: selectedSourceIds,
            depth: values.depth,
            max_pages_per_source: values.max_pages_per_source,
            kb_id: values.kb_id,
            parse: values.parse || false,
          },
          apiKey,
        );
        message.success(
          `已启动后台抓取任务，共 ${selectedSourceIds.length} 个新闻源，内容将上传到知识库「${selectedDataset?.name || values.kb_id}」`,
        );
      } else {
        await topicSearchCrawl(
          {
            source_ids: selectedSourceIds,
            keywords: values.keywords || [],
            max_depth: values.max_depth || 2,
            max_pages_per_source: values.max_pages_per_source || 30,
            max_crawl_pages_per_source:
              values.max_crawl_pages_per_source || 100,
            score_threshold: values.score_threshold || 0.3,
            kb_id: values.kb_id,
            parse: values.parse || false,
          },
          apiKey,
        );
        message.success(
          `已启动主题搜索抓取任务，共 ${selectedSourceIds.length} 个新闻源，内容将上传到知识库「${selectedDataset?.name || values.kb_id}」`,
        );
      }
    } catch (error: any) {
      message.error(error.response?.data?.message || '抓取失败');
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
      const response = await createNewsSource(data, apiKey);
      if (response.status === 200 || response.status === 201) {
        message.success('新闻源创建成功');
        closeModal();
        await loadGroupedSources();
      }
    } catch (error: any) {
      message.error(error.response?.data?.message || '创建失败');
    } finally {
      setLoading(false);
    }
  };

  const handleEditSource = async (data: NewsSource) => {
    if (!editingSource?.id) return;
    if (!data.name || !data.url) {
      message.error('新闻源名称和URL不能为空');
      return;
    }
    setLoading(true);
    try {
      await updateNewsSource(editingSource.id, data, apiKey);
      message.success('新闻源更新成功');
      closeModal();
      await loadGroupedSources();
    } catch (error: any) {
      message.error(error.response?.data?.message || '更新失败');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteSource = async (id: string) => {
    if (!id) return;
    try {
      await deleteNewsSource(id, apiKey);
      message.success('新闻源删除成功');
      await loadGroupedSources();
    } catch (error: any) {
      message.error(error.response?.data?.message || '删除失败');
    }
  };

  const checkApiStatus = async () => {
    const authType = getAuthType();
    if (authType === 'none') {
      setApiStatus('error');
      return;
    }
    setApiStatus('checking');
    try {
      const result = await checkApiHealth(apiKey);
      if (result.status === 'ok') {
        setApiStatus('ok');
        message.success(
          `认证成功 (${authType === 'login' ? '登录态' : 'API Key'})`,
        );
      } else {
        setApiStatus('error');
        message.error('API 连接异常');
      }
    } catch (error) {
      setApiStatus('error');
      message.error('API 连接失败');
    }
  };

  // 生命周期
  useEffect(() => {
    if (hasAuthToken()) {
      checkApiStatus();
    } else {
      setApiStatus('error');
    }
  }, [apiKey]);

  useEffect(() => {
    if (apiStatus === 'ok') {
      loadDatasets();
      loadGroupedSources();
    }
  }, [apiStatus]);

  // 批量导入
  const handleImport = async () => {
    if (!importJsonText.trim()) {
      message.warning('请输入要导入的JSON数据');
      return;
    }
    let sourcesToImport: Partial<NewsSource>[];
    try {
      const parsed = JSON.parse(importJsonText);
      sourcesToImport = Array.isArray(parsed) ? parsed : [parsed];
    } catch (e) {
      message.error('JSON格式错误');
      return;
    }
    for (let i = 0; i < sourcesToImport.length; i++) {
      if (!sourcesToImport[i].name || !sourcesToImport[i].url) {
        message.error(`第 ${i + 1} 条数据缺少 name 或 url`);
        return;
      }
    }
    setImportLoading(true);
    try {
      const response = await importNewsSources(sourcesToImport, apiKey);
      const data = response.data?.data;
      const createdCount = data?.created_count || data?.sources?.length || 0;
      if (createdCount > 0) {
        message.success(`成功导入 ${createdCount} 个新闻源`);
      } else {
        message.success('导入完成');
      }
      setImportModalVisible(false);
      setImportJsonText('');
      await loadGroupedSources();
    } catch (error: any) {
      message.error(error.response?.data?.message || '批量导入失败');
    } finally {
      setImportLoading(false);
    }
  };

  // 过滤搜索
  const getFilteredGroups = () => {
    if (!searchKeyword.trim()) return groupedSources;
    return groupedSources
      .map((g) => ({
        ...g,
        sources: g.sources.filter(
          (s) =>
            s.name.toLowerCase().includes(searchKeyword.toLowerCase()) ||
            s.url.toLowerCase().includes(searchKeyword.toLowerCase()) ||
            s.region?.toLowerCase().includes(searchKeyword.toLowerCase()) ||
            s.issuer?.toLowerCase().includes(searchKeyword.toLowerCase()),
        ),
      }))
      .filter((g) => g.sources.length > 0);
  };

  const filteredGroups = getFilteredGroups();

  const importExampleJson = `[
  {
    "name": "国家发改委政策",
    "url": "https://www.ndrc.gov.cn",
    "source_type": "policy",
    "region": "全国",
    "issuer": "国家发展和改革委员会",
    "policy_theme": ["分时电价", "能源政策"],
    "status": "active"
  }
]`;

  // 渲染单个新闻源卡片
  const renderSourceCard = (source: NewsSource) => {
    const isSelected = selectedSourceIds.includes(source.id || '');
    const isActive = source.status === 'active';

    return (
      <Card
        key={source.id}
        size="small"
        style={{ marginBottom: 8 }}
        title={
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <Space>
              {isActive && (
                <Checkbox
                  checked={isSelected}
                  onChange={(e) =>
                    source.id && handleSelectSource(source.id, e.target.checked)
                  }
                />
              )}
              <span>{source.name}</span>
              <Tag color={isActive ? 'success' : 'default'}>
                {isActive ? '启用' : '禁用'}
              </Tag>
            </Space>
            <Space>
              <Button
                size="small"
                icon={<EditOutlined />}
                onClick={() => openEditModal(source)}
              >
                编辑
              </Button>
              <Popconfirm
                title="确定删除此新闻源？"
                onConfirm={() => source.id && handleDeleteSource(source.id)}
                okText="确定"
                cancelText="取消"
              >
                <Button size="small" danger icon={<DeleteOutlined />}>
                  删除
                </Button>
              </Popconfirm>
            </Space>
          </div>
        }
      >
        <p>
          <strong>URL:</strong>{' '}
          <a href={source.url} target="_blank" rel="noopener noreferrer">
            {source.url}
          </a>
        </p>
        <Space wrap>
          <span>
            <strong>模式:</strong>{' '}
            <Tag color={source.remark === '1' ? 'green' : 'blue'}>
              {source.remark === '1' ? '精确' : '自动'}
            </Tag>
          </span>
        </Space>
        {source.source_type === 'policy' &&
          (source.region || source.issuer || source.policy_theme?.length) && (
            <div
              style={{
                background: '#fff7e6',
                padding: '8px 12px',
                borderRadius: 4,
                marginTop: 8,
                fontSize: 13,
              }}
            >
              {source.region && (
                <span style={{ marginRight: 16 }}>📍 {source.region}</span>
              )}
              {source.issuer && (
                <span style={{ marginRight: 16 }}>🏛️ {source.issuer}</span>
              )}
              {source.policy_theme && source.policy_theme.length > 0 && (
                <div style={{ marginTop: 4 }}>
                  🏷️{' '}
                  {source.policy_theme.map((t) => (
                    <Tag key={t} color="orange" style={{ marginRight: 4 }}>
                      {t}
                    </Tag>
                  ))}
                </div>
              )}
            </div>
          )}
      </Card>
    );
  };

  // 渲染分组面板头部
  const renderGroupHeader = (group: GroupedSources) => {
    const config = SOURCE_TYPE_CONFIG[
      group.group as keyof typeof SOURCE_TYPE_CONFIG
    ] || { label: group.group, color: 'default' };
    const activeCount = group.sources.filter(
      (s) => s.status === 'active',
    ).length;
    const activeSourceIds = group.sources
      .filter((s) => s.status === 'active' && s.id)
      .map((s) => s.id!);
    const selectedInGroup = activeSourceIds.filter((id) =>
      selectedSourceIds.includes(id),
    ).length;
    const allGroupSelected =
      activeSourceIds.length > 0 && selectedInGroup === activeSourceIds.length;
    const someGroupSelected =
      selectedInGroup > 0 && selectedInGroup < activeSourceIds.length;

    return (
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          width: '100%',
        }}
      >
        <Space>
          {activeSourceIds.length > 0 && (
            <Checkbox
              checked={allGroupSelected}
              indeterminate={someGroupSelected}
              onChange={(e) => {
                e.stopPropagation();
                handleSelectGroup(group, e.target.checked);
              }}
              onClick={(e) => e.stopPropagation()}
            />
          )}
          <Tag
            color={config.color}
            style={{ fontSize: 14, padding: '2px 12px' }}
          >
            {config.label}
          </Tag>
          <span style={{ color: '#666' }}>
            {group.sources.length} 个源 ({activeCount} 个启用
            {selectedInGroup > 0 ? `, ${selectedInGroup} 个已选` : ''})
          </span>
        </Space>
      </div>
    );
  };

  return (
    <div className="mx-8">
      {/* 认证状态提示 */}
      {!hasAuthToken() && (
        <Alert
          type="warning"
          showIcon
          message="需要身份认证"
          description="请登录 RAGFlow 主系统或配置 API Key"
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
          style={{ marginBottom: 16 }}
          action={
            <Button size="small" onClick={checkApiStatus}>
              重新检查
            </Button>
          }
        />
      )}
      {hasAuthToken() && apiStatus === 'checking' && (
        <Alert
          type="info"
          showIcon
          message="正在验证身份..."
          style={{ marginBottom: 16 }}
        />
      )}

      {/* 头部 */}
      <div className="flex justify-between items-center mb-6">
        <div>
          <h2 className="text-2xl font-bold mb-2">新闻收集器</h2>
          <p className="text-gray-600">
            共 {totalSources} 个新闻源，{activeSources} 个启用，已选择{' '}
            {selectedCount} 个
          </p>
        </div>
        <Space>
          <Button icon={<KeyOutlined />} onClick={openApiKeyModal}>
            API Key
          </Button>
          <Button
            icon={<ImportOutlined />}
            onClick={() => setImportModalVisible(true)}
            disabled={!hasAuthToken()}
          >
            批量导入
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
            disabled={!hasAuthToken() || selectedCount === 0}
          >
            即时抓取 {selectedCount > 0 && `(${selectedCount})`}
          </Button>
        </Space>
      </div>

      {/* 主内容区 */}
      <div className="h-[calc(100dvh-220px)] overflow-auto">
        <Card>
          <Tabs activeKey={activeTab} onChange={setActiveTab}>
            <TabPane tab="新闻源管理" key="sources">
              {/* 搜索和批量操作 */}
              <div
                style={{
                  marginBottom: 16,
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                }}
              >
                <Search
                  placeholder="搜索新闻源名称、URL、地区、机构..."
                  value={searchKeyword}
                  onChange={(e) => setSearchKeyword(e.target.value)}
                  style={{ width: 400 }}
                  allowClear
                />
                <Space>
                  <Button
                    icon={<CheckSquareOutlined />}
                    onClick={handleSelectAll}
                    disabled={activeSources === 0}
                  >
                    全选
                  </Button>
                  <Button
                    icon={<BorderOutlined />}
                    onClick={handleDeselectAll}
                    disabled={selectedCount === 0}
                  >
                    取消全选
                  </Button>
                </Space>
              </div>

              {/* 分组列表 */}
              <Spin spinning={sourcesLoading}>
                {filteredGroups.length === 0 && !sourcesLoading ? (
                  <Empty description="暂无新闻源" style={{ margin: '40px 0' }}>
                    <Button type="primary" onClick={openAddModal}>
                      添加第一个新闻源
                    </Button>
                  </Empty>
                ) : (
                  <Collapse
                    activeKey={expandedGroups}
                    onChange={(keys) => setExpandedGroups(keys as string[])}
                    expandIcon={({ isActive }) =>
                      isActive ? <DownOutlined /> : <RightOutlined />
                    }
                  >
                    {filteredGroups.map((group) => (
                      <Panel
                        header={renderGroupHeader(group)}
                        key={group.group}
                      >
                        {group.sources.map((source) =>
                          renderSourceCard(source),
                        )}
                      </Panel>
                    ))}
                  </Collapse>
                )}
              </Spin>
            </TabPane>

            {/* 新增：爬虫目标 Tab */}
            <TabPane tab="爬虫目标" key="targets">
              <TargetList
                apiKey={apiKey}
                refreshTrigger={targetRefreshTrigger}
                sources={groupedSources
                  .flatMap((g) => g.sources)
                  .map((s) => ({ id: s.id!, name: s.name }))}
                datasets={datasets}
                onEdit={(target) => {
                  setEditingTarget(target);
                  setTargetFormModalVisible(true);
                }}
                onAdd={() => {
                  setEditingTarget(null);
                  setTargetFormModalVisible(true);
                }}
              />
            </TabPane>

            {/* 新增：运行记录 Tab */}
            <TabPane tab="运行记录" key="logs">
              <TaskLogsList apiKey={apiKey} />
            </TabPane>
          </Tabs>
        </Card>
      </div>

      {/* Target 表单模态框 */}
      <Modal
        title={editingTarget ? '编辑爬虫目标' : '添加爬虫目标'}
        open={targetFormModalVisible}
        onCancel={() => {
          setTargetFormModalVisible(false);
          setEditingTarget(null);
        }}
        footer={null}
        width={700}
      >
        <TargetForm
          initialData={editingTarget || undefined}
          sources={groupedSources
            .flatMap((g) => g.sources)
            .map((s) => ({ id: s.id!, name: s.name }))}
          datasets={datasets}
          onSubmit={async (data) => {
            setLoading(true);
            try {
              console.log('[主页面] 提交 Target 数据:', data);
              if (editingTarget?.id) {
                const response = await updateTarget(
                  editingTarget.id,
                  data,
                  apiKey,
                );
                console.log('[主页面] 更新响应:', response);
                message.success('目标更新成功');
              } else {
                const response = await createTarget(data, apiKey);
                console.log('[主页面] 创建响应:', response);
                message.success('目标创建成功');
              }
              setTargetFormModalVisible(false);
              setEditingTarget(null);
              // 触发刷新
              setTargetRefreshTrigger((prev) => prev + 1);
              // 确保在 targets Tab
              setActiveTab('targets');
            } catch (error: any) {
              console.error('[主页面] 操作失败:', error);
              message.error(error.response?.data?.message || '操作失败');
            } finally {
              setLoading(false);
            }
          }}
          onCancel={() => {
            setTargetFormModalVisible(false);
            setEditingTarget(null);
          }}
          loading={loading}
          isEditing={!!editingTarget}
        />
      </Modal>

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

      {/* API Key 模态框 */}
      <Modal
        title="配置 API Key"
        open={apiKeyModalVisible}
        onOk={handleSaveApiKey}
        onCancel={closeApiKeyModal}
        okText="保存"
        cancelText="取消"
      >
        <Input.TextArea
          placeholder="请输入 API Key"
          value={tempApiKey}
          onChange={(e) => setTempApiKey(e.target.value)}
          rows={3}
        />
      </Modal>

      {/* 抓取配置模态框 */}
      <Modal
        title="配置抓取参数"
        open={crawlConfigModalVisible}
        onOk={executeCrawl}
        onCancel={() => setCrawlConfigModalVisible(false)}
        okText="开始抓取"
        cancelText="取消"
        width={600}
      >
        <div style={{ marginBottom: 16 }}>
          <label style={{ marginRight: 20 }}>
            <input
              type="radio"
              value="instant"
              checked={crawlMode === 'instant'}
              onChange={() => setCrawlMode('instant')}
              style={{ marginRight: 8 }}
            />
            即时抓取
          </label>
          <label>
            <input
              type="radio"
              value="topic"
              checked={crawlMode === 'topic'}
              onChange={() => setCrawlMode('topic')}
              style={{ marginRight: 8 }}
            />
            主题搜索
          </label>
        </div>
        <Form form={crawlConfigForm} layout="vertical">
          <Form.Item
            name="kb_id"
            label="目标知识库"
            rules={[{ required: true, message: '请选择知识库' }]}
          >
            <Select placeholder="选择知识库">
              {datasets.map((ds) => (
                <Select.Option key={ds.id} value={ds.id}>
                  {ds.name}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>

          {/* 即时抓取模式参数 */}
          {crawlMode === 'instant' && (
            <Form.Item
              name="depth"
              label="抓取深度"
              initialValue={2}
              tooltip="从首页开始递归抓取的链接层级深度"
            >
              <InputNumber min={1} max={5} style={{ width: '100%' }} />
            </Form.Item>
          )}

          {/* 主题搜索模式参数 */}
          {crawlMode === 'topic' && (
            <>
              <Form.Item
                name="keywords"
                label="搜索关键词"
                rules={[{ required: true, message: '请输入搜索关键词' }]}
                tooltip="输入多个关键词，用逗号分隔"
              >
                <Input
                  placeholder="输入关键词，用逗号分隔，如：电力市场,现货交易"
                  onChange={(e) => {
                    const keywords = e.target.value
                      .split(',')
                      .map((k) => k.trim())
                      .filter((k) => k);
                    crawlConfigForm.setFieldValue('keywords', keywords);
                  }}
                />
              </Form.Item>
              <Form.Item
                name="max_depth"
                label="最大爬取深度"
                initialValue={2}
                tooltip="从首页开始递归爬取的链接层级深度"
              >
                <InputNumber min={1} max={5} style={{ width: '100%' }} />
              </Form.Item>
              <Form.Item
                name="max_crawl_pages_per_source"
                label="每源最大爬取页数"
                initialValue={100}
                tooltip="每个源最多爬取的页面数，用于限制爬虫的搜索范围"
              >
                <InputNumber min={1} max={10000} style={{ width: '100%' }} />
              </Form.Item>
              <Form.Item
                name="score_threshold"
                label="相关性分数阈值"
                initialValue={0.3}
                tooltip="0-1之间，低于此分数的页面将被跳过"
              >
                <InputNumber
                  min={0}
                  max={1}
                  step={0.1}
                  style={{ width: '100%' }}
                />
              </Form.Item>
            </>
          )}

          <Form.Item
            name="max_pages_per_source"
            label="每源最大收集页数"
            initialValue={crawlMode === 'instant' ? 10 : 30}
            tooltip="每个源最多收集的页面数量"
          >
            <InputNumber min={1} max={1000} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item
            name="parse"
            label="自动解析"
            valuePropName="checked"
            tooltip="上传后立即解析文档"
          >
            <Switch />
          </Form.Item>
        </Form>
      </Modal>

      {/* 批量导入模态框 */}
      <Modal
        title="批量导入新闻源"
        open={importModalVisible}
        onOk={handleImport}
        onCancel={() => {
          setImportModalVisible(false);
          setImportJsonText('');
        }}
        okText="导入"
        cancelText="取消"
        confirmLoading={importLoading}
        width={700}
      >
        <Alert
          type="info"
          message="请输入 JSON 格式的新闻源数据，必填字段：name、url"
          style={{ marginBottom: 16 }}
        />
        <TextArea
          rows={12}
          value={importJsonText}
          onChange={(e) => setImportJsonText(e.target.value)}
          placeholder={importExampleJson}
          style={{ fontFamily: 'monospace' }}
        />
        <Button
          type="link"
          onClick={() => setImportJsonText(importExampleJson)}
          style={{ padding: 0, marginTop: 8 }}
        >
          填入示例数据
        </Button>
      </Modal>
    </div>
  );
};

export default NewsCollector;
