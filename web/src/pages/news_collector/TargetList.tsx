import {
  BorderOutlined,
  CheckSquareOutlined,
  DeleteOutlined,
  EditOutlined,
  PlayCircleOutlined,
  PlusOutlined,
} from '@ant-design/icons';
import {
  Button,
  Card,
  Checkbox,
  Empty,
  Popconfirm,
  Space,
  Spin,
  Tag,
  Tooltip,
  message,
} from 'antd';
import React, { useEffect, useState } from 'react';
import type { CrawlTarget } from './NewsCollectorService';
import { deleteTarget, getTargets, runTargets } from './NewsCollectorService';

interface TargetListProps {
  apiKey?: string;
  onEdit: (target: CrawlTarget) => void;
  onAdd: () => void;
  refreshTrigger?: number;
  sources?: Array<{ id: string; name: string }>;
  datasets?: Array<{ id: string; name: string }>;
}

const TargetList: React.FC<TargetListProps> = ({
  apiKey,
  onEdit,
  onAdd,
  refreshTrigger,
  sources = [],
  datasets = [],
}) => {
  const [targets, setTargets] = useState<CrawlTarget[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedTargetIds, setSelectedTargetIds] = useState<string[]>([]);
  const [runningTargets, setRunningTargets] = useState<Set<string>>(new Set());

  // 根据ID获取名称的辅助函数
  const getSourceName = (sourceId: string) => {
    const source = sources.find((s) => s.id === sourceId);
    return source ? source.name : sourceId;
  };

  const getDatasetName = (kbId: string) => {
    const dataset = datasets.find((d) => d.id === kbId);
    return dataset ? dataset.name : kbId;
  };

  // 加载 Target 列表
  const loadTargets = async () => {
    setLoading(true);
    try {
      const response = await getTargets({}, apiKey);
      if (response?.data?.data?.targets) {
        setTargets(response.data.data.targets);
      }
    } catch (error: any) {
      message.error('加载爬虫目标失败');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTargets();
  }, [apiKey, refreshTrigger]); // 添加 refreshTrigger 依赖

  // 删除 Target
  const handleDelete = async (id: string) => {
    try {
      await deleteTarget(id, apiKey);
      message.success('删除成功');
      loadTargets();
    } catch (error: any) {
      message.error(error.response?.data?.message || '删除失败');
    }
  };

  // 运行单个 Target
  const handleRun = async (targetId: string) => {
    setRunningTargets((prev) => new Set(prev).add(targetId));
    try {
      const response = await runTargets([targetId], apiKey);
      if (response?.data?.data?.dispatched) {
        const logId = response.data.data.dispatched[0]?.log_id;
        message.success(`已触发后台任务，任务ID: ${logId}`);
      } else {
        message.success('已触发后台任务');
      }
      loadTargets();
    } catch (error: any) {
      message.error(error.response?.data?.message || '运行失败');
    } finally {
      setRunningTargets((prev) => {
        const newSet = new Set(prev);
        newSet.delete(targetId);
        return newSet;
      });
    }
  };

  // 批量运行
  const handleBatchRun = async () => {
    if (selectedTargetIds.length === 0) {
      message.warning('请先选择要运行的目标');
      return;
    }

    try {
      const response = await runTargets(selectedTargetIds, apiKey);
      if (response?.data?.data?.count) {
        message.success(`已触发 ${response.data.data.count} 个后台任务`);
      } else {
        message.success('已触发后台任务');
      }
      setSelectedTargetIds([]);
      loadTargets();
    } catch (error: any) {
      message.error(error.response?.data?.message || '批量运行失败');
    }
  };

  // 全选/取消全选
  const handleSelectAll = () => {
    const allIds = targets
      .filter((t) => t.status === 'active' && t.id)
      .map((t) => t.id!);
    setSelectedTargetIds(allIds);
  };

  const handleDeselectAll = () => {
    setSelectedTargetIds([]);
  };

  // 切换选择
  const handleToggleSelect = (targetId: string) => {
    setSelectedTargetIds((prev) =>
      prev.includes(targetId)
        ? prev.filter((id) => id !== targetId)
        : [...prev, targetId],
    );
  };

  // 渲染单个 Target 卡片
  const renderTargetCard = (target: CrawlTarget) => {
    const isSelected = selectedTargetIds.includes(target.id || '');
    const isRunning = runningTargets.has(target.id || '');
    const isActive = target.status === 'active';

    return (
      <Card
        key={target.id}
        size="small"
        style={{ marginBottom: 12 }}
        title={
          <div
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
            }}
          >
            <Space>
              {isActive && (
                <Checkbox
                  checked={isSelected}
                  onChange={() => target.id && handleToggleSelect(target.id)}
                />
              )}
              <span style={{ fontWeight: 'bold' }}>{target.name}</span>
              <Tag color={isActive ? 'success' : 'default'}>
                {isActive ? '启用' : '禁用'}
              </Tag>
            </Space>
            <Space>
              <Tooltip title="运行">
                <Button
                  size="small"
                  type="primary"
                  icon={<PlayCircleOutlined />}
                  onClick={() => target.id && handleRun(target.id)}
                  loading={isRunning}
                  disabled={!isActive}
                >
                  运行
                </Button>
              </Tooltip>
              <Tooltip title="编辑">
                <Button
                  size="small"
                  icon={<EditOutlined />}
                  onClick={() => onEdit(target)}
                />
              </Tooltip>
              <Popconfirm
                title="确定删除此目标？"
                onConfirm={() => target.id && handleDelete(target.id)}
                okText="确定"
                cancelText="取消"
              >
                <Button size="small" danger icon={<DeleteOutlined />} />
              </Popconfirm>
            </Space>
          </div>
        }
      >
        <div style={{ fontSize: 13 }}>
          <p style={{ margin: '4px 0' }}>
            <strong>新闻源:</strong> {getSourceName(target.source_id)}
          </p>
          {target.kb_id && (
            <p style={{ margin: '4px 0' }}>
              <strong>知识库:</strong> {getDatasetName(target.kb_id)}
            </p>
          )}
          <p style={{ margin: '4px 0' }}>
            <strong>参数:</strong> 深度 {target.max_depth || 2} | 收集{' '}
            {target.max_pages_per_source || 50} 页 | 爬取{' '}
            {target.max_crawl_pages_per_source || 100} 页
          </p>
          {target.last_run_time && (
            <p style={{ margin: '4px 0', color: '#666' }}>
              <strong>最后运行:</strong>{' '}
              {new Date(target.last_run_time).toLocaleString()}
            </p>
          )}
          {target.remark && (
            <p style={{ margin: '4px 0', color: '#666' }}>
              <strong>备注:</strong> {target.remark}
            </p>
          )}
        </div>
      </Card>
    );
  };

  return (
    <div>
      {/* 操作栏 */}
      <div
        style={{
          marginBottom: 16,
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <Space>
          <Button type="primary" icon={<PlusOutlined />} onClick={onAdd}>
            添加目标
          </Button>
          <Button
            icon={<PlayCircleOutlined />}
            onClick={handleBatchRun}
            disabled={selectedTargetIds.length === 0}
          >
            批量运行{' '}
            {selectedTargetIds.length > 0 && `(${selectedTargetIds.length})`}
          </Button>
        </Space>
        <Space>
          <Button
            icon={<CheckSquareOutlined />}
            onClick={handleSelectAll}
            disabled={targets.filter((t) => t.status === 'active').length === 0}
          >
            全选
          </Button>
          <Button
            icon={<BorderOutlined />}
            onClick={handleDeselectAll}
            disabled={selectedTargetIds.length === 0}
          >
            取消全选
          </Button>
        </Space>
      </div>

      {/* Target 列表 */}
      <Spin spinning={loading}>
        {targets.length === 0 && !loading ? (
          <Empty description="暂无爬虫目标" style={{ margin: '40px 0' }}>
            <Button type="primary" onClick={onAdd}>
              添加第一个目标
            </Button>
          </Empty>
        ) : (
          <div>{targets.map((target) => renderTargetCard(target))}</div>
        )}
      </Spin>
    </div>
  );
};

export default TargetList;
