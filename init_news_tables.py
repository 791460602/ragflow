#!/usr/bin/env python3
"""
新闻收集器数据库初始化脚本

运行此脚本可以在数据库中创建新闻收集器所需的表结构。
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.db.db_models import NewsSource, NewsTask, NewsContent, DB

def init_news_tables():
    """初始化新闻收集器数据表"""
    print("开始初始化新闻收集器数据表...")
    
    with DB.connection_context():
        tables = [NewsSource, NewsTask, NewsContent]
        
        for table in tables:
            table_name = table._meta.table_name
            try:
                if table.table_exists():
                    print(f"表 {table_name} 已存在，跳过创建")
                else:
                    table.create_table()
                    print(f"成功创建表: {table_name}")
            except Exception as e:
                print(f"创建表 {table_name} 失败: {e}")
                return False
    
    print("新闻收集器数据表初始化完成！")
    return True

if __name__ == "__main__":
    try:
        success = init_news_tables()
        if success:
            print("\n✅ 数据库初始化成功！")
            print("现在可以使用新闻收集器API了。")
        else:
            print("\n❌ 数据库初始化失败！")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ 初始化过程中发生错误: {e}")
        sys.exit(1)
