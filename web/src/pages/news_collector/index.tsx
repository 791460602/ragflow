import React, { useState, useEffect } from 'react';
import NewsCollectorForm from './NewsCollectorForm';
import NewsCollectorList from './NewsCollectorList';
import NewsCollectorHistory from './NewsCollectorHistory';
import { getDatasets, fetchNews } from './NewsCollectorService';

// mock数据结构
const initialSources = [
  { id: 1, name: '新浪新闻', url: 'https://news.sina.com.cn', remark: '默认示例' },
  { id: 2, name: '网易新闻', url: 'https://news.163.com', remark: '' },
];
const initialHistory = [
  { id: 1, sourceName: '新浪新闻', title: '示例新闻1', status: '成功', createdAt: '2024-05-01 10:00' },
  { id: 2, sourceName: '网易新闻', title: '示例新闻2', status: '失败', createdAt: '2024-05-01 11:00' },
];

// 假设API Key自动获取（如从localStorage、全局状态等）
const getApiKey = () => localStorage.getItem('apiKey') || '';

const NewsCollector: React.FC = () => {
  const [sources, setSources] = useState(initialSources);
  const [history, setHistory] = useState(initialHistory);
  const [datasets, setDatasets] = useState<{ id: string; name: string }[]>([]);
  const [selectedDataset, setSelectedDataset] = useState('');
  const apiKey = getApiKey();

  useEffect(() => {
    if (apiKey) {
      getDatasets(apiKey).then(res => {
        setDatasets(res.data.data || []);
      });
    }
  }, [apiKey]);

  // 添加新闻源
  const handleAddSource = (data: { name: string; url: string; remark?: string }) => {
    setSources(prev => [
      ...prev,
      { id: Date.now(), ...data },
    ]);
  };

  // 删除新闻源
  const handleDeleteSource = (id: number) => {
    setSources(prev => prev.filter(s => s.id !== id));
  };

  // 抓取新闻
  const handleFetchNews = async () => {
    if (!selectedDataset) {
      alert('请选择知识库');
      return;
    }
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
      alert('已抓取新闻并上传到知识库');
    } catch (e) {
      alert('抓取或上传失败，请检查API Key和网络');
    }
  };

  return (
    <div style={{ padding: 32 }}>
      <h1>新闻收集</h1>
      <NewsCollectorForm
        onSubmit={handleAddSource}
        datasets={datasets}
        selectedDataset={selectedDataset}
        onDatasetChange={setSelectedDataset}
      />
      <NewsCollectorList sources={sources} onDelete={handleDeleteSource} />
      <button style={{ marginTop: 24 }} onClick={handleFetchNews}>立即抓取新闻</button>
      <NewsCollectorHistory history={history} />
    </div>
  );
};

export default NewsCollector; 