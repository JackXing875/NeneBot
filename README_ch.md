<div align="center">


# NeneBot: A RAG-Powered Ayachi Nene AI Companion

 <div>&nbsp;</div>

<img src="assets/nene.gif" width="300" alt="Ayachi Nene">

 <div>&nbsp;</div>

<p align="center">
  <b>基于检索增强生成 (RAG) 架构的绫地宁宁 AI 对话服务</b><br>
  <i>"メンカタカラメヤサイダブルニンニクアブラマシマシ！"</i>
</p>

 <div>&nbsp;</div>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10%2B-3776AB.svg?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Node.js-20%2B-339933.svg?style=flat-square&logo=node.js&logoColor=white" alt="Node.js">
  <img src="https://img.shields.io/badge/FastAPI-0.110%2B-009688.svg?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/Vue.js-3.x-4FC08D.svg?style=flat-square&logo=vuedotjs&logoColor=white" alt="Vue">
  <img src="https://img.shields.io/badge/Vite-5.x-646CFF.svg?style=flat-square&logo=vite&logoColor=white" alt="Vite">
  <img src="https://img.shields.io/badge/Tailwind_CSS-4.x-38B2AC.svg?style=flat-square&logo=tailwind-css&logoColor=white" alt="Tailwind">
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Ollama-Local_LLM-black.svg?style=flat-square&logo=ollama&logoColor=white" alt="Ollama">
  <img src="https://img.shields.io/badge/Claude-API-D97706.svg?style=flat-square&logo=anthropic&logoColor=white" alt="Claude">
  <img src="https://img.shields.io/badge/DeepSeek-API-4F46E5.svg?style=flat-square" alt="DeepSeek">
  <img src="https://img.shields.io/badge/FAISS-Vector_DB-1877F2.svg?style=flat-square&logo=meta&logoColor=white" alt="FAISS">

</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-GPLv3-green.svg?style=flat-square" alt="License"></a>
</p>

<div>&nbsp;</div>

> RAG 对话型 AI，结合 FAISS 语义检索与可插拔 LLM 后端（Claude、DeepSeek 或本地 Ollama）。支持多轮会话记忆、SSE 流式输出、沉浸式 Vue 3 视觉界面与余弦相似度阈值熔断，在消除"幻觉"与"OOC"方面表现出色。

<div>&nbsp;</div>

[**项目愿景**](#项目愿景) | [**核心特性**](#核心特性) | [**快速开始**](#快速开始) | [**项目架构**](#项目架构) | [**常见问题**](#常见问题)

</div>

---

## 项目愿景 



传统的二次元角色 AI 往往面临两个致命痛点：**“幻觉”**（乱编设定）和 **“OOC”**（Out Of Character，语气崩坏）。常规的微调不仅耗费显卡，而且难以彻底根除这些问题。

专注于以 RAG 技术重现 Galgame 角色：
* **外挂记忆引擎**：将《魔女的夜宴》原版剧本切片并向量化，让 AI 拥有"真物"般的记忆。
* **原汁原味还原**：模型被强制要求参考检索到的原版台词进行输出，100% 还原宁宁温柔、害羞的性格特点。
* **可插拔 LLM 后端**：一行环境变量在本地 Ollama 与云端 API（Claude、DeepSeek）之间自由切换。
* **极致还原游戏**：告别简陋的控制台，打造沉浸式的现代 Galgame 视觉交互界面。

---

## 核心特性

* **灵活的 LLM 后端**：本地 Ollama 保护隐私，云端 Claude / DeepSeek 提供更高质量，`LLM_PROVIDER` 一行切换，无需改代码。
* **多轮对话记忆**：滑动窗口式会话历史，宁宁能记住上下文，不再"失忆"。
* **流式实时输出**：SSE 逐 token 推送，原生打字机体验。
* **毫秒级语义检索**：使用 Meta 开源的 FAISS 向量数据库，配合 `bge-small-zh` 模型，精准定位历史剧本。
* **阈值熔断机制**：`match_threshold` 余弦相似度过滤（默认 `0.55`），宁宁遇到不懂的话题会自由发挥，绝不”驴头不对马嘴”。
* **沉浸式视觉体验**：Vue 3 + Vite 驱动的深色磨砂玻璃 UI，支持打字机特效与动态呼吸感布局。
* **全自动开箱即用**：提供 Windows/Linux 双平台一键环境装载与启动脚本，无需任何终端知识。

---

## 快速开始

请根据你的操作系统选择相应的步骤：

在本地运行之前，请先决定你要使用哪一种 **LLM 后端**：

* **本地 Ollama**：零 API 成本、完全本地化，适合离线或隐私优先场景。
* **云端 API（Claude / DeepSeek / OpenAI-Compatible）**：回答质量通常更高，也更适合低配机器。

首次运行前，建议先创建 `.env`：

```bash
cp .env.example .env
```

然后只填写你所选后端对应的配置：

```env
# 方案一：本地 Ollama
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://127.0.0.1:11434
LLM_MODEL_NAME=qwen2.5

# 方案二：DeepSeek
# LLM_PROVIDER=deepseek
# OPENAI_COMPAT_API_KEY=sk-...
# OPENAI_COMPAT_BASE_URL=https://api.deepseek.com
# OPENAI_COMPAT_MODEL=deepseek-chat

# 方案三：Claude
# LLM_PROVIDER=claude
# ANTHROPIC_API_KEY=sk-ant-...
# CLAUDE_MODEL_NAME=claude-haiku-4-5-20251001
```

> **补充说明：** 仓库中已经包含 `data/raw/train.jsonl` 以及预构建好的 `vector_store/`。在全新环境中，如果索引缺失，`scripts/setup.sh` 也会自动重新构建。

### Windows 用户

**第一步：安装两大基础软件（如果你的电脑已有，可跳过）**
1. 下载并安装 [Python 3.10+](https://www.python.org/downloads/)。**【极其重要】**：安装界面底部一定要勾选 <kbd>Add Python to PATH</kbd>！
2. 下载并安装 [Node.js (LTS版本)](https://nodejs.org/)，一路点击下一步即可。
3. *（仅使用本地 Ollama 时需要）* 下载并安装 [Ollama Windows版](https://ollama.com/download/windows)。

**第二步：下载 NeneBot 源码**
在 GitHub 页面点击绿色的 `Code` 按钮，选择 `Download ZIP`。解压到你的电脑中（建议路径全英文，如 `D:\NeneBot`）。

**第二点五步：配置模型来源**
将 `.env.example` 复制为 `.env`。如果你使用云端 API，请先把对应 Key 填好再启动。

**第三步：双击运行！**
进入解压后的文件夹，找到并**双击运行 `start_windows.bat`**。
* 喝口水，脚本会自动为你下载依赖、唤醒 AI 引擎并打开浏览器。
* 当你看对话界面弹出时，宁宁就已经在等你了！

---

### Linux 用户

打开你的终端，依次执行以下三段优雅的指令：

```bash
# 1. 克隆代码库并进入目录
git clone https://github.com/your-username/NeneBot.git
cd NeneBot

# 2. 创建本地环境变量文件
cp .env.example .env

# 3. 赋予脚本执行权限
chmod +x scripts/setup.sh scripts/run.sh

# 4. 执行全自动装配 (仅首次需要)
./scripts/setup.sh

# 5. 运行
./scripts/run.sh
```

> **Tip:** 服务启动后，浏览器访问 `http://localhost:5173` 即可进入交互界面。后端 API 文档位于 `http://localhost:8000/docs`。
>
> **重要：** 不要直接双击打开 `frontend/index.html`。这个项目不是纯静态网页，聊天功能依赖 FastAPI 后端的 `/v1/*` 接口；应通过 `5173` 开发服务器访问，或先构建前端后由 FastAPI 统一托管。

### 单端口本地运行（更接近生产部署）

如果你希望只通过 **一个地址** 访问完整页面，而不是分别启动前端开发服务器：

```bash
# 1. 后端环境
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 2. 构建前端
cd frontend
npm install
npm run build
cd ..

# 3. 由 FastAPI 同时提供 API 和前端页面
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000
```

然后访问：

* `http://localhost:8000` → 完整应用
* `http://localhost:8000/admin` → 只读后台控制台
* `http://localhost:8000/docs` → API 文档

### Docker Compose 本地部署（app + Redis）

如果你希望在本地以更接近生产环境的方式运行，并启用持久化会话存储：

```bash
cp .env.example .env
docker compose -f deploy/docker_compose.yml up --build
```

该方案会启动：

* `app`：`http://localhost:8000`
* `redis`：`localhost:6379`

建议在 `.env` 中设置：

```env
SESSION_BACKEND=redis
REDIS_URL=redis://redis:6379/0
```

运维排查入口：

* `GET /health`：查看服务、向量索引、前端模式、会话后端状态
* `GET /health/live` / `GET /health/ready`：分别用于存活探针与就绪探针
* `GET /metrics`：导出 Prometheus 风格指标文本
* 响应头 `X-Request-ID`：用于把客户端报错与服务端日志串起来

可选的 API 保护配置：

```env
API_AUTH_ENABLED=true
API_AUTH_TOKENS=frontend|chat:dev-chat-token,ops|ops:dev-ops-token
API_AUTH_REGISTRY_PATH=./config/api_tokens.json
```

开启后，请求需要带上以下任一请求头：

* `Authorization: Bearer <token>`
* `X-API-Key: <token>`

Scope 规则：

* `/v1/*` 需要 `chat`
* `/health*` 与 `/metrics` 需要 `ops`
* 没显式声明 scope 的旧 token 仍默认拥有 `chat` + `ops`，以保证兼容

如果不想把 token 直接写进 `.env`，也可以使用本地 registry 文件：

```json
[
  { "name": "frontend", "token": "replace-with-chat-token", "scopes": ["chat"] },
  { "name": "ops-dashboard", "token": "replace-with-ops-token", "scopes": ["ops"] }
]
```

完整格式可参考 [config/api_tokens.json.example](/home/schrieffer/NeneBot/config/api_tokens.json.example)。

同时服务日志会输出结构化审计字段，例如 `action`、`endpoint`、`session_id`、`auth_subject`、`auth_scopes`、`request_id`，便于排查调用链路。

可选 tracing 配置：

```env
TRACING_ENABLED=true
TRACING_SERVICE_NAME=nenebot
TRACING_EXPORTER=console
```

当前会产出的 span：

* `http.request`
* `rag.retrieve`
* `llm.request`

如何在本地验证 tracing 是否成功：

1. 先安装最新依赖：
   ```bash
   pip install -r requirements.txt
   ```
2. 在 `.env` 里开启 tracing：
   ```env
   TRACING_ENABLED=true
   TRACING_EXPORTER=console
   ```
3. 启动 API 服务后，实际发送一次聊天请求。
4. 观察服务端终端输出，应该能看到 span 名称，例如：
   * `http.request`
   * `rag.retrieve`
   * `llm.request`
5. 再确认 span 属性里带有这些字段：
   * `request_id`
   * `http_path`
   * `provider_name`
   * `rag.retrieved_count`
   * 如果启用了 token，还应看到 `auth.subject`

如果接口本身能正常响应，同时终端里出现这些 span 输出，就说明 tracing 接线已经成功。

只读后台 MVP：

* `GET /admin/api/overview`：查看运行状态、健康信息、LLM、检索、鉴权、集成配置摘要
* `GET /admin/api/metrics/summary`：查看 Prometheus 指标预览
* `GET /admin/api/knowledge/overview`：查看数据集摘要和向量索引摘要
* `POST /admin/api/knowledge/import`：导入 JSONL 数据集内容
* `POST /admin/api/knowledge/rebuild`：基于当前数据集重建向量索引
* `http://localhost:8000/admin`：浏览器后台控制台

如何验证后台控制台是否正常：

1. 先在 `.env` 或 `config/api_tokens.json` 中配置一个带 `ops` scope 的 token。
2. 构建前端并启动应用。
3. 打开 `http://localhost:8000/admin`。
4. 页面提示时输入这个 `ops` token。
5. 确认页面能显示：
   * 服务名 / 环境 / 版本
   * health 状态
   * LLM provider / model
   * 已配置的鉴权身份
   * metrics 预览内容

如果页面能正常加载，且这些卡片都填充出来，就说明后台 MVP 已经接通。

知识库操作：

* 后台现在已经有一个知识库面板，支持：
  * 查看数据集预览
  * 先做 JSONL 预校验
  * 导入 JSONL 内容
  * 重建向量索引
* 导入内容必须是 JSONL，每行一个 JSON 对象，并且包含 `messages` 列表。

如何验证知识库导入和重建是否成功：

1. 用一个带 `ops` scope 的 token 打开 `http://localhost:8000/admin`。
2. 在知识库输入框里粘贴一行合法 JSONL，例如：
   ```json
   {"messages":[{"role":"system","content":"You are Nene."},{"role":"user","content":"你好"},{"role":"assistant","content":"你好呀，保科君。"}]}
   ```
3. 先点击 `VALIDATE`，确认 dry-run 校验通过。
4. 再点击 `IMPORT + REBUILD`。
5. 确认页面发生变化：
   * dataset line count 更新
   * preview 出现刚导入的 user / assistant 内容
   * vector store 摘要刷新
6. 再发送一次正常聊天请求，确认服务仍能正常回答。

如果数据集摘要刷新成功，且索引重建没有报错，就说明这条知识库运维链路已经接通。

发布前请对照 [RELEASE_CHECKLIST.md](/home/schrieffer/NeneBot/RELEASE_CHECKLIST.md) 做一次完整检查。

### Telegram Bot 接入（长轮询）

如果你想先接入一个最简单的 IM 平台，推荐先用 Telegram 官方 Bot API。

1. 通过 `@BotFather` 创建机器人
2. 将 token 写入 `.env`
3. 启动长轮询适配器：

```bash
cp .env.example .env

# 至少填写：
# TELEGRAM_BOT_TOKEN=123456:ABC...
# LLM_PROVIDER=deepseek   # 或 ollama / claude / openai

python -m src.adapters.telegram
```

说明：

* Telegram 聊天会映射到内部会话 id，例如 `telegram:<chat_id>`
* 内置命令：`/start`、`/help`、`/reset`、`/model`
* 发送 `/reset` 可以清空该聊天窗口的记忆
* 默认采用长轮询方式接入，因此暂时 **不需要** 公网 webhook 地址

如果后续要切换到 webhook 模式，可在 `.env` 中配置：

```env
TELEGRAM_MODE=webhook
TELEGRAM_PUBLIC_BASE_URL=https://your-domain.com
TELEGRAM_WEBHOOK_PATH=/integrations/telegram/webhook
TELEGRAM_WEBHOOK_SECRET=your-secret
```

然后启动正常的 API 服务即可。Telegram 会把更新推送到：

* `POST /integrations/telegram/webhook`

如果设置了 `TELEGRAM_WEBHOOK_SECRET`，服务端会校验
`X-Telegram-Bot-Api-Secret-Token` 请求头。

---

## 项目架构 

本项目的目录结构遵循严格的微服务与前后端解耦规范：

```text
NeneBot/
├── 📂 data/             # 原始剧本语料库 (用于向量化)
├── 📂 vector_store/     # FAISS 持久化向量索引
├── 📂 frontend/         # Vue 3 + Vite + Tailwind 沉浸式前端界面
├── 📂 src/              # FastAPI 核心后端服务
│   ├── api/             # 路由控制与 Pydantic 数据校验
│   ├── core/            # pydantic-settings 配置中心与全局异常处理
│   ├── infrastructure/  # 基础设施适配层 (FAISS, Ollama, Claude, DeepSeek)
│   └── services/        # 核心业务逻辑 (RAG 管线, Embedding, 会话记忆)
├── 📂 scripts/          # 自动化运维工具箱 (装载、启动、Linter检查)
├── 📄 railway.toml      # Railway 一键部署配置
├── 📄 .env.example      # 环境变量模板
├── 📄 pyproject.toml    # Ruff & Mypy 工业级代码规范配置
└── 📄 requirements.txt  # Python 依赖清单
```

---

## 高级配置 

对于有开发能力的玩家，你可以通过修改以下文件来“调教”属于你的宁宁：

* **切换 LLM**：在 `.env` 中设置 `LLM_PROVIDER=claude / deepseek / ollama / openai`，并填入对应的 API Key，详见 `.env.example`。
* **修改严格程度**：调整 `MATCH_THRESHOLD`（默认 `0.55`），值越小回答越贴合剧本，值越大越自由发挥。
* **修改立绘与背景**：替换 `frontend/public/` 目录下的 `nene_sprite.png` 和 `bg_room.png`，无需重启即可生效（Vite 热更新支持）。
* **修改角色设定**：编辑 `src/services/rag_pipeline.py` 中的 `_CHARACTER_CARD` 常量，增加新的性格设定指令。
* **重建记忆库**：如果你替换了 `data/raw/train.jsonl`，请运行 `python scripts/init_vector_db.py` 重新生成 `vector_store/`。
* **持久化会话**：设置 `SESSION_BACKEND=redis` 并配置 `REDIS_URL`，即可在重启后保留聊天记忆。
* **运维排障**：通过 `/health` 查看组件状态，通过 `X-Request-ID` 关联客户端请求与服务端日志。
* **Telegram 适配器**：设置 `TELEGRAM_BOT_TOKEN` 后运行 `python -m src.adapters.telegram`，即可通过长轮询方式接入 Telegram。

---

## 常见问题 

<details>
<summary><b>1. 启动时提示 "Python / Node 不是内部或外部命令" 怎么办？</b></summary>


这是因为你没有安装 Python/Node.js，或者安装时忘记配置环境变量。请卸载后重新安装，并在安装界面务必勾选“Add to PATH”选项。
</details>

<details>
<summary><b>2. 出现"宁宁的思绪断开了"错误提示？</b></summary>

请先确认后端服务本身是否已经正常启动：

* 前端开发页面：`http://localhost:5173`
* 后端健康检查：`http://localhost:8000/health`
* 后端文档：`http://localhost:8000/docs`

**使用本地 Ollama 时**：Ollama 服务未启动，或内存/显存不足。尝试手动运行 `ollama run qwen2.5`。WSL/Linux 用户还需确认系统代理没有拦截本地请求（`unset http_proxy`）。

**使用云端 API 时**：检查 `.env` 中的 `ANTHROPIC_API_KEY` 或 `OPENAI_COMPAT_API_KEY` 是否正确，以及 `LLM_PROVIDER` 是否与所用 Key 匹配。
</details>

<details>
<summary><b>3. 可以不启动服务，直接双击页面文件使用吗？</b></summary>

不可以。这个项目不是一个纯静态 HTML 页面。

Vue 前端依赖 FastAPI 提供的 `/v1/chat/stream`、会话记忆和 RAG 检索能力，因此应使用以下两种方式之一：

1. **开发模式**：运行 `./scripts/run.sh`，访问 `http://localhost:5173`
2. **单端口模式**：构建 `frontend/dist` 后启动 FastAPI，访问 `http://localhost:8000`
</details>

<details>
<summary><b>4. 我想换成其他角色（比如三司绫濑）可以吗？</b></summary>





完全可以！本项目是通用架构。你只需要：

1. 准备绫濑的对话记录（替换 <code>data/raw/train.jsonl</code>）。
2. 运行 <code>python scripts/init_vector_db.py</code> 重新构建记忆库。
3. 替换 <code>frontend/public/</code> 下的立绘资源。
4. 修改系统提示词中的名字与设定即可。
</details>

---

## 参与贡献

我们非常欢迎来自社区的力量！无论是提交 Bug 修复、改进前端样式，还是提供更优质的剧本数据集，都可以通过以下流程参与：

1. `Fork` 本仓库。
2. 创建您的特性分支: `git checkout -b feature/AmazingFeature`
3. 提交您的更改: `git commit -m 'feat: Add some AmazingFeature'`
4. 推送至分支: `git push origin feature/AmazingFeature`
5. 开启一个 Pull Request。

*(注：提交代码前，请务必运行 `./scripts/run_linter.sh` 确保代码符合 Ruff 和 Mypy 的规范。)*

---

## 协议声明 

本项目采用 **[GNU General Public License v3.0](https://www.gnu.org/licenses/gpl-3.0)** 许可。
本项目仅作为技术探讨与学习使用，立绘及剧本等相关资源版权归原作公司（Yuzusoft）所有，请勿用于任何商业用途。
