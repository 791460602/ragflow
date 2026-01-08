import { PlusOutlined, QuestionCircleOutlined } from '@ant-design/icons';
import {
  Button,
  Collapse,
  Form,
  Input,
  Radio,
  Select,
  Space,
  Tag,
  Tooltip,
} from 'antd';
import React, { useEffect, useState } from 'react';

const { Panel } = Collapse;
const { TextArea } = Input;

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
}

interface NewsSourceFormProps {
  onSubmit: (data: NewsSource) => void;
  onCancel?: () => void;
  initialData?: NewsSource;
  loading?: boolean;
  isEditing?: boolean;
}

// 源类型配置
const SOURCE_TYPE_OPTIONS = [
  { value: 'news', label: '新闻源', color: 'blue' },
  { value: 'policy', label: '政策源', color: 'red' },
  { value: 'other', label: '其他', color: 'default' },
];

// 常用地区选项
const REGION_OPTIONS = [
  '全国',
  '北京市',
  '上海市',
  '广东省',
  '浙江省',
  '江苏省',
  '山东省',
  '四川省',
  '湖北省',
  '湖南省',
  '河南省',
  '福建省',
  '安徽省',
  '河北省',
  '陕西省',
  '重庆市',
  '天津市',
];

// 常用发布机构选项
const ISSUER_OPTIONS = [
  '国家发展和改革委员会',
  '国家能源局',
  '工业和信息化部',
  '财政部',
  '住房和城乡建设部',
  '国家电网有限公司',
  '中国南方电网有限责任公司',
];

const NewsCollectorForm: React.FC<NewsSourceFormProps> = ({
  onSubmit,
  onCancel,
  initialData,
  loading = false,
  isEditing = false,
}) => {
  const [form] = Form.useForm();
  const [crawlMode, setCrawlMode] = useState<string>(
    initialData?.remark || '0',
  );
  const [sourceType, setSourceType] = useState<SourceType>(
    initialData?.source_type || 'news',
  );
  const [policyThemeInput, setPolicyThemeInput] = useState('');

  // 当 initialData 变化时，更新表单和状态
  useEffect(() => {
    if (initialData) {
      // 更新抓取模式状态
      setCrawlMode(initialData.remark || '0');
      setSourceType(initialData.source_type || 'news');

      // 重置表单值
      form.setFieldsValue({
        name: initialData.name,
        url: initialData.url,
        status: initialData.status || 'active',
        remark: initialData.remark || '0',
        source_type: initialData.source_type || 'news',
        region: initialData.region,
        issuer: initialData.issuer,
        policy_theme: initialData.policy_theme || [],
        fetch_config_text: initialData.fetch_config
          ? JSON.stringify(initialData.fetch_config, null, 2)
          : '',
      });
    } else {
      // 如果是新增，重置为默认值
      setCrawlMode('0');
      setSourceType('news');
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
        const lines = fetch_config_text
          .split('\n')
          .filter((line: string) => line.trim());
        lines.forEach((line: string) => {
          const [key, value] = line.split(':').map((s: string) => s.trim());
          if (key && value) {
            (fetch_config as Record<string, string>)[key] = value;
          }
        });
      }
    }

    // 处理 region 和 issuer（Select mode="tags" 返回数组，取第一个值）
    const region = Array.isArray(values.region)
      ? values.region[0]
      : values.region;
    const issuer = Array.isArray(values.issuer)
      ? values.issuer[0]
      : values.issuer;

    const formData: NewsSource = {
      ...otherValues,
      fetch_config: values.remark === '1' ? fetch_config : {},
      // 确保 policy_theme 是数组
      policy_theme: Array.isArray(values.policy_theme)
        ? values.policy_theme
        : [],
      region: region || undefined,
      issuer: issuer || undefined,
    };

    onSubmit(formData);
    if (!isEditing) {
      form.resetFields();
      setCrawlMode('0');
      setSourceType('news');
    }
  };

  const handleModeChange = (e: any) => {
    const mode = e.target.value;
    setCrawlMode(mode);
    form.setFieldsValue({ remark: mode });
  };

  const handleSourceTypeChange = (value: SourceType) => {
    setSourceType(value);
    form.setFieldsValue({ source_type: value });
  };

  // 添加主题标签
  const handleAddPolicyTheme = () => {
    if (!policyThemeInput.trim()) return;
    const currentThemes = form.getFieldValue('policy_theme') || [];
    if (!currentThemes.includes(policyThemeInput.trim())) {
      form.setFieldsValue({
        policy_theme: [...currentThemes, policyThemeInput.trim()],
      });
    }
    setPolicyThemeInput('');
  };

  // 移除主题标签
  const handleRemovePolicyTheme = (theme: string) => {
    const currentThemes = form.getFieldValue('policy_theme') || [];
    form.setFieldsValue({
      policy_theme: currentThemes.filter((t: string) => t !== theme),
    });
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
                <QuestionCircleOutlined
                  style={{ marginLeft: 8, color: '#1890ff' }}
                />
              </Tooltip>
            </span>
          }
          key="1"
        >
          <Form.Item
            name="fetch_config_text"
            label="选择器配置"
            rules={
              crawlMode === '1'
                ? [{ required: true, message: '精确模式需要配置CSS选择器' }]
                : []
            }
          >
            <TextArea
              rows={6}
              placeholder={exampleConfig}
              style={{ fontFamily: 'monospace' }}
            />
          </Form.Item>
          <div style={{ fontSize: '12px', color: '#666', marginTop: '8px' }}>
            <p>
              <strong>配置说明：</strong>
            </p>
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

  // 渲染政策源专属字段
  const renderPolicyFields = () => {
    if (sourceType !== 'policy') return null;

    return (
      <div
        style={{
          background: '#fff7e6',
          padding: '16px',
          borderRadius: '8px',
          marginBottom: '16px',
          border: '1px solid #ffd591',
        }}
      >
        <h4 style={{ marginBottom: '16px', color: '#d46b08' }}>
          📋 政策源信息
        </h4>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: '1fr 1fr',
            gap: '16px',
          }}
        >
          <Form.Item name="region" label="所属地区">
            <Select
              placeholder="选择或输入地区"
              allowClear
              showSearch
              mode="tags"
            >
              {REGION_OPTIONS.map((region) => (
                <Select.Option key={region} value={region}>
                  {region}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>

          <Form.Item name="issuer" label="发布机构">
            <Select
              placeholder="选择或输入发布机构"
              allowClear
              showSearch
              mode="tags"
            >
              {ISSUER_OPTIONS.map((issuer) => (
                <Select.Option key={issuer} value={issuer}>
                  {issuer}
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
        </div>

        <Form.Item
          label={
            <span>
              主题标签
              <Tooltip title="该源主打的主题标签，如：分时电价、电力市场">
                <QuestionCircleOutlined
                  style={{ marginLeft: 8, color: '#1890ff' }}
                />
              </Tooltip>
            </span>
          }
        >
          <div>
            <Space style={{ marginBottom: 8 }}>
              <Input
                placeholder="输入主题标签"
                value={policyThemeInput}
                onChange={(e) => setPolicyThemeInput(e.target.value)}
                onPressEnter={(e) => {
                  e.preventDefault();
                  handleAddPolicyTheme();
                }}
                style={{ width: 200 }}
              />
              <Button
                type="dashed"
                icon={<PlusOutlined />}
                onClick={handleAddPolicyTheme}
              >
                添加
              </Button>
            </Space>
            <div>
              {(form.getFieldValue('policy_theme') || []).map(
                (theme: string) => (
                  <Tag
                    key={theme}
                    closable
                    onClose={() => handleRemovePolicyTheme(theme)}
                    style={{ marginBottom: 4 }}
                    color="orange"
                  >
                    {theme}
                  </Tag>
                ),
              )}
            </div>
          </div>
        </Form.Item>
        {/* 隐藏字段用于存储 policy_theme 数据 */}
        <Form.Item name="policy_theme" hidden>
          <Input />
        </Form.Item>
      </div>
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
        source_type: 'news',
        policy_theme: [],
        ...initialData,
        fetch_config_text: initialData?.fetch_config
          ? JSON.stringify(initialData.fetch_config, null, 2)
          : '',
      }}
      style={{ width: '100%' }}
    >
      <div
        style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}
      >
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
            { type: 'url', message: '请输入有效的URL' },
          ]}
        >
          <Input placeholder="https://example.com" />
        </Form.Item>
      </div>

      {/* 源类型选择 */}
      <Form.Item
        name="source_type"
        label={
          <span>
            源类型
            <Tooltip title="政策源会显示额外的分类字段，便于管理政策文档">
              <QuestionCircleOutlined
                style={{ marginLeft: 8, color: '#1890ff' }}
              />
            </Tooltip>
          </span>
        }
        rules={[{ required: true, message: '请选择源类型' }]}
      >
        <Select onChange={handleSourceTypeChange} value={sourceType}>
          {SOURCE_TYPE_OPTIONS.map((opt) => (
            <Select.Option key={opt.value} value={opt.value}>
              <Tag color={opt.color} style={{ marginRight: 8 }}>
                {opt.label}
              </Tag>
              {opt.value === 'policy' && '适用于政府政策文件'}
              {opt.value === 'news' && '适用于新闻资讯网站'}
              {opt.value === 'other' && '其他类型网站'}
            </Select.Option>
          ))}
        </Select>
      </Form.Item>

      {/* 政策源专属字段 */}
      {renderPolicyFields()}

      <Form.Item
        name="remark"
        label={
          <span>
            抓取模式
            <Tooltip title="自动模式使用AI智能提取，精确模式使用CSS选择器精确定位">
              <QuestionCircleOutlined
                style={{ marginLeft: 8, color: '#1890ff' }}
              />
            </Tooltip>
          </span>
        }
      >
        <Radio.Group onChange={handleModeChange} value={crawlMode}>
          <Radio value="0">
            <span>自动模式</span>
            <div style={{ fontSize: '12px', color: '#666' }}>
              AI智能提取，配置简单
            </div>
          </Radio>
          <Radio value="1">
            <span>精确模式</span>
            <div style={{ fontSize: '12px', color: '#666' }}>
              使用CSS选择器，提取精确
            </div>
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
          {onCancel && <Button onClick={onCancel}>取消</Button>}
        </Space>
      </Form.Item>
    </Form>
  );
};

export default NewsCollectorForm;
export type { NewsSource, NewsSourceFormProps };
