# Persona Studio

> 本地优先、重视内容权利、检索结果可追溯的 Character Pack 运行时。

[English](README.md) · [Character Pack v1](docs/character-packs.md) ·
[私有迁移指南](docs/private-pack-migration.md) · [长期路线](MEMORY.md)

Persona Studio 把角色内容与聊天运行时彻底分开。persona、prompt、知识、检索评测、主题、
来源、许可证和安全审核统一放在严格的 Character Pack 中；离线构建器把 Pack 编译成经过完整性
校验的 FAISS Artifact，Web 与 Telegram 运行时只读取明确发布的 Artifact。

仓库只附带一个原创、使用 CC0 许可的演示 Pack：**米拉（Mira）**。她是架空档案馆的夜班
引导员，使用代码生成的首字母头像；仓库不再附带第三方角色美术或对白语料。

## Phase 1 已实现

- 严格 Pack 校验：拒绝重复 key、路径穿越、符号链接、超限文件和未知字段；
- 逐条知识与整个 Pack 的 canonical SHA-256；
- 每条知识都必须声明来源、许可、权利基础并完成安全审核；
- 离线构建 FAISS Artifact，并在检索 metadata 中保留完整来源；
- Pack 自带确定性的检索评测集；
- 内容寻址的 Artifact 版本、完整性复验、原子发布和回滚；
- 通过派生新 Pack 版本按精确来源清退记录，再走相同构建流程；
- 只读的 `/v1/chat`、`/v1/chat/stream`、`/v1/character` 运行接口；
- 同步与 SSE 响应均返回引用元数据；
- 不依赖角色图片的 Vue 对话页，以及只读 Artifact 运维面板。

旧在线知识导入与重建 URL 固定返回 HTTP `410`，内容无法绕过 Pack / Artifact 边界进入运行时。

## 快速开始

需要 Python 3.10+、Node.js 22.12+、npm，以及一个可访问的 LLM provider。开发环境默认使用
Ollama。

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install -e . --no-deps
cp .env.example .env

cd frontend
npm ci
cd ..
```

启动运行时前，先构建、发布并评测演示 Pack：

```bash
persona pack validate packs/demo
persona pack build packs/demo
persona pack promote mira-demo 1.0.0
persona pack eval packs/demo
```

同时启动前后端：

```bash
persona dev --host 127.0.0.1
```

浏览器访问 `http://localhost:5173`。API 位于 `http://127.0.0.1:8000`，接口文档在 `/docs`。
`persona local --host 127.0.0.1` 只启动后端。

## Pack 发布流程

```bash
# 1. 校验所有源文件。
persona pack validate path/to/pack

# 2. 安装不可变 Artifact，但不改变运行时当前版本。
persona pack build path/to/pack --artifact-version 1.1.0

# 3. 使用精确版本、完整 hash 或 Artifact 目录名发布。
persona pack promote my-pack 1.1.0

# 4. 使用 Pack 中的 fixtures 评测当前 Artifact。
persona pack eval path/to/pack

# 5. 回到上一个已安装版本。
persona pack rollback my-pack
```

清退某个来源时，不要直接修改活动索引，而应派生一个新 Pack：

```bash
persona pack derive private/my-pack \
  --exclude-source "licensed/source-a.jsonl" \
  --output private/my-pack-1.2.0 \
  --version 1.2.0
persona pack build private/my-pack-1.2.0
```

`private/`、`packs/private/` 和生成的 `artifacts/` 默认被 Git 忽略；`derive` 永远不会修改源 Pack。

## API 与运维

| 端点 | 用途 |
| --- | --- |
| `GET /v1/character` | 当前 Pack 身份、主题和权利信息 |
| `POST /v1/chat` | 带可追溯引用的兼容聊天 API |
| `POST /v1/chat/stream` | meta/chunk/error/done SSE 流 |
| `GET /livez` | 公开进程存活探针 |
| `GET /readyz` | 公开最小就绪探针 |
| `GET /ops/health` | 受保护的详细诊断 |
| `GET /admin/api/knowledge/overview` | 受保护的只读 Artifact / 版本视图 |

启用鉴权时，应使用彼此独立的 `chat` 与 `ops` scope 凭据；生产环境要求 Redis 会话。使用云端
LLM 时，用户消息、Pack prompt 和检索片段可能被发送给服务商，处理敏感内容前应获得知情同意并
检查服务商的数据保留条款。

## 验证

```bash
./scripts/run_linter.sh
```

该命令执行 Ruff 格式/lint、严格 mypy、后端测试和前端生产构建。测试不能代替内容事实核验或
法律审核；只应发布自己拥有、已获许可或依法可使用的内容。

## 仓库结构

```text
packs/demo/          原创公开演示 Pack
src/knowledge/       Pack、构建器、Artifact Store 与运行时契约
src/                 FastAPI 运行时和适配器
frontend/            Pack 驱动的对话页和只读运维面板
docs/                格式与私有迁移指南
tests/               单元、ASGI 与端到端契约测试
MEMORY.md            长期路线与实施记录
```

源码使用 [GPL-3.0](LICENSE)；Pack 内容使用其 manifest 中独立声明的许可和来源。
