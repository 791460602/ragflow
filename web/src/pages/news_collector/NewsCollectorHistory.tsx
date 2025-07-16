import React from 'react';

interface NewsHistoryItem {
  id: number;
  sourceName: string;
  title: string;
  status: string;
  createdAt: string;
}

interface NewsCollectorHistoryProps {
  history: NewsHistoryItem[];
}

const NewsCollectorHistory: React.FC<NewsCollectorHistoryProps> = ({ history }) => {
  return (
    <div style={{ marginTop: 32 }}>
      <h2>抓取历史</h2>
      <table style={{ width: '100%', borderCollapse: 'collapse' }}>
        <thead>
          <tr>
            <th>来源</th>
            <th>标题</th>
            <th>状态</th>
            <th>时间</th>
          </tr>
        </thead>
        <tbody>
          {history.map(item => (
            <tr key={item.id}>
              <td>{item.sourceName}</td>
              <td>{item.title}</td>
              <td>{item.status}</td>
              <td>{item.createdAt}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default NewsCollectorHistory; 