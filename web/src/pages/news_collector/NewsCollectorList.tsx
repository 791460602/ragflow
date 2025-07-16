import React from 'react';

interface NewsSource {
  id: number;
  name: string;
  url: string;
  remark?: string;
}

interface NewsCollectorListProps {
  sources: NewsSource[];
  onDelete: (id: number) => void;
}

const NewsCollectorList: React.FC<NewsCollectorListProps> = ({ sources, onDelete }) => {
  return (
    <table style={{ width: '100%', marginTop: 16, borderCollapse: 'collapse' }}>
      <thead>
        <tr>
          <th>名称</th>
          <th>URL</th>
          <th>备注</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        {sources.map(source => (
          <tr key={source.id}>
            <td>{source.name}</td>
            <td>{source.url}</td>
            <td>{source.remark}</td>
            <td>
              <button onClick={() => onDelete(source.id)}>删除</button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
};

export default NewsCollectorList; 