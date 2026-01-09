import { Button, Form, Input, InputNumber, Select, Space, Switch } from 'antd';
import React, { useEffect } from 'react';
import type { CrawlTarget } from './NewsCollectorService';

const { TextArea } = Input;

interface TargetFormProps {
  initialData?: CrawlTarget;
  sources: Array<{ id: string; name: string }>;
  datasets: Array<{ id: string; name: string }>;
  onSubmit: (data: CrawlTarget) => void;
  onCancel?: () => void;
  loading?: boolean;
  isEditing?: boolean;
}

const TargetForm: React.FC<TargetFormProps> = ({
  initialData,
  sources,
  datasets,
  onSubmit,
  onCancel,
  loading = false,
  isEditing = false,
}) => {
  const [form] = Form.useForm();

  useEffect(() => {
    if (initialData) {
      form.setFieldsValue(initialData);
    } else {
      form.resetFields();
    }
  }, [initialData, form]);

  const handleFinish = (values: any) => {
    onSubmit(values);
  };

  return (
    <Form
      form={form}
      layout="vertical"
      onFinish={handleFinish}
      initialValues={{
        status: 'active',
        parse: false,
        max_depth: 2,
        max_pages_per_source: 50,
        max_crawl_pages_per_source: 100,
        ...initialData,
      }}
    >
      <Form.Item
        name="name"
        label="目标名称"
        rules={[{ required: true, message: '请输入目标名称' }]}
      >
        <Input placeholder="例如：每日上海能源政策" />
      </Form.Item>

      <Form.Item
        name="source_id"
        label="绑定新闻源"
        rules={[{ required: true, message: '请选择新闻源' }]}
      >
        <Select placeholder="选择新闻源" showSearch optionFilterProp="children">
          {sources.map((source) => (
            <Select.Option key={source.id} value={source.id}>
              {source.name}
            </Select.Option>
          ))}
        </Select>
      </Form.Item>

      <Form.Item
        name="kb_id"
        label="目标知识库"
        tooltip="抓取的内容将上传到此知识库"
      >
        <Select
          placeholder="选择知识库（可选）"
          allowClear
          showSearch
          optionFilterProp="children"
        >
          {datasets.map((ds) => (
            <Select.Option key={ds.id} value={ds.id}>
              {ds.name}
            </Select.Option>
          ))}
        </Select>
      </Form.Item>

      <div
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr 1fr',
          gap: '16px',
        }}
      >
        <Form.Item
          name="max_depth"
          label="爬取深度"
          tooltip="从首页开始递归爬取的链接层级深度"
        >
          <InputNumber min={1} max={5} style={{ width: '100%' }} />
        </Form.Item>

        <Form.Item
          name="max_pages_per_source"
          label="最大收集页数"
          tooltip="每个源最多收集的页面数量"
        >
          <InputNumber min={1} max={1000} style={{ width: '100%' }} />
        </Form.Item>

        <Form.Item
          name="max_crawl_pages_per_source"
          label="最大爬取页数"
          tooltip="每个源最多爬取的页面数（用于搜索）"
        >
          <InputNumber min={1} max={10000} style={{ width: '100%' }} />
        </Form.Item>
      </div>

      <div
        style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}
      >
        <Form.Item
          name="parse"
          label="自动解析"
          valuePropName="checked"
          tooltip="上传后立即解析文档"
        >
          <Switch />
        </Form.Item>

        <Form.Item name="status" label="状态">
          <Select>
            <Select.Option value="active">启用</Select.Option>
            <Select.Option value="inactive">禁用</Select.Option>
          </Select>
        </Form.Item>
      </div>

      <Form.Item name="remark" label="备注">
        <TextArea rows={3} placeholder="可选的备注信息" />
      </Form.Item>

      <Form.Item style={{ marginTop: '24px' }}>
        <Space>
          <Button type="primary" htmlType="submit" loading={loading}>
            {isEditing ? '保存修改' : '创建目标'}
          </Button>
          {onCancel && <Button onClick={onCancel}>取消</Button>}
        </Space>
      </Form.Item>
    </Form>
  );
};

export default TargetForm;
