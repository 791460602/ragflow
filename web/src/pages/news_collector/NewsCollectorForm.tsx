import React, { useState } from 'react';
import { Form, Input, Select, Button, Space } from 'antd';

interface NewsSourceFormProps {
  onSubmit: (data: { name: string; url: string; remark?: string }) => void;
  initialData?: { name: string; url: string; remark?: string };
  datasets: { id: string; name: string }[];
  selectedDataset: string;
  onDatasetChange: (id: string) => void;
}

const NewsCollectorForm: React.FC<NewsSourceFormProps> = ({ onSubmit, initialData, datasets, selectedDataset, onDatasetChange }) => {
  const [form] = Form.useForm();

  const handleFinish = (values: { name: string; url: string; remark?: string }) => {
    onSubmit(values);
    form.resetFields();
  };

  return (
    <Form
      form={form}
      layout="inline"
      onFinish={handleFinish}
      initialValues={initialData}
      style={{ width: '100%' }}
    >
      <Form.Item name="dataset" initialValue={selectedDataset} rules={[{ required: true, message: '请选择知识库' }]}
        style={{ minWidth: 180 }}>
        <Select
          placeholder="选择知识库"
          value={selectedDataset}
          onChange={onDatasetChange}
          style={{ minWidth: 160 }}
        >
          {datasets.map(ds => (
            <Select.Option key={ds.id} value={ds.id}>{ds.name}</Select.Option>
          ))}
        </Select>
      </Form.Item>
      <Form.Item name="name" rules={[{ required: true, message: '请输入网站名称' }]}
        style={{ minWidth: 120 }}>
        <Input placeholder="网站名称" />
      </Form.Item>
      <Form.Item name="url" rules={[{ required: true, message: '请输入新闻源URL' }]}
        style={{ minWidth: 200 }}>
        <Input placeholder="新闻源URL" type="url" />
      </Form.Item>
      <Form.Item name="remark" style={{ minWidth: 120 }}>
        <Input placeholder="备注（可选）" />
      </Form.Item>
      <Form.Item>
        <Button type="primary" htmlType="submit">{initialData ? '保存' : '添加'}</Button>
      </Form.Item>
    </Form>
  );
};

export default NewsCollectorForm; 