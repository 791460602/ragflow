@echo off
REM 新闻抓取系统 Windows 安装脚本

echo 🚀 安装新闻抓取系统依赖包...

REM 检查Python版本
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python 未安装或不在PATH中
    echo 请先安装 Python 3.7+ 版本
    pause
    exit /b 1
)

echo ✅ Python 已安装

REM 升级pip
echo 📦 升级pip...
python -m pip install --upgrade pip

REM 安装核心依赖
echo 📦 安装核心依赖包...
python -m pip install aiohttp>=3.8.0
python -m pip install beautifulsoup4>=4.11.0
python -m pip install flask>=2.0.0
python -m pip install requests>=2.28.0

REM 安装可选依赖
echo 📦 安装可选依赖包...
python -m pip install python-dateutil>=2.8.0
python -m pip install pyyaml>=6.0
python -m pip install python-dotenv>=1.0.0
python -m pip install colorlog>=6.7.0

REM 安装测试依赖
echo 📦 安装测试依赖包...
python -m pip install pytest>=7.0.0
python -m pip install pytest-asyncio>=0.21.0

REM 创建日志目录
if not exist "logs" (
    mkdir logs
    echo ✅ 创建日志目录
)

REM 创建配置文件（如果不存在）
if not exist ".env" (
    echo # 新闻抓取系统环境变量配置 > .env
    echo RAGFLOW_API_KEY=ragflow-M3NDJjZmEyNjYwZDExZjBhMTAwYjlkOD >> .env
    echo RAGFLOW_BASE_URL=http://localhost:9380 >> .env
    echo LOG_LEVEL=INFO >> .env
    echo SCRAPER_TIMEOUT=30 >> .env
    echo SCRAPER_MAX_CONCURRENT=10 >> .env
    echo ✅ 创建配置文件 .env
)

echo.
echo ✅ 安装完成！
echo.
echo 📋 下一步：
echo 1. 确保 RAGFlow 服务正在运行
echo 2. 检查 .env 文件中的配置
echo 3. 运行测试：python test_news_collector.py
echo 4. 初始化系统：python setup_news_collector.py
echo.

pause
