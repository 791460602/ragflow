import axios from 'axios';

// 获取新闻源列表
export const getNewsSources = () => axios.get('/api/news_collector/sources');
// 新增新闻源
export const addNewsSource = (data) => axios.post('/api/news_collector/sources', data);
// 删除新闻源
export const deleteNewsSource = (id) => axios.delete(`/api/news_collector/sources/${id}`);
// 抓取新闻
export const fetchNews = (data, apiKey) => axios.post('/api/news_collector/fetch', data, { headers: { Authorization: 'Bearer ' + apiKey } });
// 获取抓取历史
export const getHistory = () => axios.get('/api/news_collector/history');
// 获取知识库列表
export const getDatasets = (apiKey) => axios.get('/api/sdk/dataset/datasets', { headers: { Authorization: 'Bearer ' + apiKey } }); 