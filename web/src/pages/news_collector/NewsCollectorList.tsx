import React from 'react';
import { Table, Button } from 'antd';

interface NewsSource {
  id: number;
  name: string;
  url: string;
  remark?: string;
}

interface NewsCollectorListProps {
  sources: NewsSource[];
  onDelete: (id: number) => void;
}

const NewsCollectorList: React.FC<NewsCollectorListProps> = ({ sources, onDelete }) => {
  const columns = [
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: 'URL', dataIndex: 'url', key: 'url', render: (text: string) => <a href={text} target="_blank" rel="noopener noreferrer">{text}</a> },
    { title: '备注', dataIndex: 'remark', key: 'remark' },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: NewsSource) => (
        <Button danger size="small" onClick={() => onDelete(record.id)}>删除</Button>
      ),
    },
  ];

  return (
    <Table
      columns={columns}
      dataSource={sources}
      rowKey="id"
      pagination={false}
      size="middle"
      style={{ marginTop: 8 }}
    />
  );
};

export default NewsCollectorList; 