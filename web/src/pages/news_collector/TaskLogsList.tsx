import { EyeOutlined, ReloadOutlined } from '@ant-design/icons';
import { Button, Select, Space, Table, Tag, Tooltip, message } from 'antd';
import React, { useEffect, useState } from 'react';
import type { TaskLog } from './NewsCollectorService';
import { getTaskLogs } from './NewsCollectorService';

interface TaskLogsListProps {
  apiKey?: string;
  targetId?: string;
}

const TaskLogsList: React.FC<TaskLogsListProps> = ({ apiKey, targetId }) => {
  const [logs, setLogs] = useState<TaskLog[]>([]);
  const [loading, setLoading] = useState(false);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [statusFilter, setStatusFilter] = useState<string | undefined>();

  // 加载任务日志
  const loadLogs = async () => {
    setLoading(true);
    try {
      const response = await getTaskLogs(
        {
          page,
          page_size: pageSize,
          target_id: targetId,
          status: statusFilter,
        },
        apiKey,
      );
      if (response?.data?.data) {
        setLogs(response.data.data.logs || []);
        setTotal(response.data.data.total || 0);
      }
    } catch (error: any) {
      message.error('加载任务日志失败');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadLogs();
  }, [page, pageSize, targetId, statusFilter, apiKey]);

  // 状态颜色映射
  const getStatusColor = (status: string) => {
    const colorMap: Record<string, string> = {
      dispatched: 'blue',
      running: 'processing',
      completed: 'success',
      failed: 'error',
    };
    return colorMap[status] || 'default';
  };

  // 状态文本映射
  const getStatusText = (status: string) => {
    const textMap: Record<string, string> = {
      dispatched: '已派发',
      running: '运行中',
      completed: '已完成',
      failed: '失败',
    };
    return textMap[status] || status;
  };

  // 计算耗时
  const getDuration = (startedAt: number, finishedAt: number | null) => {
    if (!finishedAt) return '-';
    const duration = finishedAt - startedAt;
    const seconds = Math.floor(duration / 1000);
    const minutes = Math.floor(seconds / 60);
    const hours = Math.floor(minutes / 60);

    if (hours > 0) {
      return `${hours}小时${minutes % 60}分钟`;
    } else if (minutes > 0) {
      return `${minutes}分钟${seconds % 60}秒`;
    } else {
      return `${seconds}秒`;
    }
  };

  const columns = [
    {
      title: '任务ID',
      dataIndex: 'id',
      key: 'id',
      width: 150,
      ellipsis: true,
      render: (id: string) => (
        <Tooltip title={id}>
          <span>{id.substring(0, 12)}...</span>
        </Tooltip>
      ),
    },
    {
      title: '目标ID',
      dataIndex: 'target_id',
      key: 'target_id',
      width: 150,
      ellipsis: true,
      render: (targetId: string) => (
        <Tooltip title={targetId}>
          <span>{targetId.substring(0, 12)}...</span>
        </Tooltip>
      ),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => (
        <Tag color={getStatusColor(status)}>{getStatusText(status)}</Tag>
      ),
    },
    {
      title: '运行类型',
      dataIndex: 'run_type',
      key: 'run_type',
      width: 100,
      render: (type: string) => (
        <Tag color={type === 'manual' ? 'blue' : 'orange'}>
          {type === 'manual' ? '手动' : '定时'}
        </Tag>
      ),
    },
    {
      title: '开始时间',
      dataIndex: 'started_at',
      key: 'started_at',
      width: 180,
      render: (time: number) => new Date(time).toLocaleString(),
    },
    {
      title: '结束时间',
      dataIndex: 'finished_at',
      key: 'finished_at',
      width: 180,
      render: (time: number | null) =>
        time ? new Date(time).toLocaleString() : '-',
    },
    {
      title: '耗时',
      key: 'duration',
      width: 120,
      render: (_: any, record: TaskLog) =>
        getDuration(record.started_at, record.finished_at),
    },
    {
      title: '错误信息',
      dataIndex: 'error_message',
      key: 'error_message',
      ellipsis: true,
      render: (msg: string | null) =>
        msg ? (
          <Tooltip title={msg}>
            <span style={{ color: 'red' }}>{msg.substring(0, 30)}...</span>
          </Tooltip>
        ) : (
          '-'
        ),
    },
    {
      title: '操作',
      key: 'action',
      width: 80,
      render: (_: any, record: TaskLog) => (
        <Tooltip title="查看详情">
          <Button
            size="small"
            icon={<EyeOutlined />}
            onClick={() => {
              // TODO: 显示详情模态框
              message.info('详情功能待实现');
            }}
          />
        </Tooltip>
      ),
    },
  ];

  return (
    <div>
      {/* 过滤栏 */}
      <div
        style={{
          marginBottom: 16,
          display: 'flex',
          justifyContent: 'space-between',
        }}
      >
        <Space>
          <span>状态筛选：</span>
          <Select
            style={{ width: 120 }}
            placeholder="全部状态"
            allowClear
            value={statusFilter}
            onChange={setStatusFilter}
          >
            <Select.Option value="dispatched">已派发</Select.Option>
            <Select.Option value="running">运行中</Select.Option>
            <Select.Option value="completed">已完成</Select.Option>
            <Select.Option value="failed">失败</Select.Option>
          </Select>
        </Space>
        <Button icon={<ReloadOutlined />} onClick={loadLogs} loading={loading}>
          刷新
        </Button>
      </div>

      {/* 表格 */}
      <Table
        columns={columns}
        dataSource={logs}
        loading={loading}
        rowKey="id"
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: true,
          showTotal: (total) => `共 ${total} 条记录`,
          onChange: (newPage, newPageSize) => {
            setPage(newPage);
            if (newPageSize !== pageSize) {
              setPageSize(newPageSize);
              setPage(1);
            }
          },
        }}
        scroll={{ x: 1200 }}
      />
    </div>
  );
};

export default TaskLogsList;
