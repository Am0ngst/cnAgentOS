# cnAgentOS — 智能瞭望与智慧舆情分析系统

基于 **Python Tornado** 的 B/S 架构智能平台，集成 AI 大模型对话、Web 数据采集、AI 深度内容分析、智慧舆情监控、即时通讯（IM）、RBAC 权限管理等能力，支持多数字员工的统一调度与协作。

---

## 技术栈

- **后端框架**: Tornado (Python)
- **数据库**: SQLite
- **AI 大模型**: OpenAI 兼容 API（DeepSeek 等）
- **前端**: Bootstrap 5 + Font Awesome 5 + ECharts + SSE（Server-Sent Events）
- **运行端口**: `10086`

---

## 项目结构

```
cnAgentOS/
├── app.py                          # 主入口，Tornado 应用启动与路由定义
├── data/                           # SQLite 数据库文件目录
│   └── cnagent.db                  # 自动生成的数据库文件
├── app/
│   ├── controllers/                # 控制器层（Handler）
│   │   ├── base.py                 # 公共基础类（认证机制）
│   │   ├── auth.py                 # 前台登录/登出
│   │   ├── home.py                 # 首页
│   │   ├── admin.py                # 后台管理（登录、控制台、用户管理）
│   │   ├── rbac.py                 # RBAC（功能/角色/权限/菜单管理）
│   │   ├── model_engine.py         # AI 模型引擎管理
│   │   ├── watch_engine.py         # 瞭望采集与数据仓库
│   │   ├── deep_crawl.py           # AI 深度内容采集
│   │   ├── api_interface_mgr.py    # 第三方 API 接口管理
│   │   ├── digital_employee_mgr.py # 数字员工管理与 AI 工具配置
│   │   ├── user_chat.py            # 用户侧智能对话
│   │   ├── sentiment.py            # 智慧舆情分析（SSE AI 分析引擎）
│   │   ├── im_controller.py        # IM 智能聊天子系统（用户侧）
│   │   └── admin_im.py             # IM 后台管理（群组/文件/服务器）
│   ├── models/                     # 模型层（数据仓库/Repository）
│   │   ├── db.py                   # 数据库连接与建表（含菜单初始化）
│   │   ├── user.py                 # 用户模型
│   │   ├── rbac.py                 # 功能/角色/权限模型与菜单树构建
│   │   ├── ai_model.py             # AI 模型与 Token 统计模型
│   │   ├── watch_source.py         # 数据源与采集数据模型
│   │   ├── api_interface.py        # API 接口模型
│   │   ├── digital_employee.py     # 数字员工模型
│   │   ├── conversation.py         # 对话历史模型
│   │   ├── sentiment_repository.py # 智慧舆情数据仓库
│   │   └── im_model.py             # IM 聊天子系统数据层
│   ├── templates/                  # 前端 HTML 模板
│   │   ├── admin/                  # 后台模板（20+ 页面）
│   │   └── user/                   # 用户侧模板
│   └── static/                     # 静态资源
│       ├── css/
│       ├── bootstrap-5.3.8-dist/
│       └── fontawesome-free-5.15.4-web/
└── prompts.txt                     # AI 提示词与功能需求设计文档
```

---

## 功能模块

### 1. 用户认证系统

- **前台登录/注册**：用户通过 `/user/login` 登录、`/user/register` 注册
- **密码安全**：PBKDF2-SHA256 加盐哈希存储，100,000 次迭代
- **会话管理**：基于 Tornado Secure Cookie，管理员与普通用户 Cookie 隔离
- **默认管理员**：admin / admin888

### 2. 后台管理面板

- **独立登录页** `/admin/login`
- **控制台**：系统概览仪表盘
- **用户管理**：增删改查、角色分配、搜索与批量删除（admin 用户受保护）

### 3. RBAC 权限管理

- **功能菜单**：多级树状结构，支持图标、URL、排序、启用/禁用
- **角色管理**：系统角色（超级管理员、普通用户、会员）+ 自定义角色
- **权限分配**：树状勾选界面，按角色配置菜单访问权限
- **动态菜单**：根据当前登录用户角色自动渲染侧边栏

### 4. 后台菜单结构

```
📊 控制台
🔒 用户权限 → 用户管理 / 角色管理 / 权限管理
⚙️ 系统配置 → 功能管理 / 接口管理
🤖 AI 引擎 → 模型引擎 / 数字员工（含 AI 工具配置）
🛰️ 数据采集 → 瞭望采集 / 数据仓库
📈 智慧舆情 → 数智大屏 / 智能舆情
💬 智能聊天 → 群管理 / 文件管理 / 服务器管理
```

### 5. AI 模型引擎

- 多模型配置（OpenAI 兼容接口）
- 默认模型设置、对话测试（SSE 流式 / 普通响应）
- Token 按天统计与调用日志
- Thinking 模式支持

### 6. 瞭望采集引擎

- **数据源管理**：多数据源配置、`{keyword}` / `{pn}` 占位符、Cookie 配置
- **关键词采集**：多源并发采集、多页深度采集、智能去重
- **预置**：百度新闻数据源

### 7. 数据仓库与深度采集

- 采集数据分页检索（按关键词/数据源筛选）
- AI 深度内容分析：正文提取 → 摘要/关键词/情感分析/实体提取
- 批量深度采集、状态追踪、统计面板

### 8. 接口管理

- 第三方 API 接口增删改查
- QPS 限制、认证 Token、标签分组
- 预置：网易云音乐、天气查询

### 9. 数字员工与 AI 工具

- **员工管理**：AI 型（关联模型 + 系统提示词）和 API 型（关联接口）
- **@别名调度**：唯一的 `@name` 标识
- **AI 工具配置**：在同一页面内管理可调用工具，支持绑定到数字员工
- **对话页面**：`/admin/digital-chat` 流式智能对话
- **预置员工**：@川小农（文案助手）、@天气、@音乐

### 10. 用户侧智能对话

- 多轮对话创建/切换/删除，SSE 流式输出
- 智能 SQL 生成与数据查询
- 数字员工 @别名 自动调动，上下文感知自动延续

### 11. 智能聊天子系统（IM）

仿微信即时通讯，支持私聊、群聊、文件传输，集成数字员工。

**用户侧**：
- 好友搜索与请求、通讯录管理、删除联系人
- 私聊消息 SSE 实时推送、消息已读、2 分钟内右键撤回
- 群聊创建（多选好友自动命名）、群名称修改、退出/解散群聊
- 数字员工以好友/群成员身份参与对话，@别名 触发 AI/API 调用
- 文件上传下载、图片预览

**后台管理**：
- 群管理：群列表、成员查看、聊天记录浏览（分页）、禁言、解散、系统公告
- 文件管理：统一管理聊天文件、去重、预览、删除
- 服务器管理：多服务器配置、启用/禁用

### 12. 智慧舆情分析

基于 AI 大模型的自动化舆情监控与风险分析。

- **数智大屏**：全屏指挥中心，ECharts 可视化
  - 用户活跃度趋势、全球瞭望数据地球仪
  - 瞭望关键词 TOP10（横向柱状图）
  - 模型调用统计（饼图）
  - 聊天词云：汇聚私聊 + 群聊 + AI 对话的聊天内容词频
  - 近期分析记录
- **智能舆情分析中心**：
  - 综合舆情分析：全面扫描系统数据，评估整体态势
  - 对话风险检测：深度分析私聊 + 群聊 + AI 对话记录，识别异常言论
  - 瞭望趋势洞察：追踪采集关键词走势，发现热点话题
  - 风险预警评估
  - SSE 流式 AI 分析结果实时输出
  - 历史分析记录查看与删除

---

## 快速开始

### 环境要求

- Python 3.8+
- pip

### 安装与运行

```bash
# 1. 创建虚拟环境
python -m venv venv

# 2. 激活虚拟环境
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# 3. 安装依赖
pip install -r requirements.txt

# 4. 启动服务
python app.py
```

启动后访问：
| 入口 | 地址 | 默认账号 |
|------|------|----------|
| 后台管理 | http://localhost:10086/admin/login | admin / admin888 |
| 用户端 | http://localhost:10086/user/login | 自行注册 |
| 智能聊天 | http://localhost:10086/user/im | 登录后访问 |

---

## 数据库表结构

| 表名 | 说明 |
|------|------|
| users | 用户表（PBKDF2 密码哈希） |
| functions | 功能菜单表（多级树状） |
| roles | 角色表 |
| permissions | 权限表（角色-功能映射） |
| ai_models | AI 模型配置表 |
| token_logs | Token 消耗日志 |
| watch_sources | 瞭望数据源 |
| watch_data | 采集数据 |
| watch_data_detail | AI 深度分析详情 |
| deep_crawl_log | 深度采集日志 |
| api_interfaces | 第三方 API 接口 |
| digital_employees | 数字员工 |
| ai_tools | AI 工具配置 |
| conversation_history | 对话会话 |
| conversation_messages | 对话消息 |
| sentiment_analysis | 智慧舆情分析记录 |
| im_contacts | IM 好友关系 |
| im_friend_requests | IM 好友请求 |
| im_groups | IM 群组 |
| im_group_members | IM 群成员 |
| im_messages | IM 私聊消息 |
| im_group_messages | IM 群聊消息 |
| im_chat_servers | IM 聊天服务器配置 |
| im_group_announcements | IM 群公告 |
| im_group_bans | IM 群管控记录 |
