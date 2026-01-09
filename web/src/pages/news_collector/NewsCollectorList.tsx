import {
  DeleteOutlined,
  EditOutlined,
  GlobalOutlined,
} from '@ant-design/icons';
import { Button, Popconfirm, Space, Table, Tag, Tooltip } from 'antd';
import React from 'react';

// 源类型定义
type SourceType = 'policy' | 'news' | 'other';

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
  // 新增字段
  source_type?: SourceType;
  region?: string;
  issuer?: string;
  policy_theme?: string[];
  create_time?: string;
  update_time?: string;
}

interface NewsCollectorListProps {
  sources: NewsSource[];
  onEdit: (source: NewsSource) => void;
  onDelete: (id: string) => void;
  loading?: boolean;
}

// 源类型配置
const SOURCE_TYPE_CONFIG: Record<string, { label: string; color: string }> = {
  policy: { label: '政策源', color: 'red' },
  news: { label: '新闻源', color: 'blue' },
  other: { label: '其他', color: 'default' },
};

const NewsCollectorList: React.FC<NewsCollectorListProps> = ({
  sources,
  onEdit,
  onDelete,
  loading = false,
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
            {record.create_time &&
              `创建于 ${new Date(record.create_time).toLocaleDateString()}`}
          </div>
        </div>
      ),
    },
    {
      title: '源类型',
      dataIndex: 'source_type',
      key: 'source_type',
      width: 100,
      render: (sourceType: SourceType, record: NewsSource) => {
        const config =
          SOURCE_TYPE_CONFIG[sourceType] || SOURCE_TYPE_CONFIG.other;
        return (
          <Tooltip
            title={
              record.source_type === 'policy' &&
              (record.region || record.issuer) ? (
                <div>
                  {record.region && <div>📍 地区: {record.region}</div>}
                  {record.issuer && <div>🏛️ 机构: {record.issuer}</div>}
                  {record.policy_theme && record.policy_theme.length > 0 && (
                    <div>🏷️ 主题: {record.policy_theme.join(', ')}</div>
                  )}
                </div>
              ) : undefined
            }
          >
            <Tag color={config.color}>{config.label}</Tag>
          </Tooltip>
        );
      },
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
              maxWidth: '250px',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            }}
          >
            <GlobalOutlined style={{ marginRight: 4 }} />
            {text}
          </a>
        </Tooltip>
      ),
    },
    {
      title: '地区/机构',
      key: 'region_issuer',
      width: 150,
      render: (_: any, record: NewsSource) => {
        if (record.source_type !== 'policy') {
          return <span style={{ color: '#999' }}>-</span>;
        }
        return (
          <div style={{ fontSize: '12px' }}>
            {record.region && <div>📍 {record.region}</div>}
            {record.issuer && (
              <Tooltip title={record.issuer}>
                <div
                  style={{
                    maxWidth: '130px',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap',
                  }}
                >
                  🏛️ {record.issuer}
                </div>
              </Tooltip>
            )}
          </div>
        );
      },
    },
    {
      title: '主题标签',
      dataIndex: 'policy_theme',
      key: 'policy_theme',
      width: 150,
      render: (themes: string[], record: NewsSource) => {
        if (record.source_type !== 'policy' || !themes || themes.length === 0) {
          return <span style={{ color: '#999' }}>-</span>;
        }
        return (
          <div>
            {themes.slice(0, 2).map((theme) => (
              <Tag key={theme} color="orange" style={{ marginBottom: 2 }}>
                {theme}
              </Tag>
            ))}
            {themes.length > 2 && (
              <Tooltip title={themes.slice(2).join(', ')}>
                <Tag>+{themes.length - 2}</Tag>
              </Tooltip>
            )}
          </div>
        );
      },
    },
    {
      title: '抓取模式',
      dataIndex: 'remark',
      key: 'mode',
      width: 100,
      render: (remark: string, record: NewsSource) => {
        const isAuto = remark === '0' || !remark;
        return (
          <div>
            <Tag color={isAuto ? 'blue' : 'green'}>
              {isAuto ? '自动' : '精确'}
            </Tag>
            {!isAuto && record.fetch_config && (
              <Tooltip
                title={
                  <div>
                    <p>配置的CSS选择器：</p>
                    <ul>
                      {Object.entries(record.fetch_config).map(
                        ([key, value]) => (
                          <li key={key}>
                            {key}: {value}
                          </li>
                        ),
                      )}
                    </ul>
                  </div>
                }
              >
                <span style={{ cursor: 'help', color: '#1890ff' }}>🔧</span>
              </Tooltip>
            )}
          </div>
        );
      },
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 80,
      render: (status: string) => {
        const colors = {
          active: 'success',
          inactive: 'default',
          deleted: 'error',
        };
        const labels = {
          active: '启用',
          inactive: '禁用',
          deleted: '已删除',
        };
        return (
          <Tag color={colors[status as keyof typeof colors] || 'default'}>
            {labels[status as keyof typeof labels] || status || '未知'}
          </Tag>
        );
      },
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
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
              <Button icon={<DeleteOutlined />} danger size="small" />
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
      rowKey={(record) => record.id || record.name}
      loading={loading}
      pagination={{
        showSizeChanger: true,
        showQuickJumper: true,
        showTotal: (total, range) =>
          `第 ${range[0]}-${range[1]} 条，共 ${total} 条`,
        defaultPageSize: 10,
        pageSizeOptions: ['10', '20', '50'],
      }}
      size="middle"
    />
  );
};

export default NewsCollectorList;
export type { NewsCollectorListProps, NewsSource };
