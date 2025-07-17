# 🔍 招标廉政体检系统

基于AI的招标文件风险分析平台，帮助识别招标文件中的潜在廉政风险。

## ✨ 功能特性

### 🎯 核心功能
- **智能文档解析**: 支持.docx和.pdf格式招标文件的自动解析
- **规则引擎**: 基于预定义规则快速识别风险点
- **AI深度分析**: 集成大语言模型进行智能风险评估
- **多维度检查**: 预算合理性、地域限制、资质要求等专项检查
- **可视化报告**: 直观的风险分析报告和图表展示

### 🛡️ 安全特性
- **文件验证**: 严格的文件格式和大小限制
- **错误处理**: 完善的异常处理和错误恢复机制
- **配置管理**: 集中化的配置管理和环境变量支持
- **日志记录**: 详细的操作日志和审计跟踪

### 🚀 性能优化
- **异步处理**: 支持并发LLM调用和批量处理
- **缓存机制**: 智能缓存提升响应速度
- **资源限制**: 合理的并发控制和超时设置
- **热重载**: 规则文件动态加载，无需重启服务

## 🏗️ 系统架构

```
招标廉政体检系统/
├── backend/                 # 后端API服务
│   ├── app.py              # FastAPI主应用
│   ├── config.py           # 配置管理
│   ├── llm_client.py       # LLM客户端
│   ├── utils_doc.py        # 文档处理工具
│   ├── run_rules.py        # 规则引擎
│   ├── post_checks.py      # 后处理检查
│   ├── rules.yaml          # 风险规则定义
│   └── requirements.txt    # 后端依赖
├── frontend/               # 前端Streamlit应用
│   ├── streamlit_app.py    # 主应用界面
│   └── requirements.txt    # 前端依赖
├── .env.example            # 环境变量模板
├── start_system.py         # 系统启动脚本
└── README.md              # 项目文档
```

## 🚀 快速开始

### 环境要求
- Python 3.8+
- 8GB+ 内存推荐
- Windows/Linux/macOS

### 1. 克隆项目
```bash
git clone <repository-url>
cd bid-anti-corruption
```

### 2. 配置环境
```bash
# 复制环境变量模板
cp .env.example .env

# 编辑环境变量（必须配置）
notepad .env  # Windows
# 或
vim .env     # Linux/macOS
```

### 3. 一键启动（推荐）
```bash
# 开发模式启动（自动安装依赖）
python start_system.py --install-deps

# 生产模式启动
python start_system.py --mode prod

# 自定义端口
python start_system.py --backend-port 8080 --frontend-port 8502
```

### 4. 手动启动
```bash
# 安装后端依赖
cd backend
pip install -r requirements.txt

# 启动后端服务
uvicorn app:app --host 0.0.0.0 --port 8000 --reload

# 新终端窗口 - 安装前端依赖
cd frontend
pip install -r requirements.txt

# 启动前端应用
streamlit run streamlit_app.py --server.port 8501
```

### 5. 访问系统
- **前端应用**: http://localhost:8501
- **后端API**: http://localhost:8000
- **API文档**: http://localhost:8000/docs
- **健康检查**: http://localhost:8000/health

## ⚙️ 配置说明

### 环境变量配置

创建 `.env` 文件并配置以下变量：

```bash
# === 应用配置 ===
APP_NAME=招标廉政体检系统
APP_VERSION=2.0.0
DEBUG=true
CORS_ORIGINS=http://localhost:8501,http://127.0.0.1:8501

# === Dify LLM配置 ===
DIFY_APPID=your_dify_app_id
DIFY_TOKEN=your_dify_token
DIFY_URL=https://api.dify.ai/v1
DIFY_TIMEOUT=30
DIFY_MAX_RETRIES=3
DIFY_RETRY_DELAY=1

# === 文件处理配置 ===
MAX_FILE_SIZE=10485760
ALLOWED_EXTENSIONS=.docx
UPLOAD_DIR=./uploads

# === 处理配置 ===
MAX_CONCURRENT_LLM=5
TIMEOUT_SECONDS=300
CHUNK_SIZE=1000
CHUNK_OVERLAP=200

# === 安全配置 ===
SECRET_KEY=your_secret_key_here
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# === 日志配置 ===
LOG_LEVEL=INFO
LOG_FILE=./logs/app.log
LOG_MAX_SIZE=10485760
LOG_BACKUP_COUNT=5

# === 规则配置 ===
RULES_FILE=./rules.yaml
RULES_AUTO_RELOAD=true
RULES_CHECK_INTERVAL=60
```

### 规则配置

编辑 `backend/rules.yaml` 文件来自定义风险检测规则：

```yaml
rules:
  - id: "budget_mismatch"
    name: "预算不匹配"
    pattern: "预算.*?([0-9]+).*?万元"
    level: "high"
    priority: 1
    tags: ["预算", "财务"]
    description: "检测预算相关风险"
    
  - id: "geographic_limit"
    name: "地域限制"
    pattern: "(仅限|只限|限于).*(本地|当地|本市|本省)"
    level: "medium"
    priority: 2
    tags: ["地域", "限制"]
    description: "检测不合理的地域限制"
```

## 📖 使用指南

### 基本使用流程

1. **上传文件**: 选择.docx格式的招标文件
2. **设置参数**: 输入项目预算等基本信息
3. **开始分析**: 点击分析按钮，等待处理完成
4. **查看结果**: 浏览详细的风险分析报告
5. **导出报告**: 下载JSON格式的分析结果

### 高级功能

#### 规则管理
- 在系统管理页面可以重新加载规则文件
- 支持规则的热更新，无需重启服务
- 可以查看规则统计信息

#### 系统监控
- 实时查看系统状态和配置信息
- 监控Dify连接状态
- 查看处理性能指标

#### 历史记录
- 自动保存分析历史
- 支持历史记录的查看和管理
- 可以清空历史数据

## 🔧 开发指南

### 项目结构详解

#### 后端模块

- **app.py**: FastAPI主应用，定义API端点
- **config.py**: 配置管理，环境变量加载和验证
- **llm_client.py**: Dify LLM客户端，处理AI分析请求
- **utils_doc.py**: 文档处理工具，解析和提取文本
- **run_rules.py**: 规则引擎，执行风险检测规则
- **post_checks.py**: 后处理检查，专项风险分析

#### 前端模块

- **streamlit_app.py**: Streamlit主应用，提供Web界面

### API接口文档

#### 主要端点

- `POST /analyze`: 分析招标文件
- `GET /health`: 健康检查
- `GET /stats`: 系统状态
- `POST /reload-rules`: 重新加载规则

#### 请求示例

```python
import requests

# 分析文件
with open('tender.docx', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/analyze',
        files={'file': f},
        data={'budget': 1000000}
    )
    result = response.json()
```

### 扩展开发

#### 添加新的风险检测规则

1. 编辑 `backend/rules.yaml`
2. 添加新的规则定义
3. 通过API重新加载规则

#### 添加新的后处理检查

1. 在 `backend/post_checks.py` 中定义新函数
2. 注册到 `POST_CHECK_FUNCTIONS`
3. 重启服务生效

#### 自定义LLM提供商

1. 修改 `backend/llm_client.py`
2. 实现新的客户端类
3. 更新配置文件

## 🐛 故障排除

### 常见问题

#### 1. 服务启动失败
```bash
# 检查端口占用
netstat -ano | findstr :8000

# 检查Python版本
python --version

# 检查依赖安装
pip list | grep fastapi
```

#### 2. 文件上传失败
- 检查文件格式是否为.docx
- 确认文件大小不超过10MB
- 验证文件是否损坏

#### 3. LLM分析失败
- 检查Dify配置是否正确
- 验证网络连接
- 查看错误日志

#### 4. 规则不生效
- 检查规则文件语法
- 确认规则已重新加载
- 验证正则表达式

### 日志查看

```bash
# 查看应用日志
tail -f logs/app.log

# 查看错误日志
grep ERROR logs/app.log

# 查看特定时间的日志
grep "2024-01-01" logs/app.log
```

## 🔒 安全注意事项

1. **环境变量**: 不要将敏感信息提交到版本控制
2. **文件上传**: 系统已实现文件类型和大小限制
3. **API访问**: 生产环境建议添加认证机制
4. **日志安全**: 避免在日志中记录敏感信息
5. **网络安全**: 使用HTTPS和防火墙保护服务

## 📊 性能优化

### 系统调优

1. **并发设置**: 根据硬件调整 `MAX_CONCURRENT_LLM`
2. **内存管理**: 监控内存使用，适当调整文件大小限制
3. **缓存策略**: 启用规则缓存和结果缓存
4. **数据库**: 生产环境建议使用PostgreSQL或MySQL

### 监控指标

- 请求响应时间
- 文件处理速度
- LLM调用成功率
- 内存和CPU使用率
- 错误率统计

## 🤝 贡献指南

1. Fork 项目
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 📄 许可证

本项目采用 MIT 许可证 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 📞 支持与反馈

如果您在使用过程中遇到问题或有改进建议，请：

1. 查看本文档的故障排除部分
2. 搜索已有的 Issues
3. 创建新的 Issue 描述问题
4. 联系开发团队

---

**🔍 招标廉政体检系统 v2.0.0**  
*基于AI技术，助力廉政建设*
