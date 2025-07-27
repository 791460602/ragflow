"""
新闻爬虫工具实现示例

基于抽象接口的具体爬虫实现，展示如何扩展新闻收集器
"""

import os
import json
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse

from ..interfaces.news_crawler_interface import (
    INewsCrawler, NewsSource, NewsArticle, CrawlTask, CrawlResult, CrawlerStatus
)


class ScrapyNewsCrawler(INewsCrawler):
    """基于Scrapy的新闻爬虫实现"""
    
    def __init__(self, scrapy_project_path: str = None):
        self.scrapy_project_path = scrapy_project_path
        self.supported_domains = [
            "tech.sina.com.cn",
            "tech.163.com",
            "36kr.com",
            "ithome.com"
        ]
    
    def validate_source(self, source: NewsSource) -> bool:
        """验证新闻源是否支持"""
        try:
            domain = urlparse(source.url).netloc
            return domain in self.supported_domains
        except:
            return False
    
    def crawl_articles(self, task: CrawlTask) -> CrawlResult:
        """执行Scrapy爬虫任务"""
        result = CrawlResult(
            task_id=task.task_id,
            status=CrawlerStatus.RUNNING,
            output_directory=task.output_directory
        )
        
        try:
            # 确保输出目录存在
            os.makedirs(task.output_directory, exist_ok=True)
            
            all_articles = []
            
            for source in task.sources:
                if not self.validate_source(source):
                    result.skipped_count += 1
                    continue
                
                # 执行Scrapy爬虫
                articles = self._run_scrapy_spider(source, task)
                all_articles.extend(articles)
                
                # 保存文章到目录
                success = self.save_articles_to_directory(
                    articles, task.output_directory, source.name
                )
                
                if success:
                    result.success_count += len(articles)
                else:
                    result.failed_count += len(articles)
            
            result.articles = all_articles
            result.total_articles = len(all_articles)
            result.status = CrawlerStatus.COMPLETED
            
        except Exception as e:
            result.status = CrawlerStatus.FAILED
            result.error_message = str(e)
        
        return result
    
    def get_supported_domains(self) -> List[str]:
        """获取支持的域名列表"""
        return self.supported_domains
    
    def _run_scrapy_spider(self, source: NewsSource, task: CrawlTask) -> List[NewsArticle]:
        """运行Scrapy爬虫"""
        # 这里是Scrapy爬虫的具体实现
        # 为了演示，我们生成模拟数据
        
        articles = []
        domain = urlparse(source.url).netloc
        
        # 根据不同域名生成不同内容
        if "sina" in domain:
            articles = self._crawl_sina_tech(source, task.max_articles_per_source)
        elif "163" in domain:
            articles = self._crawl_163_tech(source, task.max_articles_per_source)
        elif "36kr" in domain:
            articles = self._crawl_36kr(source, task.max_articles_per_source)
        elif "ithome" in domain:
            articles = self._crawl_ithome(source, task.max_articles_per_source)
        
        return articles
    
    def _crawl_sina_tech(self, source: NewsSource, max_count: int) -> List[NewsArticle]:
        """爬取新浪科技新闻"""
        articles = []
        
        for i in range(min(max_count, 5)):
            article = NewsArticle(
                title=f"新浪科技：AI技术新突破 {i+1}",
                content=f"""
# 新浪科技：AI技术新突破 {i+1}

## 新闻概要
本文报道了最新的人工智能技术发展动态，展示了AI在各个领域的应用进展。

## 技术要点
1. **深度学习算法优化**
   - 模型压缩技术取得新进展
   - 推理速度提升了30%
   - 内存占用减少了40%

2. **应用场景扩展**
   - 智能制造领域应用
   - 医疗诊断辅助系统
   - 自动驾驶技术升级

## 市场影响
这些技术突破将对相关产业产生深远影响：
- 降低AI应用门槛
- 提高部署效率
- 减少运营成本

## 专家观点
业内专家认为，这些进展标志着AI技术正在向更加实用化的方向发展。

## 未来展望
预计未来6个月内，这些技术将开始在实际项目中得到应用。

---
*报道时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
                """,
                url=f"{source.url}/article/ai-breakthrough-{i+1}",
                author="新浪科技记者",
                publish_time=datetime.now(),
                category="人工智能",
                tags=["AI", "技术突破", "深度学习"],
                summary="报道了最新的AI技术突破和应用进展"
            )
            articles.append(article)
        
        return articles
    
    def _crawl_163_tech(self, source: NewsSource, max_count: int) -> List[NewsArticle]:
        """爬取网易科技新闻"""
        articles = []
        
        for i in range(min(max_count, 5)):
            article = NewsArticle(
                title=f"网易科技：云计算新趋势 {i+1}",
                content=f"""
# 网易科技：云计算新趋势 {i+1}

## 行业动态
云计算领域正在经历新一轮的技术革新，各大厂商纷纷推出创新解决方案。

## 技术趋势
1. **边缘计算兴起**
   - 降低延迟需求
   - 数据本地化处理
   - 提升用户体验

2. **容器化部署**
   - Kubernetes生态成熟
   - 微服务架构普及
   - DevOps流程优化

3. **安全性增强**
   - 零信任架构
   - 数据加密升级
   - 合规性保障

## 市场分析
根据最新研究报告：
- 全球云计算市场预计增长25%
- 企业数字化转型加速
- 多云策略成为主流

## 案例研究
某大型企业通过云原生改造：
- 部署效率提升50%
- 运维成本降低30%
- 系统可用性达到99.9%

---
*发布时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
                """,
                url=f"{source.url}/tech/cloud-trends-{i+1}",
                author="网易科技编辑部",
                publish_time=datetime.now(),
                category="云计算",
                tags=["云计算", "边缘计算", "容器化"],
                summary="分析了云计算领域的最新技术趋势和市场动态"
            )
            articles.append(article)
        
        return articles
    
    def _crawl_36kr(self, source: NewsSource, max_count: int) -> List[NewsArticle]:
        """爬取36氪新闻"""
        articles = []
        
        for i in range(min(max_count, 5)):
            article = NewsArticle(
                title=f"36氪：创业公司融资动态 {i+1}",
                content=f"""
# 36氪：创业公司融资动态 {i+1}

## 融资概况
本周科技创业领域出现多起重要融资事件，显示出投资市场对新兴技术的持续关注。

## 重点事件
1. **AI芯片公司完成B轮融资**
   - 融资金额：2亿美元
   - 投资方：知名风投基金
   - 应用领域：边缘AI计算

2. **量子计算初创公司获投**
   - 融资规模：5000万美元
   - 技术特点：量子纠错算法
   - 商业化前景：金融科技应用

3. **生物技术公司Pre-A轮**
   - 资金规模：3000万美元
   - 研发方向：基因编辑技术
   - 市场定位：精准医疗

## 投资趋势分析
- 硬科技赛道持续升温
- 投资阶段前移，早期项目受青睐
- 产业应用能力成为关键评估指标

## 市场前景
分析师认为，随着技术成熟度提升，这些领域将迎来爆发式增长。

---
*36氪报道 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
                """,
                url=f"{source.url}/p/{i+100000}",
                author="36氪记者",
                publish_time=datetime.now(),
                category="创业投资",
                tags=["融资", "创业", "AI芯片", "量子计算"],
                summary="报道了科技创业领域的最新融资动态和投资趋势"
            )
            articles.append(article)
        
        return articles
    
    def _crawl_ithome(self, source: NewsSource, max_count: int) -> List[NewsArticle]:
        """爬取IT之家新闻"""
        articles = []
        
        for i in range(min(max_count, 5)):
            article = NewsArticle(
                title=f"IT之家：硬件新品发布 {i+1}",
                content=f"""
# IT之家：硬件新品发布 {i+1}

## 产品发布
今日多家厂商发布了新一代硬件产品，涵盖处理器、显卡、存储等多个领域。

## 新品亮点
1. **新一代处理器**
   - 制程工艺：3nm
   - 性能提升：较上代提升15%
   - 功耗控制：降低20%

2. **高性能显卡**
   - 光线追踪：第三代RT核心
   - AI加速：专用AI处理单元
   - 内存配置：24GB GDDR6X

3. **固态硬盘**
   - 接口标准：PCIe 5.0
   - 读取速度：12GB/s
   - 容量选择：1TB-8TB

## 技术解析
这些新品在技术上实现了多项突破：
- 架构设计更加高效
- 制造工艺持续进步
- 软硬件协同优化

## 市场定位
- 专业用户：内容创作、科学计算
- 游戏玩家：4K高刷新率游戏
- 企业级：数据中心、AI训练

## 价格信息
预计产品将于下月正式上市，价格区间从中端到高端全覆盖。

---
*IT之家 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
                """,
                url=f"{source.url}/news/{i+500000}",
                author="IT之家编辑",
                publish_time=datetime.now(),
                category="硬件产品",
                tags=["硬件", "处理器", "显卡", "存储"],
                summary="报道了多家厂商发布的新一代硬件产品及其技术特点"
            )
            articles.append(article)
        
        return articles


class NewspaperNewsCrawler(INewsCrawler):
    """基于Newspaper3k的新闻爬虫实现"""
    
    def __init__(self):
        self.supported_domains = ["*"]  # 支持通用网站
    
    def validate_source(self, source: NewsSource) -> bool:
        """验证新闻源是否有效"""
        try:
            return source.url.startswith(('http://', 'https://'))
        except:
            return False
    
    def crawl_articles(self, task: CrawlTask) -> CrawlResult:
        """执行Newspaper3k爬虫任务"""
        result = CrawlResult(
            task_id=task.task_id,
            status=CrawlerStatus.RUNNING,
            output_directory=task.output_directory
        )
        
        try:
            # 这里应该调用newspaper3k库
            # 为了演示，返回模拟结果
            
            os.makedirs(task.output_directory, exist_ok=True)
            
            all_articles = []
            
            for source in task.sources:
                # 模拟newspaper3k抓取
                articles = self._newspaper_crawl(source, task.max_articles_per_source)
                all_articles.extend(articles)
                
                # 保存文章
                success = self.save_articles_to_directory(
                    articles, task.output_directory, source.name
                )
                
                if success:
                    result.success_count += len(articles)
                else:
                    result.failed_count += len(articles)
            
            result.articles = all_articles
            result.total_articles = len(all_articles)
            result.status = CrawlerStatus.COMPLETED
            
        except Exception as e:
            result.status = CrawlerStatus.FAILED
            result.error_message = str(e)
        
        return result
    
    def get_supported_domains(self) -> List[str]:
        """获取支持的域名列表"""
        return self.supported_domains
    
    def _newspaper_crawl(self, source: NewsSource, max_count: int) -> List[NewsArticle]:
        """模拟newspaper3k抓取"""
        articles = []
        
        for i in range(min(max_count, 3)):
            article = NewsArticle(
                title=f"Newspaper3k抓取: {source.name}通用新闻 {i+1}",
                content=f"""
# Newspaper3k抓取: {source.name}通用新闻 {i+1}

## 新闻内容
这是通过Newspaper3k库自动抓取的新闻内容，该库能够智能识别网页中的新闻正文。

## 技术优势
Newspaper3k具有以下特点：
- 自动识别新闻正文
- 提取标题、作者、发布时间
- 支持多种语言
- 处理各种网页结构

## 应用场景
- 新闻聚合网站
- 舆情监控系统
- 内容分析平台
- 知识库构建

## 实现细节
```python
import newspaper

# 创建新闻源
paper = newspaper.build(source.url)

# 获取文章列表
for article in paper.articles:
    article.download()
    article.parse()
    article.nlp()
```

## 数据质量
通过自动化抓取，确保了：
- 内容完整性
- 格式规范化
- 元数据准确性

---
*Newspaper3k自动抓取于 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
                """,
                url=f"{source.url}/auto-article-{i+1}",
                author="自动识别",
                publish_time=datetime.now(),
                category="通用新闻",
                tags=["自动抓取", "Newspaper3k", "通用"],
                summary="通过Newspaper3k库自动抓取的通用新闻内容"
            )
            articles.append(article)
        
        return articles


class DemoCrawler(INewsCrawler):
    """演示爬虫 - 生成示例数据"""
    
    def __init__(self):
        self.supported_domains = ["*"]  # 支持所有域名
    
    def validate_source(self, source: NewsSource) -> bool:
        """验证新闻源是否有效"""
        try:
            return source.url.startswith(('http://', 'https://'))
        except:
            return False
    
    def crawl_articles(self, task: CrawlTask) -> CrawlResult:
        """执行演示爬虫任务 - 生成模拟数据"""
        result = CrawlResult(
            task_id=task.task_id,
            status=CrawlerStatus.RUNNING,
            output_directory=task.output_directory
        )
        
        try:
            # 确保输出目录存在
            os.makedirs(task.output_directory, exist_ok=True)
            
            all_articles = []
            error_messages = []
            
            for source in task.sources:
                try:
                    # 生成演示文章
                    articles = self._generate_demo_articles(source, task.max_articles_per_source)
                    all_articles.extend(articles)
                    
                    # 保存文章，增加详细错误处理
                    try:
                        success = self.save_articles_to_directory(
                            articles, task.output_directory, source.name
                        )
                        
                        if success:
                            result.success_count += len(articles)
                        else:
                            result.failed_count += len(articles)
                            error_messages.append(f"保存文章失败: {source.name}")
                    except Exception as save_error:
                        result.failed_count += len(articles)
                        error_msg = f"保存文章异常: {source.name} - {str(save_error)}"
                        error_messages.append(error_msg)
                        print(f"❌ {error_msg}")  # 添加控制台输出
                        
                except Exception as source_error:
                    error_msg = f"处理新闻源失败: {source.name} - {str(source_error)}"
                    error_messages.append(error_msg)
                    print(f"❌ {error_msg}")  # 添加控制台输出
            
            result.articles = all_articles
            result.total_articles = len(all_articles)
            result.status = CrawlerStatus.COMPLETED
            
            # 汇总错误信息
            if error_messages:
                result.error_message = "; ".join(error_messages)
                print(f"⚠️  Demo爬虫完成，但有错误: {result.error_message}")
            else:
                print(f"✅ Demo爬虫完成，生成 {result.total_articles} 篇文章")
            
        except Exception as e:
            result.status = CrawlerStatus.FAILED
            result.error_message = str(e)
            print(f"❌ Demo爬虫执行失败: {e}")
        
        return result
    
    def get_supported_domains(self) -> List[str]:
        """获取支持的域名列表"""
        return self.supported_domains
    
    def _generate_demo_articles(self, source: NewsSource, max_count: int) -> List[NewsArticle]:
        """生成演示文章"""
        articles = []
        
        # 根据新闻源名称生成不同类型的内容
        if "新浪" in source.name:
            articles = self._generate_sina_demo(source, max_count)
        elif "网易" in source.name:
            articles = self._generate_163_demo(source, max_count)
        elif "36" in source.name:
            articles = self._generate_36kr_demo(source, max_count)
        else:
            articles = self._generate_generic_demo(source, max_count)
        
        return articles
    
    def _generate_sina_demo(self, source: NewsSource, max_count: int) -> List[NewsArticle]:
        """生成新浪科技演示文章"""
        articles = []
        
        topics = [
            "人工智能技术突破新里程碑",
            "5G网络建设取得重大进展", 
            "电动汽车技术创新发展",
            "云计算市场竞争加剧",
            "半导体产业链重构"
        ]
        
        for i in range(min(max_count, len(topics))):
            article = NewsArticle(
                title=f"【新浪科技演示】{topics[i]}",
                content=f"""# {topics[i]}

## 新闻摘要
这是一篇由演示爬虫生成的新浪科技新闻文章，展示了新闻收集器的基本功能。

## 技术要点
1. **技术创新**：介绍最新的技术发展动态
2. **市场分析**：分析行业发展趋势和竞争格局  
3. **应用场景**：探讨技术在实际应用中的价值

## 深度解析
当前科技行业正在经历快速变革，各种新兴技术不断涌现。企业需要密切关注技术发展趋势，及时调整战略布局。

### 核心观点
- 技术创新是企业发展的核心驱动力
- 市场竞争日趋激烈，需要差异化策略
- 用户体验成为产品成功的关键因素

## 行业影响
这一发展将对整个行业产生深远影响，推动相关产业链的升级和转型。

## 未来展望
专家预测，未来3-5年内，相关技术将迎来大规模商业化应用。

---
*本文由新闻收集器演示爬虫生成，仅用于功能测试*
*生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
                """,
                url=f"{source.url}demo/article/{i+1}",
                author="新浪科技记者",
                publish_time=datetime.now(),
                category="科技新闻",
                tags=["科技", "创新", "市场分析"],
                summary=f"介绍了{topics[i]}的最新发展情况和行业影响"
            )
            articles.append(article)
        
        return articles
    
    def _generate_163_demo(self, source: NewsSource, max_count: int) -> List[NewsArticle]:
        """生成网易科技演示文章"""
        articles = []
        
        topics = [
            "互联网企业数字化转型加速",
            "大数据技术在金融领域应用", 
            "区块链技术标准化进程",
            "物联网设备安全挑战",
            "边缘计算发展趋势分析"
        ]
        
        for i in range(min(max_count, len(topics))):
            article = NewsArticle(
                title=f"【网易科技演示】{topics[i]}",
                content=f"""# {topics[i]}

## 行业背景
当前数字化转型已成为企业发展的必然选择，各行各业都在积极探索数字化升级路径。

## 发展现状
根据最新调研数据显示：
- 90%的企业已启动数字化转型项目
- 技术投入平均占营收的12%
- 数字化程度与企业绩效呈正相关

## 技术架构
现代企业数字化架构主要包括：

### 基础设施层
- 云计算平台
- 大数据存储
- 网络安全防护

### 应用服务层  
- 业务管理系统
- 数据分析平台
- 用户交互界面

### 数据智能层
- 机器学习算法
- 预测分析模型
- 智能决策支持

## 实施策略
成功的数字化转型需要：
1. 制定清晰的数字化战略
2. 建立跨部门协作机制
3. 培养数字化人才团队
4. 构建敏捷的技术架构

## 挑战与机遇
虽然数字化转型面临技术、资金、人才等多重挑战，但也为企业带来了前所未有的发展机遇。

---
*网易科技演示内容 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
                """,
                url=f"{source.url}demo/tech/{i+1}",
                author="网易科技编辑",
                publish_time=datetime.now(),
                category="企业科技",
                tags=["数字化", "转型", "技术架构"],
                summary=f"分析了{topics[i]}的现状、挑战和发展前景"
            )
            articles.append(article)
        
        return articles
    
    def _generate_36kr_demo(self, source: NewsSource, max_count: int) -> List[NewsArticle]:
        """生成36氪演示文章"""
        articles = []
        
        topics = [
            "AI独角兽企业估值创新高",
            "新能源汽车供应链重塑", 
            "SaaS企业商业模式创新",
            "跨境电商平台竞争格局",
            "元宇宙技术商业化探索"
        ]
        
        for i in range(min(max_count, len(topics))):
            article = NewsArticle(
                title=f"【36氪演示】{topics[i]}",
                content=f"""# {topics[i]}

## 投资热点
创投市场持续关注新兴技术领域，投资活跃度不断提升。

## 融资动态
### 最新融资事件
本周科技领域共发生15起融资事件，总融资金额超过50亿元人民币。

### 投资机构动向
- 顶级VC加大早期项目投资
- 产业基金积极布局战略赛道  
- 国际资本持续看好中国市场

## 市场分析
### 行业趋势
1. **技术成熟度提升**
   - 算法性能持续优化
   - 应用场景不断拓展
   - 商业化进程加速

2. **竞争格局变化**
   - 头部企业优势巩固
   - 新兴玩家崭露头角
   - 跨界合作增多

3. **用户需求演进**
   - 个性化需求增强
   - 体验要求提高
   - 价格敏感度下降

## 商业模式
### 盈利途径
- 产品销售收入
- 服务订阅费用
- 平台交易佣金
- 数据授权许可

### 成本结构
- 研发投入占比最高
- 市场推广费用增长
- 人力成本持续上升

## 风险与机遇
市场机遇与挑战并存，企业需要在快速发展中保持理性和谨慎。

---
*36氪创投观察 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
                """,
                url=f"{source.url}demo/startup/{i+1}",
                author="36氪分析师",
                publish_time=datetime.now(),
                category="创业投资",
                tags=["创业", "投资", "市场分析"],
                summary=f"深度分析了{topics[i]}的投资价值和市场前景"
            )
            articles.append(article)
        
        return articles
    
    def _generate_generic_demo(self, source: NewsSource, max_count: int) -> List[NewsArticle]:
        """生成通用演示文章"""
        articles = []
        
        for i in range(max_count):
            article = NewsArticle(
                title=f"【演示新闻】{source.name}通用新闻内容 {i+1}",
                content=f"""# {source.name}通用新闻内容 {i+1}

## 新闻概述
这是由新闻收集器演示爬虫生成的通用新闻内容，用于验证系统功能。

## 主要内容
1. **新闻要点**：介绍新闻的核心信息
2. **背景分析**：提供相关背景和上下文
3. **影响评估**：分析新闻的潜在影响

## 详细报道
当前时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

这篇演示文章展示了新闻收集器处理各种新闻源的能力，包括：
- 文章标题提取
- 正文内容格式化
- 元数据信息整理
- Markdown格式输出

## 技术特点
- 支持多种新闻源格式
- 自动内容清理和格式化
- 智能元数据提取
- 标准化输出格式

## 应用价值
通过演示爬虫，用户可以：
- 验证系统基本功能
- 测试集成流程
- 评估处理效果
- 优化配置参数

---
*演示内容由新闻收集器自动生成*
                """,
                url=f"{source.url}demo/generic/{i+1}",
                author="演示爬虫",
                publish_time=datetime.now(),
                category="演示新闻",
                tags=["演示", "测试", "通用"],
                summary="这是一篇演示新闻，用于测试新闻收集器的基本功能"
            )
            articles.append(article)
        
        return articles


# Newspaper3k爬虫类名修正
class Newspaper3kCrawler(NewspaperNewsCrawler):
    """Newspaper3k爬虫的别名，保持兼容性"""
    pass


# 爬虫注册和管理
class CrawlerRegistry:
    """爬虫注册器"""
    
    def __init__(self):
        self.crawlers = {}
        self._register_default_crawlers()
    
    def _register_default_crawlers(self):
        """注册默认爬虫"""
        # 注册DemoCrawler作为默认演示爬虫
        demo_crawler = DemoCrawler()
        self.crawlers["demo"] = demo_crawler
        
        # 注册Scrapy爬虫
        scrapy_crawler = ScrapyNewsCrawler()
        for domain in scrapy_crawler.get_supported_domains():
            self.crawlers[domain] = scrapy_crawler
        
        # 注册Newspaper3k爬虫作为通用爬虫
        self.crawlers["*"] = NewspaperNewsCrawler()
    
    def register_crawler(self, crawler: INewsCrawler, domains: List[str]):
        """注册自定义爬虫"""
        for domain in domains:
            self.crawlers[domain] = crawler
    
    def get_crawler(self, domain: str) -> INewsCrawler:
        """获取适合的爬虫"""
        # 先查找精确匹配
        if domain in self.crawlers:
            return self.crawlers[domain]
        
        # 查找通配符匹配
        if "*" in self.crawlers:
            return self.crawlers["*"]
        
        # 返回None表示不支持
        return None
    
    def list_supported_domains(self) -> List[str]:
        """列出所有支持的域名"""
        return list(self.crawlers.keys())


# 全局爬虫注册器
crawler_registry = CrawlerRegistry()
