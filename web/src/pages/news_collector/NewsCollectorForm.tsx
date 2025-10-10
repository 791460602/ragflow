import React, { useState, useEffect } from 'react';
import { Form, Input, Select, Button, Space, Radio, Collapse, Tooltip } from 'antd';
import { QuestionCircleOutlined } from '@ant-design/icons';

const { Panel } = Collapse;
const { TextArea } = Input;

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
}

interface NewsSourceFormProps {
  onSubmit: (data: NewsSource) => void;
  onCancel?: () => void;
  initialData?: NewsSource;
  loading?: boolean;
  isEditing?: boolean;
}

const NewsCollectorForm: React.FC<NewsSourceFormProps> = ({ 
  onSubmit, 
  onCancel, 
  initialData, 
  loading = false, 
  isEditing = false 
}) => {
  const [form] = Form.useForm();
  const [crawlMode, setCrawlMode] = useState<string>(initialData?.remark || '0');

  // 当 initialData 变化时，更新表单和状态
  useEffect(() => {
    if (initialData) {
      // 更新抓取模式状态
      setCrawlMode(initialData.remark || '0');
      
      // 重置表单值
      form.setFieldsValue({
        name: initialData.name,
        url: initialData.url,
        status: initialData.status || 'active',
        remark: initialData.remark || '0',
        fetch_config_text: initialData.fetch_config ? 
          JSON.stringify(initialData.fetch_config, null, 2) : ''
      });
    } else {
      // 如果是新增，重置为默认值
      setCrawlMode('0');
      form.resetFields();
    }
  }, [initialData, form]);

  const handleFinish = (values: any) => {
    const { fetch_config_text, ...otherValues } = values;
    let fetch_config: Record<string, any> = {};
    
    if (values.remark === '1' && fetch_config_text) {
      try {
        fetch_config = JSON.parse(fetch_config_text);
      } catch (e) {
        // 如果JSON解析失败，尝试解析为单独的选择器
        const lines = fetch_config_text.split('\n').filter((line: string) => line.trim());
        lines.forEach((line: string) => {
          const [key, value] = line.split(':').map((s: string) => s.trim());
          if (key && value) {
            (fetch_config as Record<string, string>)[key] = value;
          }
        });
      }
    }
    
    const formData: NewsSource = {
      ...otherValues,
      fetch_config: values.remark === '1' ? fetch_config : {}
    };
    
    onSubmit(formData);
    if (!isEditing) {
      form.resetFields();
      setCrawlMode('0');
    }
  };

  const handleModeChange = (e: any) => {
    const mode = e.target.value;
    setCrawlMode(mode);
    form.setFieldsValue({ remark: mode });
  };

  const renderAdvancedConfig = () => {
    if (crawlMode !== '1') return null;
    
    const exampleConfig = `{
  "link_selector": "div.nav a[href], div.main a[href]",
  "title_selector": "h1, h2.article_title, span.title",
  "content_selector": "div.article-content, div.TRS_Editor",
  "publication_time_selector": "span.date, span.times",
  "author_selector": "span.author, div.ly.laiyuantext"
}`;
    
    return (
      <Collapse ghost>
        <Panel 
          header={
            <span>
              CSS选择器配置 
              <Tooltip title="精确模式需要配置CSS选择器来提取页面内容">
                <QuestionCircleOutlined style={{ marginLeft: 8, color: '#1890ff' }} />
              </Tooltip>
            </span>
          } 
          key="1"
        >
          <Form.Item 
            name="fetch_config_text" 
            label="选择器配置"
            rules={crawlMode === '1' ? [{ required: true, message: '精确模式需要配置CSS选择器' }] : []}
          >
            <TextArea 
              rows={6} 
              placeholder={exampleConfig}
              style={{ fontFamily: 'monospace' }}
            />
          </Form.Item>
          <div style={{ fontSize: '12px', color: '#666', marginTop: '8px' }}>
            <p><strong>配置说明：</strong></p>
            <ul>
              <li>link_selector: 用于发现页面中的链接</li>
              <li>title_selector: 提取文章标题</li>
              <li>content_selector: 提取文章正文内容</li>
              <li>publication_time_selector: 提取发布时间</li>
              <li>author_selector: 提取作者信息</li>
            </ul>
          </div>
        </Panel>
      </Collapse>
    );
  };

  return (
    <Form
      form={form}
      layout="vertical"
      onFinish={handleFinish}
      initialValues={{
        status: 'active',
        remark: '0',
        ...initialData,
        fetch_config_text: initialData?.fetch_config ? 
          JSON.stringify(initialData.fetch_config, null, 2) : ''
      }}
      style={{ width: '100%' }}
    >
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
        <Form.Item 
          name="name" 
          label="新闻源名称" 
          rules={[{ required: true, message: '请输入新闻源名称' }]}
        >
          <Input placeholder="例如：新华网、央视新闻" />
        </Form.Item>
        
        <Form.Item 
          name="url" 
          label="网站URL" 
          rules={[
            { required: true, message: '请输入网站URL' },
            { type: 'url', message: '请输入有效的URL' }
          ]}
        >
          <Input placeholder="https://example.com" />
        </Form.Item>
      </div>
      
      <Form.Item 
        name="remark" 
        label={
          <span>
            抓取模式 
            <Tooltip title="自动模式使用AI智能提取，精确模式使用CSS选择器精确定位">
              <QuestionCircleOutlined style={{ marginLeft: 8, color: '#1890ff' }} />
            </Tooltip>
          </span>
        }
      >
        <Radio.Group onChange={handleModeChange} value={crawlMode}>
          <Radio value="0">
            <span>自动模式</span>
            <div style={{ fontSize: '12px', color: '#666' }}>AI智能提取，配置简单</div>
          </Radio>
          <Radio value="1">
            <span>精确模式</span>
            <div style={{ fontSize: '12px', color: '#666' }}>使用CSS选择器，提取精确</div>
          </Radio>
        </Radio.Group>
      </Form.Item>
      
      {renderAdvancedConfig()}
      
      <Form.Item name="status" label="状态">
        <Select>
          <Select.Option value="active">启用</Select.Option>
          <Select.Option value="inactive">禁用</Select.Option>
        </Select>
      </Form.Item>
      
      <Form.Item style={{ marginTop: '24px' }}>
        <Space>
          <Button type="primary" htmlType="submit" loading={loading}>
            {isEditing ? '保存修改' : '添加新闻源'}
          </Button>
          {onCancel && (
            <Button onClick={onCancel}>
              取消
            </Button>
          )}
        </Space>
      </Form.Item>
    </Form>
  );
};

export default NewsCollectorForm;
export type { NewsSource, NewsSourceFormProps }; 