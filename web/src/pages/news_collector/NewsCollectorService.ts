import axios from 'axios';

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
}

interface CrawlRequest {
  source_ids: string[];
  depth?: number;
  max_pages_per_source?: number;
  kb_id?: string;  // 目标知识库ID
}

interface PaginatedResponse<T> {
  sources: T[];
  total: number;
  page: number;
  page_size: number;
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
      timeout: 5000 // 5秒超时
    });
    return { status: 'ok', data: response.data };
  } catch (error: any) {
    console.error('API健康检查失败:', error);
    return { 
      status: 'error', 
      error: error.response?.status === 404 ? '接口不存在' : '网络错误' 
    };
  }
};

// 新闻源管理 CRUD - 添加更好的错误处理
export const getNewsSources = async (params?: {
  page?: number;
  page_size?: number;
  name?: string;
  status?: string;
}, apiKey?: string) => {
  const cleanParams = params ? 
    Object.entries(params)
      .filter(([_, v]) => v !== undefined && v !== '')
      .reduce((acc, [k, v]) => ({ ...acc, [k]: v }), {}) : {};
  
  const queryString = Object.keys(cleanParams).length > 0 ? 
    '?' + new URLSearchParams(cleanParams as Record<string, string>).toString() : '';
  
  const fullUrl = `${API_BASE}/sources${queryString}`;
  console.log('获取新闻源API请求URL:', fullUrl);
  console.log('请求头:', getAuthHeaders(apiKey));
  
  try {
    const response = await axios.get<{ code: number; data: PaginatedResponse<NewsSource> }>(fullUrl, {
      headers: getAuthHeaders(apiKey),
      timeout: 10000 // 10秒超时
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
      timeout: 10000
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

export const updateNewsSource = async (id: string, data: Partial<NewsSource>, apiKey?: string) => {
  try {
    return await axios.put(`${API_BASE}/sources/${id}`, data, {
      headers: getAuthHeaders(apiKey),
      timeout: 10000
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
      timeout: 10000
    });
  } catch (error: any) {
    console.error('删除新闻源失败:', error);
    throw error;
  }
};

export const getNewsSource = (id: string, apiKey?: string) => 
  axios.get(`${API_BASE}/sources/${id}`, {
    headers: getAuthHeaders(apiKey)
  });

// 即时抓取功能
export const crawlFromPost = async (data: CrawlRequest, apiKey?: string) => {
  try {
    return await axios.post(`${API_BASE}/crawl_from_post`, data, {
      headers: getAuthHeaders(apiKey),
      timeout: 15000 // 抓取可能需要更长时间
    });
  } catch (error: any) {
    console.error('启动抓取任务失败:', error);
    throw error;
  }
};

// 内容与哈希管理
export const getContentHashes = (params?: {
  page?: number;
  page_size?: number;
}, apiKey?: string) => {
  const queryString = params ? 
    '?' + Object.entries(params).filter(([_, v]) => v !== undefined).map(([k, v]) => `${k}=${v}`).join('&') :
    '';
  return axios.get(`${API_BASE}/contents/hashes${queryString}`, {
    headers: getAuthHeaders(apiKey)
  });
};

export const deleteAllContents = (apiKey?: string) => 
  axios.delete(`${API_BASE}/contents`, {
    headers: getAuthHeaders(apiKey)
  });

// 获取知识库列表 - 使用新闻收集器专用的知识库 API（支持登录态）
export const getDatasets = async (apiKey?: string) => {
  try {
    // 使用新闻收集器的专用知识库 API，支持登录态认证
    return await axios.get(`${API_BASE}/datasets`, { 
      headers: getAuthHeaders(apiKey),
      timeout: 8000
    });
  } catch (error: any) {
    console.error('获取知识库列表失败:', error);
    throw error;
  }
};

// 向后兼容的旧接口
export const addNewsSource = createNewsSource;
export const fetchNews = crawlFromPost;

// 导出类型
export type { NewsSource, CrawlRequest, PaginatedResponse }; 