import React, { useState, useEffect } from 'react';
import { Flex, Card, Button, Input, Space, Spin, Empty, message } from 'antd';
import { PlusOutlined, SyncOutlined } from '@ant-design/icons';
import NewsCollectorForm from './NewsCollectorForm';
import NewsCollectorList from './NewsCollectorList';
import NewsCollectorHistory from './NewsCollectorHistory';
import { getDatasets, fetchNews } from './NewsCollectorService';
import styles from './index.less';

const initialSources = [
  { id: 1, name: '新浪新闻', url: 'https://news.sina.com.cn', remark: '默认示例' },
  { id: 2, name: '网易新闻', url: 'https://news.163.com', remark: '' },
];
const initialHistory = [
  { id: 1, sourceName: '新浪新闻', title: '示例新闻1', status: '成功', createdAt: '2024-05-01 10:00' },
  { id: 2, sourceName: '网易新闻', title: '示例新闻2', status: '失败', createdAt: '2024-05-01 11:00' },
];

const getApiKey = () => localStorage.getItem('apiKey') || '';

const NewsCollector: React.FC = () => {
  const [sources, setSources] = useState(initialSources);
  const [history, setHistory] = useState(initialHistory);
  const [datasets, setDatasets] = useState<{ id: string; name: string }[]>([]);
  const [selectedDataset, setSelectedDataset] = useState('');
  const [loading, setLoading] = useState(false);
  const apiKey = getApiKey();

  useEffect(() => {
    if (apiKey) {
      getDatasets(apiKey).then(res => {
        setDatasets(res.data.data || []);
      });
    }
  }, [apiKey]);

  const handleAddSource = (data: { name: string; url: string; remark?: string }) => {
    setSources(prev => [
      ...prev,
      { id: Date.now(), ...data },
    ]);
  };

  const handleDeleteSource = (id: number) => {
    setSources(prev => prev.filter(s => s.id !== id));
  };

  const handleFetchNews = async () => {
    if (!selectedDataset) {
      message.warning('请选择知识库');
      return;
    }
    setLoading(true);
    try {
      await fetchNews({ kb_id: selectedDataset, source_ids: sources.map(s => s.id) }, apiKey);
      setHistory(prev => [
        ...prev,
        {
          id: Date.now(),
          sourceName: sources[0]?.name || '未知',
          title: '新抓取的新闻',
          status: '成功',
          createdAt: new Date().toLocaleString(),
        },
      ]);
      message.success('已抓取新闻并上传到知识库');
    } catch (e) {
      message.error('抓取或上传失败，请检查API Key和网络');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Flex className={styles.newsCollector} vertical flex={1}>
      <div className={styles.topWrapper}>
        <div>
          <span className={styles.title}>新闻收集</span>
          <p className={styles.description}>配置新闻源，抓取并自动入库，便于检索和问答。</p>
        </div>
        <Space size="large">
          {/* 这里可加搜索框等 */}
          <Button type="primary" icon={<SyncOutlined />} onClick={handleFetchNews} loading={loading}>
            立即抓取新闻
          </Button>
        </Space>
      </div>
      <Card className={styles.card} style={{ marginTop: 16 }}>
        <NewsCollectorForm
          onSubmit={handleAddSource}
          datasets={datasets}
          selectedDataset={selectedDataset}
          onDatasetChange={setSelectedDataset}
        />
      </Card>
      <Card className={styles.card} style={{ marginTop: 16 }} title="新闻源管理">
        <NewsCollectorList sources={sources} onDelete={handleDeleteSource} />
        {sources.length === 0 && <Empty description="暂无新闻源" />}
      </Card>
      <Card className={styles.card} style={{ marginTop: 16 }} title="抓取历史">
        <NewsCollectorHistory history={history} />
        {history.length === 0 && <Empty description="暂无抓取历史" />}
      </Card>
      <Spin spinning={loading} />
    </Flex>
  );
};

export default NewsCollector; 