import React from 'react';
import { Table, Tag } from 'antd';

interface NewsHistoryItem {
  id: number;
  sourceName: string;
  title: string;
  status: string;
  createdAt: string;
}

interface NewsCollectorHistoryProps {
  history: NewsHistoryItem[];
}

const NewsCollectorHistory: React.FC<NewsCollectorHistoryProps> = ({ history }) => {
  const columns = [
    { title: '来源', dataIndex: 'sourceName', key: 'sourceName' },
    { title: '标题', dataIndex: 'title', key: 'title' },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (text: string) => (
        <Tag color={text === '成功' ? 'green' : 'red'}>{text}</Tag>
      ),
    },
    { title: '时间', dataIndex: 'createdAt', key: 'createdAt' },
  ];

  return (
    <Table
      columns={columns}
      dataSource={history}
      rowKey="id"
      pagination={false}
      size="middle"
      style={{ marginTop: 8 }}
    />
  );
};

export default NewsCollectorHistory; 