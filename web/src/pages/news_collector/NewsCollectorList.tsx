import React from 'react';
import { Table, Button, Space, Tag, Tooltip, Popconfirm } from 'antd';
import { EditOutlined, DeleteOutlined, GlobalOutlined } from '@ant-design/icons';

interface NewsSource {
  id?: string;
  name: string;
  url: string;
  status?: string;
  remark?: string;
  fetch_config?: {
    link_selector?: string;
    title_selector?: string;
    content_selector?: string;
    publication_time_selector?: string;
    author_selector?: string;
  };
  create_time?: string;
  update_time?: string;
}

interface NewsCollectorListProps {
  sources: NewsSource[];
  onEdit: (source: NewsSource) => void;
  onDelete: (id: string) => void;
  loading?: boolean;
}

const NewsCollectorList: React.FC<NewsCollectorListProps> = ({ 
  sources, 
  onEdit, 
  onDelete, 
  loading = false 
}) => {
  const columns = [
    {
      title: '新闻源名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: NewsSource) => (
        <div>
          <div style={{ fontWeight: 'bold' }}>{text}</div>
          <div style={{ fontSize: '12px', color: '#666' }}>
            {record.create_time && `创建于 ${new Date(record.create_time).toLocaleDateString()}`}
          </div>
        </div>
      )
    },
    {
      title: '网站URL',
      dataIndex: 'url',
      key: 'url',
      render: (text: string) => (
        <Tooltip title={text}>
          <a 
            href={text} 
            target="_blank" 
            rel="noopener noreferrer"
            style={{ 
              display: 'inline-flex', 
              alignItems: 'center',
              maxWidth: '300px',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap'
            }}
          >
            <GlobalOutlined style={{ marginRight: 4 }} />
            {text}
          </a>
        </Tooltip>
      )
    },
    {
      title: '抓取模式',
      dataIndex: 'remark',
      key: 'mode',
      render: (remark: string, record: NewsSource) => {
        const isAuto = remark === '0' || !remark;
        return (
          <div>
            <Tag color={isAuto ? 'blue' : 'green'}>
              {isAuto ? '自动模式' : '精确模式'}
            </Tag>
            {!isAuto && record.fetch_config && (
              <Tooltip title={
                <div>
                  <p>配置的CSS选择器：</p>
                  <ul>
                    {Object.entries(record.fetch_config).map(([key, value]) => (
                      <li key={key}>{key}: {value}</li>
                    ))}
                  </ul>
                </div>
              }>
                <span style={{ cursor: 'help', color: '#1890ff' }}>🔧</span>
              </Tooltip>
            )}
          </div>
        );
      }
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => {
        const colors = {
          'active': 'success',
          'inactive': 'default',
          'deleted': 'error'
        };
        const labels = {
          'active': '启用',
          'inactive': '禁用',
          'deleted': '已删除'
        };
        return (
          <Tag color={colors[status as keyof typeof colors] || 'default'}>
            {labels[status as keyof typeof labels] || status || '未知'}
          </Tag>
        );
      }
    },
    {
      title: '操作',
      key: 'action',
      width: 120,
      render: (_: any, record: NewsSource) => (
        <Space size="small">
          <Tooltip title="编辑">
            <Button 
              icon={<EditOutlined />} 
              size="small" 
              onClick={() => onEdit(record)}
            />
          </Tooltip>
          <Popconfirm
            title="删除新闻源"
            description={`确定要删除新闻源「${record.name}」吗？`}
            onConfirm={() => record.id && onDelete(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Tooltip title="删除">
              <Button 
                icon={<DeleteOutlined />} 
                danger 
                size="small" 
              />
            </Tooltip>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <Table
      columns={columns}
      dataSource={sources}
      rowKey={record => record.id || record.name}
      loading={loading}
      pagination={{
        showSizeChanger: true,
        showQuickJumper: true,
        showTotal: (total, range) => `第 ${range[0]}-${range[1]} 条，共 ${total} 条`,
        defaultPageSize: 10,
        pageSizeOptions: ['10', '20', '50']
      }}
      size="middle"
    />
  );
};

export default NewsCollectorList;
export type { NewsSource, NewsCollectorListProps }; 