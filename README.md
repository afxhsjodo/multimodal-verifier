# 多模态信息核验系统（Multimodal Verifier）

> 基于 **多智能体（Multi-Agent）协作 + 检索增强生成（RAG）** 的多模态信息核验系统。
> 输入一条含文本 / 截图 / 图文混合的争议信息，系统输出 **支持 / 反驳 / 证据不足** 三类结论，并给出可追溯证据链、来源可靠性提示、冲突证据说明与人工复核入口。

本科毕业设计项目。系统不以「自动判定一切」为目标，而是**明确提示模型可能出错**，对证据不足的内容**强制保留人工复核**。

---

## 目录

- [核心特性](#核心特性)
- [系统架构](#系统架构)
- [技术栈](#技术栈)
- [目录结构](#目录结构)
- [快速开始](#快速开始)
- [服务器部署](#服务器部署)
- [使用说明](#使用说明)
- [API 说明](#api-说明)
- [配置说明](#配置说明)
- [工具脚本与测试](#工具脚本与测试)
- [当前进度与待办](#当前进度与待办)
- [免责声明](#免责声明)

---

## 核心特性

- **5 个角色 Agent 协作**：主张拆解 → 检索规划 → 证据获取 → 可信度评估 → 结论生成，由 LangGraph 做状态管理与流程编排。
- **三类结论，不强行下判断**：`支持 / 反驳 / 证据不足`；证据不足一律标记人工复核。
- **可追溯证据链**：每条结论都引用具体证据 ID，证据带来源链接、来源类型与可信度评分 → 保证「引用与结论一致」。
- **来源可靠性提示**：按权威性 / 时效性 / 相关性 / 一致性四维打分，标注权威来源与低可信来源。
- **冲突证据说明**：同一主张下证据出现正反矛盾时，自动识别并标注「存在冲突」。
- **多模态输入**：支持纯文本、网页截图、图文混合；图片经视觉大模型（Qwen-VL）转写与理解。
- **三类工具接入**：网页检索（Tavily / DuckDuckGo）+ 文档库向量检索（Chroma）+ 图像理解（OCR / 视觉）。
- **Agent 执行过程可视化**：WebSocket 实时推送每个 Agent 的步骤、动作与耗时。
- **人工复核入口**：每条结论卡片可提交人工判定与备注，反馈落库。
- **可离线运行**：无 API Key 时自动进入 mock 模式，全流程不崩，便于开发调试与将来做消融实验。

---

## 系统架构

```
输入（文本 / 截图 / 图文混合）
   │
   ▼
┌─────────────────┐
│ ① 主张拆解 Agent │  拆成可独立核验的原子主张（含是否依赖图片）
└─────────────────┘
   │
   ▼
┌─────────────────┐
│ ② 检索规划 Agent │  为每个主张生成查询词、目标检索源、预期证据类型
└─────────────────┘
   │
   ▼
┌─────────────────┐  工具：网页搜索(Tavily/DDG) + 网页正文(trafilatura)
│ ③ 证据获取 Agent │       文档库检索(Chroma+embedding) + 图像理解(Qwen-VL)
└─────────────────┘  产出：带来源/链接/类型的证据列表（并发检索）
   │
   ▼
┌───────────────────┐  规则 + LLM 融合：权威性/时效/相关/一致性四维打分，
│ ④ 可信度评估 Agent │  并检测证据间冲突
└───────────────────┘
   │
   ▼
┌─────────────────┐  逐主张判定「支持/反驳/证据不足」，给出置信度与证据引用，
│ ⑤ 结论生成 Agent │  证据不足自动标记人工复核
└─────────────────┘
   │
   ▼
输出：结论 + 证据链 + 来源可靠性 + 冲突说明 + 免责声明 + 人工复核入口
```

每一步都会向 `state["trace"]` 追加步骤日志，通过 WebSocket 实时推送给前端展示。

---

## 技术栈

| 层次 | 选型 | 说明 |
|---|---|---|
| Agent 编排 | **LangGraph**（StateGraph） | 有状态工作流、可扩展条件边/并行 |
| 文本 LLM | **DeepSeek** `deepseek-chat` / `deepseek-reasoner` | OpenAI 兼容；中文强、成本低；推理模型用于结论生成 |
| 视觉理解 | **Qwen-VL** `qwen-vl-max`（阿里 DashScope） | 截图 / 图片内容识别与文字转写 |
| 文本向量化 | **DashScope** `text-embedding-v3` | 文档库语义检索（1024 维） |
| 向量库 | **Chroma**（本地持久化） | 免费、Python 原生、易替换为 FAISS |
| 网页检索 | **Tavily**（主）/ **DuckDuckGo**（兜底） | 面向 LLM 的干净检索结果 |
| 网页正文 | **trafilatura** | 正文抽取，失败回退 BeautifulSoup |
| 后端 | **FastAPI** + **WebSocket** | 同步接口 + 流式推送 Agent 过程 |
| 前端 | **Vue 3** + **Vite** + **Element Plus** | 中文界面 |
| 持久化 | **SQLite** | 保存核验记录与人工复核反馈 |
| 公网部署 | **腾讯云 Ubuntu + nginx + systemd** | 公网 IP 直接访问；后端 systemd 托管、nginx 反向代理 |

---

## 目录结构

```
multimodal-verifier/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI 入口：注册路由、CORS、静态托管前端
│   │   ├── core/
│   │   │   ├── config.py           # 配置（API Key / 模型名 / provider / 路径）
│   │   │   ├── models.py           # Pydantic 数据模型（Claim/Evidence/Verdict…）
│   │   │   └── llm.py              # 统一 LLM 客户端（DeepSeek + Qwen-VL + embedding + mock）
│   │   ├── agents/
│   │   │   ├── state.py            # LangGraph 共享状态
│   │   │   ├── graph.py            # LangGraph 图编排（5 节点）
│   │   │   ├── common.py           # 步骤日志 / ID 工具
│   │   │   ├── decompose.py        # ① 主张拆解
│   │   │   ├── plan.py             # ② 检索规划
│   │   │   ├── retrieve.py         # ③ 证据获取（并发）
│   │   │   ├── assess.py           # ④ 可信度评估
│   │   │   └── conclude.py         # ⑤ 结论生成
│   │   ├── tools/
│   │   │   ├── web_search.py       # 网页检索（Tavily / DuckDuckGo）
│   │   │   ├── web_scrape.py       # 网页正文提取（trafilatura）
│   │   │   ├── doc_retrieval.py    # 文档库检索（Chroma + embedding）
│   │   │   ├── vector_store.py     # Chroma 封装（线程安全初始化）
│   │   │   └── ocr_vision.py       # 图像理解（Qwen-VL）
│   │   ├── api/
│   │   │   ├── verify.py           # POST /verify + WS /ws/verify
│   │   │   └── feedback.py         # 人工复核反馈 / 历史记录
│   │   └── db/
│   │       └── database.py         # SQLite 持久化
│   ├── scripts/
│   │   ├── build_index.py          # 构建文档库向量索引
│   │   ├── check_apis.py           # 四类 API 连通性自检
│   │   ├── smoke_test.py           # 端到端管道冒烟测试
│   │   └── test_vision.py          # 视觉链路 / OCR 自检
│   ├── tests/
│   │   └── test_api.py             # 后端接口测试（health / verify / WS / feedback）
│   ├── data/
│   │   ├── corpus/                 # 文档库语料（.txt / .md）
│   │   ├── chroma/                 # Chroma 持久化（运行时生成）
│   │   ├── uploads/                # 上传图片临时目录（运行时生成）
│   │   └── verifier.db             # SQLite（运行时生成）
│   ├── requirements.txt
│   ├── .env.example                # 配置模板
│   └── .env                        # 本地实际配置（含 Key，勿提交）
├── frontend/
│   ├── src/
│   │   ├── main.js
│   │   ├── App.vue
│   │   ├── api/client.js           # 后端客户端（WS 流式 + 反馈 + 健康检查）
│   │   ├── views/Verify.vue        # 主页面
│   │   └── components/
│   │       ├── AgentFlow.vue       # Agent 执行过程时间线
│   │       ├── VerdictCard.vue     # 结论卡片 + 人工复核
│   │       └── EvidenceList.vue    # 证据列表
│   ├── dist/                       # 构建产物（后端直接托管）
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── start.bat                       # 一键启动（本机 / 局域网）
└── README.md
```

---

## 快速开始

### 环境要求

- Python **3.10+**（开发环境为 3.12）
- Node.js **18+**（仅构建前端时需要；运行时不依赖，前端已由后端托管）

> 已有现成部署：**http://134.175.40.72/** ，无需自行部署即可使用（详见 [服务器部署](#服务器部署)）。

### 1. 配置 API Key

复制 `.env.example` 为 `.env`，填入密钥：

| 变量 | 必填 | 用途 |
|---|---|---|
| `DEEPSEEK_API_KEY` | 是 | 文本 / 推理（不填则进入 mock 模式） |
| `DASHSCOPE_API_KEY` | 是 | Qwen-VL 视觉 + text-embedding-v3 |
| `TAVILY_API_KEY` | 否 | 网页检索；不填则回退 DuckDuckGo |

```env
DEEPSEEK_API_KEY=sk-xxxxxxxx
DASHSCOPE_API_KEY=sk-xxxxxxxx
TAVILY_API_KEY=tvly-xxxxxxxx
```

> 全部留空也能运行（mock 模式），用于开发调试。

### 2. 安装后端依赖

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

### 3. 构建前端（生成 `frontend/dist`，由后端托管）

```powershell
cd frontend
npm install
npm run build
```

### 4. 启动

**方式 A — 本机 / 局域网**（双击 `start.bat`，或手动）：

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

浏览器打开 `http://localhost:8000`（局域网内他人可用 `http://本机IP:8000`）。

**方式 B — 部署到服务器**：

已有现成部署，公网访问 **http://134.175.40.72/** 。如需自行部署或了解结构，见 [服务器部署](#服务器部署)。

### 5. （可选）构建文档库索引

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\build_index.py
```

---

## 服务器部署

系统已部署在一台腾讯云 Ubuntu 24.04 服务器上，公网访问：**http://134.175.40.72/**

```
用户浏览器 ── http://134.175.40.72/ ──► nginx :80 ──► uvicorn 127.0.0.1:8000（systemd: verifier）
```

| 组件 | 说明 |
|---|---|
| 代码 | 从 GitHub 克隆到 `/home/ubuntu/multimodal-verifier` |
| 后端 | Python venv + systemd 服务 `verifier`（开机自启、崩溃自动重启） |
| nginx | 反向代理 `80 → 127.0.0.1:8000`，已配置 WebSocket 升级与 300s 长超时 |
| 前端 | 本地 `npm run build` 后将 `dist` 上传，由后端静态托管 |
| 向量索引 | 服务器上执行 `scripts/build_index.py` 构建 |
| 密钥 | `backend/.env` 单独上传，未入库 |

**更新流程**（在服务器上）：

```bash
cd ~/multimodal-verifier
git pull
# 若前端有改动：本地 npm run build 后把 frontend/dist 上传到服务器
sudo systemctl restart verifier
```

---

## 使用说明

### 在线访问（推荐）

系统已部署到服务器，**无需任何安装，直接用浏览器打开即可使用**：

> **访问地址：http://134.175.40.72/**

打开后，页面右上角会显示当前模式：`Live · 已接入真实模型` 或 `Mock · 离线演示模式`。

### 本地运行

若想在本机运行（开发 / 调试），见上文 [快速开始](#快速开始)：双击 `start.bat`，或手动启动 uvicorn 后访问 `http://localhost:8000`。

### 操作步骤

1. 在输入区**粘贴一条有争议的文本**，或**上传一张截图 / 图片**（可图文混合）。
2. 点击「**开始核验**」，观察 **Agent 执行过程**时间线实时滚动。
3. 查看结果：
   - **核验结论**：每条主张一个卡片，标注 支持 / 反驳 / 证据不足，附置信度与推理说明；
   - **证据与来源**：每条证据显示来源、类型、可信度评分、冲突标记与来源链接；
   - **结论中的证据依据**：结论引用了哪些证据、各自可信度。
4. 对需要复核的结论，在卡片底部选择你的判定并提交「**人工复核**」。

> 单次核验耗时约 10–20 秒（含网页检索与推理），属正常。

---

## API 说明

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/health` | 健康检查，返回是否处于 mock 模式、各 Key 是否就绪 |
| `POST` | `/verify` | 同步核验。`multipart/form-data`：`text`（文本）+ `images`（可多张图片文件），返回完整 `VerifyResult` |
| `WS` | `/ws/verify` | 流式核验。发送 `{text, images:[{name,data(base64)}]}`，逐节点推送 `step`，最后推送 `result` |
| `POST` | `/feedback` | 提交人工复核反馈（`task_id` / `claim_id` / `user_verdict` / `comment`） |
| `GET` | `/feedback` | 查询反馈（可选 `?task_id=`） |
| `GET` | `/history/{task_id}` | 查询某次核验的历史记录 |
| `GET` | `/` | 前端页面（若存在 `frontend/dist`） |

**`VerifyResult` 主要字段**：`task_id`、`extracted_text`、`claims[]`、`evidences[]`、`assessments[]`、`verdicts[]`、`trace[]`、`disclaimer`、`mode`。

---

## 配置说明

`backend/.env`（模板见 `.env.example`）：

| 变量 | 默认 | 说明 |
|---|---|---|
| `DEEPSEEK_API_KEY` | 空 | DeepSeek 密钥（空 → mock 模式） |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | DeepSeek 接口地址 |
| `DEEPSEEK_CHAT_MODEL` | `deepseek-chat` | 文本模型（拆解 / 规划 / 评估） |
| `DEEPSEEK_REASONER_MODEL` | `deepseek-reasoner` | 推理模型（结论生成） |
| `DASHSCOPE_API_KEY` | 空 | 阿里 DashScope 密钥（视觉 + 向量） |
| `DASHSCOPE_BASE_URL` | `.../compatible-mode/v1` | DashScope OpenAI 兼容地址 |
| `QWEN_VL_MODEL` | `qwen-vl-max` | 视觉理解模型 |
| `QWEN_EMBED_MODEL` | `text-embedding-v3` | 文本向量化模型 |
| `TAVILY_API_KEY` | 空 | Tavily 密钥（空则退回 DuckDuckGo） |
| `WEB_SEARCH_PROVIDER` | `tavily` | 检索源：`tavily` / `duckduckgo` / `both` |
| `CHROMA_DIR` | `./data/chroma` | 向量库目录 |
| `CORPUS_DIR` | `./data/corpus` | 文档库语料目录 |
| `CHROMA_COLLECTION` | `evidence_corpus` | Chroma collection 名 |
| `LOG_LEVEL` | `INFO` | 日志级别 |

**运行模式**：当 `DEEPSEEK_API_KEY` 为空时，系统整体进入 **mock 模式**（LLM 走确定性降级逻辑，便于无 Key 开发与实验）。

---

## 工具脚本与测试

均在 `backend/` 目录下用虚拟环境运行：

```powershell
.\.venv\Scripts\python.exe scripts\build_index.py   # 构建文档库向量索引
.\.venv\Scripts\python.exe scripts\check_apis.py    # 四类 API 连通性自检
.\.venv\Scripts\python.exe scripts\smoke_test.py    # 端到端管道冒烟测试
.\.venv\Scripts\python.exe scripts\test_vision.py   # 视觉 / OCR 链路自检
.\.venv\Scripts\python.exe tests\test_api.py        # 后端接口测试
```

---

## 当前进度与待办

### ✅ 已完成（Phase A — 可运行 MVP）

- [x] 5 个角色的 Agent 设计 + LangGraph 编排
- [x] 接入三类工具：网页检索、文档库检索、OCR / 图像理解
- [x] DeepSeek（文本 / 推理）+ Qwen-VL（视觉）+ DashScope（embedding）统一客户端，支持 mock
- [x] FastAPI 后端：`/verify`（同步）、`/ws/verify`（流式）、`/feedback`（人工复核）、`/health`
- [x] Vue3 前端：输入（文本 + 图片）→ Agent 过程 → 结论卡片 → 证据列表 → 免责声明 → 人工复核
- [x] 三类结论 + 证据链 + 来源可靠性 + 冲突说明 + 免责声明 + 人工复核标记
- [x] 并发检索优化（单次核验约 13–16 秒）
- [x] 部署到腾讯云服务器（nginx + systemd，公网 IP 直接访问 http://134.175.40.72/）
- [x] 冒烟测试 / 接口测试 / 视觉自检脚本

### ⏳ 待办（Phase B — 完整系统，题目第 (5) 条要求）

- [ ] **构建 ≥200 条测试样本**（校园通知 / 科技新闻 / 健康科普，含人工标注真值）
- [ ] **基线对比**：单 LLM 直接问答（无 RAG、无多 Agent）vs 本系统
- [ ] **消融实验**：去除多 Agent 协作 / 来源过滤 / 证据重排序，分析各自影响
- [ ] 评测指标：结论准确率、证据相关性、引用与结论一致性、检索完整度
- [ ] 待实现脚本：`scripts/make_testset.py`（测试集生成）、`scripts/run_experiments.py`（实验对比）— **当前尚未创建**
- [ ] 撰写论文 / 报告对应章节

---

## 免责声明

本系统输出由 AI 自动生成，**仅供参考，不构成权威结论**。模型可能出错，且可能检索到不完整或相互矛盾的信息。

对标注为「**证据不足**」或重要的事实，请务必通过**人工复核**并使用可靠的权威来源进行确认。系统在页面显著位置与每条结论中都保留该免责提示，并对证据不足的内容强制保留人工复核入口。
