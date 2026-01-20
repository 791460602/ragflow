import axios from 'axios';

// 源类型定义
export type SourceType = 'policy' | 'news' | 'other';

interface NewsSource {
  id?: string;
  name: string;
  url: string;
  status?: string;
  remark?: string; // "0" for auto mode, "1" for precise mode
  fetch_config?: {
    link_selector?: string;
    title_selector?: string;
    content_selector?: string;
    publication_time_selector?: string;
    author_selector?: string;
  };
  // 新增字段 - 支持政策源分类
  source_type?: SourceType; // 源类型: policy|news|other
  region?: string; // 所属地区，如广东省/国家
  issuer?: string; // 发布机构归一化名称
  policy_theme?: string[]; // 主题标签列表
  create_time?: string;
  update_time?: string;
}

// 新增：Target 相关接口定义
interface CrawlTarget {
  id?: string;
  name: string;
  source_id: string;
  group_id?: string;
  kb_id?: string;
  parse?: boolean;
  max_depth?: number;
  max_pages_per_source?: number;
  max_crawl_pages_per_source?: number;
  status?: string;
  remark?: string;
  create_time?: string;
  update_time?: string;
  last_run_time?: number;
}

interface TargetGroup {
  id?: string;
  name: string;
  description?: string;
  status?: string;
}

interface TaskLog {
  id: string;
  target_id: string;
  status: string; // dispatched/running/completed/failed
  run_type: string; // manual/scheduled
  started_at: number;
  finished_at: number | null;
  error_message: string | null;
  params: Record<string, any>;
}

interface CrawlRequest {
  source_ids?: string[];
  source_types?: string[]; // 新增：按源类型批量抓取
  depth?: number;
  max_pages_per_source?: number;
  kb_id?: string; // 目标知识库ID
  parse?: boolean; // 是否自动解析
}

interface TopicSearchRequest {
  source_ids?: string[];
  source_types?: string[]; // 新增：按源类型批量搜索
  keywords: string[];
  max_depth?: number;
  max_pages_per_source?: number;
  max_crawl_pages_per_source?: number;
  score_threshold?: number;
  kb_id?: string;
  parse?: boolean;
}

// URL Seeding智能搜索请求接口
interface UrlSeedingSearchRequest {
  source_ids?: string[];
  source_types?: string[];
  keywords: string[];
  max_pages_per_source?: number;
  max_urls_per_source?: number; // 每源最大URL发现数量
  relevance_threshold?: number; // 相关性阈值（自定义评分）
  kb_id?: string;
  parse?: boolean;
}

interface PaginatedResponse<T> {
  sources: T[];
  total: number;
  page: number;
  page_size: number;
  groups?: string[]; // 新增：可用的源类型分组
}

// 分组响应接口
interface GroupedSourcesResponse {
  groups: {
    group: string;
    sources: NewsSource[];
  }[];
}

const API_BASE = '/v1/news_collector';

/**
 * 获取认证头
 * 优先级：
 * 1. 主系统登录态（localStorage.Authorization）
 * 2. 手动配置的 API Key（参数传入）
 * 3. localStorage 中的 apiKey
 */
const getAuthHeaders = (manualApiKey?: string) => {
  // 优先使用主系统登录态
  const authorization = localStorage.getItem('Authorization');
  if (authorization) {
    console.log('✅ 使用主系统登录态认证');
    return { Authorization: authorization };
  }

  // 降级到手动传入的 API Key
  if (manualApiKey) {
    console.log('✅ 使用手动配置的 API Key 认证');
    return { Authorization: `Bearer ${manualApiKey}` };
  }

  // 最后尝试从 localStorage 读取 apiKey
  const storedApiKey = localStorage.getItem('apiKey');
  if (storedApiKey) {
    console.log('✅ 使用存储的 API Key 认证');
    return { Authorization: `Bearer ${storedApiKey}` };
  }

  console.warn('⚠️ 未找到任何认证信息');
  return {};
};

/**
 * 检查是否有可用的认证信息
 */
export const hasAuthToken = (): boolean => {
  const authorization = localStorage.getItem('Authorization');
  const storedApiKey = localStorage.getItem('apiKey');
  return !!(authorization || storedApiKey);
};

/**
 * 获取当前认证方式
 */
export const getAuthType = (): 'login' | 'apikey' | 'none' => {
  const authorization = localStorage.getItem('Authorization');
  if (authorization) return 'login';

  const storedApiKey = localStorage.getItem('apiKey');
  if (storedApiKey) return 'apikey';

  return 'none';
};

// API健康检查
export const checkApiHealth = async (apiKey?: string) => {
  try {
    const response = await axios.get(`${API_BASE}/sources?page=1&page_size=1`, {
      headers: getAuthHeaders(apiKey),
      timeout: 5000, // 5秒超时
    });
    return { status: 'ok', data: response.data };
  } catch (error: any) {
    console.error('API健康检查失败:', error);
    return {
      status: 'error',
      error: error.response?.status === 404 ? '接口不存在' : '网络错误',
    };
  }
};

// 新闻源管理 CRUD - 添加更好的错误处理
export const getNewsSources = async (
  params?: {
    page?: number;
    page_size?: number;
    name?: string;
    status?: string;
    source_type?: string; // 新增：单个类型筛选
    source_types?: string; // 新增：多个类型筛选（逗号分隔）
  },
  apiKey?: string,
) => {
  const cleanParams = params
    ? Object.entries(params)
        .filter(([_, v]) => v !== undefined && v !== '')
        .reduce((acc, [k, v]) => ({ ...acc, [k]: v }), {})
    : {};

  const queryString =
    Object.keys(cleanParams).length > 0
      ? '?' +
        new URLSearchParams(cleanParams as Record<string, string>).toString()
      : '';

  const fullUrl = `${API_BASE}/sources${queryString}`;
  console.log('获取新闻源API请求URL:', fullUrl);
  console.log('请求头:', getAuthHeaders(apiKey));

  try {
    const response = await axios.get<{
      code: number;
      data: PaginatedResponse<NewsSource>;
    }>(fullUrl, {
      headers: getAuthHeaders(apiKey),
      timeout: 10000, // 10秒超时
    });
    console.log('获取新闻源API响应:', response.status, response.statusText);
    return response;
  } catch (error: any) {
    console.error('获取新闻源列表失败:', error);
    console.error('请求URL:', fullUrl);
    throw error;
  }
};

export const createNewsSource = async (data: NewsSource, apiKey?: string) => {
  const url = `${API_BASE}/sources`;
  console.log('创建新闻源API请求URL:', url);
  console.log('创建新闻源数据:', data);
  console.log('请求头:', getAuthHeaders(apiKey));

  try {
    const response = await axios.post(url, data, {
      headers: getAuthHeaders(apiKey),
      timeout: 10000,
    });
    console.log('创建新闻源API响应:', response.status, response.statusText);
    return response;
  } catch (error: any) {
    console.error('创建新闻源失败:', error);
    console.error('请求URL:', url);
    console.error('请求数据:', data);
    throw error;
  }
};

export const updateNewsSource = async (
  id: string,
  data: Partial<NewsSource>,
  apiKey?: string,
) => {
  try {
    return await axios.put(`${API_BASE}/sources/${id}`, data, {
      headers: getAuthHeaders(apiKey),
      timeout: 10000,
    });
  } catch (error: any) {
    console.error('更新新闻源失败:', error);
    throw error;
  }
};

export const deleteNewsSource = async (id: string, apiKey?: string) => {
  try {
    return await axios.delete(`${API_BASE}/sources/${id}`, {
      headers: getAuthHeaders(apiKey),
      timeout: 10000,
    });
  } catch (error: any) {
    console.error('删除新闻源失败:', error);
    throw error;
  }
};

// 新增：获取新闻源分组
export const getNewsSourceGroups = async (apiKey?: string) => {
  try {
    const response = await axios.get<{
      code: number;
      data: GroupedSourcesResponse;
    }>(`${API_BASE}/sources/groups`, {
      headers: getAuthHeaders(apiKey),
      timeout: 10000,
    });
    return response;
  } catch (error: any) {
    console.error('获取新闻源分组失败:', error);
    throw error;
  }
};

// 新增：批量导入新闻源（直接发送数组到 /sources 接口）
export const importNewsSources = async (
  sources: Partial<NewsSource>[],
  apiKey?: string,
) => {
  try {
    const response = await axios.post(`${API_BASE}/sources`, sources, {
      headers: getAuthHeaders(apiKey),
      timeout: 60000, // 批量导入可能需要更长时间
    });
    return response;
  } catch (error: any) {
    console.error('批量导入新闻源失败:', error);
    throw error;
  }
};

export const getNewsSource = (id: string, apiKey?: string) =>
  axios.get(`${API_BASE}/sources/${id}`, {
    headers: getAuthHeaders(apiKey),
  });

// 即时抓取功能
export const crawlFromPost = async (data: CrawlRequest, apiKey?: string) => {
  try {
    return await axios.post(`${API_BASE}/crawl_from_post`, data, {
      headers: getAuthHeaders(apiKey),
      timeout: 15000, // 抓取可能需要更长时间
    });
  } catch (error: any) {
    console.error('启动抓取任务失败:', error);
    throw error;
  }
};

// 主题搜索抓取功能
export const topicSearchCrawl = async (
  data: TopicSearchRequest,
  apiKey?: string,
) => {
  try {
    return await axios.post(`${API_BASE}/topic_search`, data, {
      headers: getAuthHeaders(apiKey),
      timeout: 15000, // 抓取可能需要更长时间
    });
  } catch (error: any) {
    console.error('启动主题搜索抓取任务失败:', error);
    throw error;
  }
};

// URL Seeding智能搜索抓取功能
export const urlSeedingCrawl = async (
  data: UrlSeedingSearchRequest,
  apiKey?: string,
) => {
  try {
    return await axios.post(`${API_BASE}/url_seeding_search`, data, {
      headers: getAuthHeaders(apiKey),
      timeout: 15000, // 抓取可能需要更长时间
    });
  } catch (error: any) {
    console.error('启动URL Seeding搜索抓取任务失败:', error);
    throw error;
  }
};

// 内容与哈希管理
export const getContentHashes = (
  params?: {
    page?: number;
    page_size?: number;
  },
  apiKey?: string,
) => {
  const queryString = params
    ? '?' +
      Object.entries(params)
        .filter(([_, v]) => v !== undefined)
        .map(([k, v]) => `${k}=${v}`)
        .join('&')
    : '';
  return axios.get(`${API_BASE}/contents/hashes${queryString}`, {
    headers: getAuthHeaders(apiKey),
  });
};

export const deleteAllContents = (apiKey?: string) =>
  axios.delete(`${API_BASE}/contents`, {
    headers: getAuthHeaders(apiKey),
  });

// 获取知识库列表 - 使用新闻收集器专用的知识库 API（支持登录态）
export const getDatasets = async (apiKey?: string) => {
  try {
    // 使用新闻收集器的专用知识库 API，支持登录态认证
    return await axios.get(`${API_BASE}/datasets`, {
      headers: getAuthHeaders(apiKey),
      timeout: 8000,
    });
  } catch (error: any) {
    console.error('获取知识库列表失败:', error);
    throw error;
  }
};

// 向后兼容的旧接口
export const addNewsSource = createNewsSource;
export const fetchNews = crawlFromPost;

// 源类型标签配置
export const SOURCE_TYPE_CONFIG = {
  policy: { label: '政策源', color: 'red' },
  news: { label: '新闻源', color: 'blue' },
  other: { label: '其他', color: 'default' },
} as const;

// ========== Target 管理 API ==========

// 获取 Target 列表
export const getTargets = async (
  params?: {
    page?: number;
    page_size?: number;
    group_id?: string;
    status?: string;
  },
  apiKey?: string,
) => {
  const cleanParams = params
    ? Object.entries(params)
        .filter(([_, v]) => v !== undefined && v !== '')
        .reduce((acc, [k, v]) => ({ ...acc, [k]: v }), {})
    : {};

  const queryString =
    Object.keys(cleanParams).length > 0
      ? '?' +
        new URLSearchParams(cleanParams as Record<string, string>).toString()
      : '';

  try {
    return await axios.get(`${API_BASE}/targets${queryString}`, {
      headers: getAuthHeaders(apiKey),
      timeout: 10000,
    });
  } catch (error: any) {
    console.error('获取 Target 列表失败:', error);
    throw error;
  }
};

// 创建 Target
export const createTarget = async (data: CrawlTarget, apiKey?: string) => {
  try {
    return await axios.post(`${API_BASE}/targets`, data, {
      headers: getAuthHeaders(apiKey),
      timeout: 10000,
    });
  } catch (error: any) {
    console.error('创建 Target 失败:', error);
    throw error;
  }
};

// 更新 Target
export const updateTarget = async (
  id: string,
  data: Partial<CrawlTarget>,
  apiKey?: string,
) => {
  try {
    return await axios.put(`${API_BASE}/targets/${id}`, data, {
      headers: getAuthHeaders(apiKey),
      timeout: 10000,
    });
  } catch (error: any) {
    console.error('更新 Target 失败:', error);
    throw error;
  }
};

// 删除 Target
export const deleteTarget = async (id: string, apiKey?: string) => {
  try {
    return await axios.delete(`${API_BASE}/targets/${id}`, {
      headers: getAuthHeaders(apiKey),
      timeout: 10000,
    });
  } catch (error: any) {
    console.error('删除 Target 失败:', error);
    throw error;
  }
};

// 运行 Target
export const runTargets = async (targetIds: string[], apiKey?: string) => {
  try {
    return await axios.post(
      `${API_BASE}/targets/run`,
      { target_ids: targetIds },
      {
        headers: getAuthHeaders(apiKey),
        timeout: 15000,
      },
    );
  } catch (error: any) {
    console.error('运行 Target 失败:', error);
    throw error;
  }
};

// ========== Target Group 管理 API ==========

// 获取 Target Group 列表
export const getTargetGroups = async (apiKey?: string) => {
  try {
    return await axios.get(`${API_BASE}/target_groups`, {
      headers: getAuthHeaders(apiKey),
      timeout: 10000,
    });
  } catch (error: any) {
    console.error('获取 Target Group 列表失败:', error);
    throw error;
  }
};

// 创建 Target Group
export const createTargetGroup = async (data: TargetGroup, apiKey?: string) => {
  try {
    return await axios.post(`${API_BASE}/target_groups`, data, {
      headers: getAuthHeaders(apiKey),
      timeout: 10000,
    });
  } catch (error: any) {
    console.error('创建 Target Group 失败:', error);
    throw error;
  }
};

// ========== Task Log API ==========

// 获取任务日志
export const getTaskLogs = async (
  params?: {
    page?: number;
    page_size?: number;
    target_id?: string;
    status?: string;
  },
  apiKey?: string,
) => {
  const cleanParams = params
    ? Object.entries(params)
        .filter(([_, v]) => v !== undefined && v !== '')
        .reduce((acc, [k, v]) => ({ ...acc, [k]: v }), {})
    : {};

  const queryString =
    Object.keys(cleanParams).length > 0
      ? '?' +
        new URLSearchParams(cleanParams as Record<string, string>).toString()
      : '';

  try {
    return await axios.get(`${API_BASE}/task_logs${queryString}`, {
      headers: getAuthHeaders(apiKey),
      timeout: 10000,
    });
  } catch (error: any) {
    console.error('获取任务日志失败:', error);
    throw error;
  }
};

// 导出类型
export type {
  CrawlRequest,
  CrawlTarget,
  GroupedSourcesResponse,
  NewsSource,
  PaginatedResponse,
  TargetGroup,
  TaskLog,
  TopicSearchRequest,
  UrlSeedingSearchRequest,
};
