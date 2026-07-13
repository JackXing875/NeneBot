# Persona Studio

> NeneBot 0.7 迁移预览——本地优先、可审计的 Character Agent Studio / Runtime。

[English](README.md) · [迁移路线](MEMORY.md) ·
[Character Pack v1](docs/character-packs.md)

这个仓库正在从“绑定单一角色的 RAG 对话 Demo”逐步重构为通用角色 Agent 平台，用来编写、
校验、测试和运行用户有权使用的角色内容。迁移不会一次性推倒重来：0.7 分支仍保留兼容运行时，
新的内容边界与运行时边界会分阶段接管旧系统。

## 当前已经有什么

下面描述的是现有 0.7 兼容运行时，不是已经完成的 Studio：

- FastAPI 后端，以及旧的 `POST /v1/chat`、`POST /v1/chat/stream` 接口；
- 增量 SSE 输出、请求限流、带 scope 的 token 鉴权和运维探针；
- Vue/Vite 对话页与偏运维用途的后台页面；
- Ollama、Anthropic 和 OpenAI-compatible LLM 适配器；
- 旧版 FAISS / sentence-transformers 检索链路；
- 默认进程内会话历史，以及可选 Redis 后端；
- 严格的 Character Pack JSON v1 校验和不可变 Artifact 暂存、发布基础设施。

Character Pack 与版本化 Artifact 目前只是已经落地的基础层：`/v1/chat` 尚未默认从 Pack 加载内容，
前端也还不是完整的 Pack 编辑器。旧 RAG 接口会作为兼容层保留到新链路完成接管。

旧版在线知识导入与索引重建接口默认关闭。新的内容应先离线校验、构建，再发布为不可变 Artifact。
已实现的 schema、来源记录、完整性校验、原子发布方式和当前限制见
[Character Pack 与 Artifact v1](docs/character-packs.md)。

## 目标方向

最终产品是围绕单一版本化 Character Pack 边界构建的模块化、本地优先 Persona Studio：

- persona、prompt、examples、knowledge、theme、eval，以及来源、许可和安全元数据一起版本化；
- 离线构建器负责内容校验，并发布可追溯、可回滚的 Artifact；
- Web 兼容 API 与经过明确授权的外部渠道共用一个 Agent Kernel；
- 类型化事件和经过 policy 校验的动作支持审计与回放；
- Studio 提供 Pack 审核、评测、发布与回滚；
- 群聊模拟器先离线评测决策，达标后才可能连接真实发送渠道；
- 长期记忆和自主外部集成之前，先完成同意、保留、查看与删除等隐私能力。

这些是分阶段目标，不是当前版本的功能承诺。详细决策、进度和验收标准记录在
[MEMORY.md](MEMORY.md)。

## 安全的本地快速启动

需要准备：

- Python 3.10 或更高版本；
- Node.js 22.12 或更高版本，以及 npm；
- 一个可访问的 LLM 后端。默认本地开发配置使用 Ollama。

先创建隔离的后端环境和本地配置：

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Windows 可使用 `venv\Scripts\activate` 激活环境。启动前请检查 `.env`，只填写实际使用的
provider 配置；不要提交 `.env` 或 API Key。如果沿用默认 Ollama 配置，请先安装对应模型并确认
Ollama 服务已经运行。

使用 lockfile 安装前端依赖：

```bash
cd frontend
npm ci
cd ..
```

在一个终端中仅监听本机地址启动后端：

```bash
source venv/bin/activate
python scripts/launch.py local --host 127.0.0.1 --reload
```

另开终端启动前端：

```bash
cd frontend
npm run dev
```

浏览器访问 `http://localhost:5173`；API 文档位于 `http://127.0.0.1:8000/docs`。

如果希望用一个本地端口提供编译后的前端与 API，可以先构建前端，再启动不带热重载的后端：

```bash
cd frontend
npm ci
npm run build
cd ..
source venv/bin/activate
python scripts/launch.py local --host 127.0.0.1
```

随后访问 `http://127.0.0.1:8000`。

### 鉴权与网络暴露

开发示例默认关闭鉴权，便于仅在 loopback 上调试。绑定非本机地址之前，应在 `.env` 中启用鉴权，
并配置彼此独立的 scope token；也可以复制
[config/api_tokens.json.example](config/api_tokens.json.example) 作为本地 registry：

```env
API_AUTH_ENABLED=true
API_AUTH_TOKENS=local-chat|chat:replace-this,local-ops|ops:replace-this-too
CORS_ALLOW_ORIGINS=https://your-ui.example
```

鉴权开启但没有有效 token 时，服务会拒绝受保护请求，不会静默降级。所有 token 都应按密钥管理。
生产配置还要求使用 Redis 会话；开发环境默认的进程内历史不会持久保存。

## 运维端点

规范端点如下：

| 端点 | 访问要求 | 含义 |
| --- | --- | --- |
| `GET /livez` | 公开 | 最小化进程存活状态 |
| `GET /readyz` | 公开 | 最小化就绪状态；依赖未就绪时返回 `503` |
| `GET /ops/health` | 开启鉴权后需要 `ops` scope | 详细运行状态与诊断信息 |

`/health`、`/health/live`、`/health/ready` 仅作为已弃用的兼容别名保留。详细 health 与 metrics
可能暴露运维信息，不应在缺少访问控制时公开到不可信网络。

## 验证

安装前后端依赖后，运行统一检查：

```bash
./scripts/run_linter.sh
```

它会检查格式、lint、后端与脚本的严格类型、后端测试，以及前端生产构建。测试通过只能证明测试
覆盖到的行为，不能证明回答没有错误、角色一定一致、内容一定安全，也不能证明数据拥有合法授权。

## 迁移、隐私与内容授权

- 仓库中可能仍有等待 Phase 1 迁移的第三方角色数据、剧本或美术。除非你已独立确认再分发权利，
  应把这些文件当作本地私有迁移输入；代码许可证不会自动授予第三方内容的使用权。
- 只导入自己拥有、获得许可或依法可以使用的材料。Character Pack 必须保留来源、许可证、权利
  基础、安全审核与内容 hash。
- 使用云端 LLM 时，用户消息、prompt 和检索片段可能被发送给服务商。处理敏感内容前应获得明确
  同意，并检查服务商的数据使用与保留政策。
- 0.7 会话层只是兼容设施，不是完整隐私系统。持久记忆、用户查看/导出/删除、同意和保留期限
  仍属于迁移工作。
- Telegram 等外部渠道必须得到运营者和参与者的明确授权。不要把当前开发运行时作为自主 Agent
  直接接入真实社群。
- 后续版本删除工作树中的文件，并不会抹除 Git 历史。历史重写、凭据轮换和公开再分发都需要
  独立的运维决策。

以上是工程迁移提示，不构成法律意见。

## 仓库结构

```text
src/                 FastAPI 兼容运行时与新的 knowledge 基础层
frontend/            Vue/Vite 兼容客户端
src/knowledge/       Character Pack 校验与不可变 Artifact 工具
docs/                迁移期格式与运维说明
scripts/             启动、迁移、评测与仓库检查脚本
tests/               后端与 ASGI 回归测试
MEMORY.md            长期路线、架构决策与实施日志
```

源码使用 [GPL-3.0](LICENSE) 发布；第三方内容授权必须与软件许可证分开核查。
