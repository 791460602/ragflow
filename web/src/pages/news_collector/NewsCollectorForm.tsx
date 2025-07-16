import React, { useState } from 'react';

interface NewsSourceFormProps {
  onSubmit: (data: { name: string; url: string; remark?: string }) => void;
  initialData?: { name: string; url: string; remark?: string };
  datasets: { id: string; name: string }[];
  selectedDataset: string;
  onDatasetChange: (id: string) => void;
}

const NewsCollectorForm: React.FC<NewsSourceFormProps> = ({ onSubmit, initialData, datasets, selectedDataset, onDatasetChange }) => {
  const [name, setName] = useState(initialData?.name || '');
  const [url, setUrl] = useState(initialData?.url || '');
  const [remark, setRemark] = useState(initialData?.remark || '');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!name || !url) return;
    onSubmit({ name, url, remark });
    setName('');
    setUrl('');
    setRemark('');
  };

  return (
    <form onSubmit={handleSubmit} style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
      <select value={selectedDataset} onChange={e => onDatasetChange(e.target.value)} required style={{ minWidth: 120 }}>
        <option value="">选择知识库</option>
        {datasets.map(ds => (
          <option key={ds.id} value={ds.id}>{ds.name}</option>
        ))}
      </select>
      <input
        type="text"
        placeholder="网站名称"
        value={name}
        onChange={e => setName(e.target.value)}
        required
      />
      <input
        type="url"
        placeholder="新闻源URL"
        value={url}
        onChange={e => setUrl(e.target.value)}
        required
      />
      <input
        type="text"
        placeholder="备注（可选）"
        value={remark}
        onChange={e => setRemark(e.target.value)}
      />
      <button type="submit">{initialData ? '保存' : '添加'}</button>
    </form>
  );
};

export default NewsCollectorForm; 