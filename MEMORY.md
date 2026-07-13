# NeneBot 重构长期记忆

> 本文件是本项目重构的持续上下文与执行契约。后续工作开始前先阅读本文件，完成一项后同步更新状态、决策和验证结果。

最后更新：2026-07-13  
当前分支：`fix/mypy-debt`  
当前阶段：Phase 0 已完成 — 按用户要求暂停在 Phase 1 前

## 1. 最终产品方向

NeneBot 不再继续扩张为一个绑定单一版权角色的 RAG 聊天 Demo，而是逐步重构为：

> **Persona Studio：本地优先、可审计的角色 Agent 构建与运行平台。**

用户通过自己拥有授权的文本、人格、示例和视觉资源创建 Character Pack。平台负责：

- Pack 导入、schema 校验、来源与许可证记录；
- 内容安全审查、知识构建、质量评测、版本发布与回滚；
- 普通对话测试台；
- 群聊 Agent 离线回放模拟器；
- 明确授权后再接入 Telegram、OneBot 等真实渠道。

现有 Nene 内容只作为本地私有迁移对象，不应继续成为公共发行物的默认数据。现有 `data/prompts.yaml` 中的群聊 Agent 草案保留其产品思想，但不会直接接线到生产运行时。

## 2. 不可变的架构原则

1. **模块化单体优先。** 这个项目的规模不需要微服务，也不需要为了“分层”制造空抽象。
2. **Character Pack 是唯一内容边界。** persona、prompt、knowledge、examples、theme、eval 必须属于明确版本的 Pack。
3. **来源不能丢。** 每条知识至少携带 source、license、safety、content hash；构建索引后仍可追溯和清退。
4. **运行时只读 artifact。** 知识库在临时目录离线构建、自检并原子发布；Web 请求不能同步覆写活动数据或索引。
5. **默认 SQLite。** 单机默认用 SQLite 原子保存 event、conversation、memory、inbox/outbox；确有水平扩展需求时才引入 Redis/Postgres。
6. **模型只做决策，不直接产生副作用。** 所有 message/reply/react/sticker/search 动作先经过类型校验和 policy，再由 transport executor 执行。
7. **不保存模型思维链。** 将草案中的 `thought` 改成有限枚举的 `decision_reason`；不得对用户展示或持久化隐藏推理。
8. **隐私能力先于长期记忆。** 群聊记忆必须有群级同意、逐用户查看/删除、TTL、敏感字段禁采和审计。
9. **兼容迁移，不做一次性爆炸重写。** 旧 `/v1/chat` 和 Telegram 先成为新 AgentKernel 的薄适配层，验证稳定后再删除旧壳。
10. **可验证才算完成。** 每个阶段都要有自动化验收；README 宣传不得超过测试能够证明的能力。

## 3. 目标结构

```text
nenebot/
  app.py                 # FastAPI factory 与生命周期
  config.py              # 唯一配置入口
  container.py           # 资源创建与关闭
  agent/
    models.py            # Event / Context / Decision / Action
    service.py           # 唯一 Agent 用例
    context.py           # history / memory / search / token budget
    prompt.py            # Character Pack 编译与渲染
    policy.py            # 输出校验和动作安全边界
  llm/
    protocol.py
    streaming.py
    openai_compat.py
    anthropic.py
    ollama.py
  storage/
    conversations.py
    sqlite.py
    redis.py              # 可选扩展
  transports/
    http.py
    telegram.py
    onebot.py
  ops/
    health.py
    telemetry.py

tools/
  knowledge/
  evaluation/

packs/
  demo/
    manifest.json
    persona.md
    prompt.yaml
    knowledge.jsonl
    eval.yaml
    theme/
```

只有确有多个实现的边界才保留 Protocol：LLM provider、event/conversation store、transport 和 tool。FAISS 若保留，只是可选的 ExampleRetriever，不再成为整个应用的中心。

## 4. 审计基线（重构前）

- 后端、脚本、测试与前端源码约 8,415 行；Git 管理 219 个文件。
- `src/**` 共 4,492 行，真正的问题是职责与依赖穿层，而不是绝对规模。
- 基线测试：`85 passed`，另有 5 个 FAISS/SWIG 弃用警告。
- Ruff：现有规则通过。
- Mypy：`src` 的 43 个文件通过 strict；`scripts` 因旧脚本和双重导入未通过。
- 前端在当前机器可构建，但 `frontend/package.json` 和 lockfile 被根目录 `*.json` 规则忽略，干净 clone 无法构建。
- 本地 `venv` 为 Python 3.12 且约 8.5GB，混有大量项目外依赖，不能作为可复现性证据。
- 当前 CI 只跑 Python 3.10、Ruff 和 pytest，不跑 Mypy、前端、格式、覆盖率、安全或镜像 smoke。
- 当前工作开始时 Git 工作树干净。

### 已确认的 P0 缺陷

1. 鉴权关闭时 scope 仍检查空集合，默认 chat/ops 路由返回 403；鉴权开启但无 token 的配置语义也不清晰。
2. `resilient_stream` 先收集完整 provider 输出再 yield，SSE 不是真流式。
3. 全局忽略 `*.json` / `*.jsonl`，误伤前端 manifest、lockfile 和未来测试 fixture。
4. 没有 `.dockerignore`，本地 `.env`、虚拟环境、Git、缓存、备份和审核数据可能进入构建上下文。
5. `/health` 受 ops 保护却被 Railway 当无凭据探针；`/health/ready` 又通过函数直调绕过依赖并暴露详细信息。
6. 索引“文件存在”“成功加载”“ready”判断不一致，可能出现 0 vectors 仍 ready。
7. RAG 阈值无命中时重新使用全部低分结果，行为与文档相反。
8. embedding、同步 Redis、知识重建在 async 请求内阻塞事件循环。
9. Admin 先覆写活动数据再重建，无完整 schema、原子发布、锁和多 worker reload。
10. Docker 每次启动无条件重建索引并吞掉失败，runtime、setup、Docker 有三套构建入口。
11. session ID 由客户端任意指定，未绑定 principal/transport；Redis append 非原子，内存存储无 TTL。
12. Telegram 缺幂等 inbox/outbox、连接复用、可靠 offset、强制 webhook secret 与群聊 thread 隔离。
13. 三个 prompt 真相源并存；RAG system prompt 还有行尾反斜杠导致规则文本粘连。
14. 前端忽略 SSE error/references，清空只删除 localStorage，开启 auth 后聊天页不会携带 token。

### 内容与发行风险

- 仓库包含第三方游戏完整路线、翻译、训练数据和角色美术；README 的免责声明不能替代再分发授权。此判断不是法律意见。
- 角色设定与原始路线包含敏感/成人内容；有限关键词得到的 “0 explicit hits” 不能视为独立安全审查。
- 云端 LLM 模式会发送用户对话和检索片段，当前没有清晰的同意、保留和删除政策。
- 清理当前文件与重写 Git 历史是两件事；历史清理属于破坏性协作操作，必须单独确认后执行。

## 5. 分阶段路线

### Phase 0 — 建立可信基线（已完成）

目标：让当前系统的测试结果能够代表真实运行状态。

- [x] 修复 auth disabled 与配置 fail-closed，补真实回归测试；日志不得记录 token 片段。
- [x] 恢复真正逐块输出的 LLM/SSE，并规定“首块前可重试、首块后不透明重试”。
- [x] 缩窄 ignore 规则，跟踪前端 manifest/lock，统一版本元数据。
- [x] 增加严格 `.dockerignore`，防止 secret、环境、缓存和私有数据进入构建上下文。
- [x] CI 增加 format check、scripts Ruff、Mypy、前端 clean build。
- [x] 增加真实 ASGI 测试，覆盖 auth 开/关、scope、SSE 正常/中断/断连、429 和 health probes。
- [x] 拆成公开最小 `/livez`、`/readyz` 与受保护详细 `/ops/health`。
- [x] 修复检索阈值 fallback、坏索引 readiness 与日志 import side effect。
- [x] 默认禁用不安全的在线 knowledge import/rebuild；只读 overview 保留，旧写路径仅可通过显式 emergency override 临时恢复。
- [x] 删除第一批明确垃圾和无引用旧脚本，并跑全套回归。

验收：干净 clone 能安装和构建；默认配置可聊天；真流式首块测试通过；CI 覆盖 Python、前端和类型；Docker context 不含本地 secret。

### Phase 1 — Character Pack 与内容边界

- [x] 定义严格 `manifest.json` 与 knowledge schema：id/version/source/license/safety/逐条 content hash；JSON 是刻意选择，以避免 YAML 隐式类型/额外依赖并支持 canonical hash。
- [ ] 创建原创或明确许可的最小 demo Pack，保住端到端基线。
- [ ] 将第三方 Nene 语料和美术移出公共发行物，提供本地私有迁移说明。
- [ ] 将 persona/prompt/examples/theme/eval 统一从 Pack 加载，消灭多套 prompt 真相。
- [ ] 合并五段数据脚本为 `persona pack validate/build/eval/promote`。
- [x] 建立临时目录 + 不可变版本目录 + 原子 `current.json` 指针的 artifact 基础，记录 Pack/file hash、模型、维度、schema/build 版本和 provenance；真实 embedding builder 尚未迁入。
- [ ] 全链路保留 provenance，支持按 source 删除和重建。

验收：公共发行物不含未授权演示内容；demo Pack 可验证、构建、对话、展示引用并安全回滚。

### Phase 2 — AgentKernel 与可靠存储

- [ ] 建立 `ConversationEvent`、`Decision` 和 discriminated `Action` 模型。
- [ ] 引入 `AgentKernel.decide(context)` 与 `PolicyValidator`。
- [ ] 旧 `/v1/chat` 转换为单事件并消费 message action。
- [ ] SQLite 保存 conversation/event/memory/inbox/outbox；ID 由服务端签发并绑定 principal/transport。
- [ ] history 按 token budget 截断；实现 TTL、查看、导出、真实删除。
- [ ] provider client 统一生命周期、超时、错误分类、取消和指标语义。

验收：Web 与 Telegram 共用同一个 Agent 用例；事件和动作可重放；并发 turn 不丢失或串线。

### Phase 3 — Chat、Studio 与 Simulator 前端

- [ ] Vue 迁移 TypeScript，拆分组件、API client 和流式状态机。
- [ ] `/chat` 支持停止、重试、历史恢复、真实删除、引用抽屉、模型/Pack 选择和隐私提示。
- [ ] `/studio` 支持 Pack 导入、来源/许可/安全报告、diff、构建、评测、发布、回滚。
- [ ] `/simulator` 对群聊 fixture 离线回放 silent/message/reply/react/search/memory 决策。
- [ ] 补前端单测、可访问性、移动端和端到端测试。

验收：管理写操作都有预览、确认和回滚；客户端完整处理 stream meta/chunk/error/done；清空会真正删除服务端数据。

### Phase 4 — 自主群聊 Agent

- [ ] 将群聊草案拆成 decision、memory、tool、image 等版本化 prompt 模块。
- [ ] 使用结构化输出；`thought` 改为 `decision_reason`，动作数量和目标严格校验。
- [ ] inbox/outbox + update id 幂等；webhook 快速 ack，后台可靠处理。
- [ ] 搜索、图片、sticker、reaction executor 与模型决策分离。
- [ ] 建立 silent precision、误记忆率、错误动作率、成本和延迟评测。
- [ ] 只有离线回放达标且群级明确授权后，才开启真实自动发送。

验收：重复 update 不重复发送；用户可关闭 Agent 和删除记忆；模型无法绕过 policy 直接调用外部副作用。

### Phase 5 — 删除旧壳并发布

- [ ] 删除巨型 `RAGPipeline`、无效 `BaseVectorStore`、旧 session store、在线索引 mutation 和重复 admin/metrics 包装。
- [ ] 删除多套 launcher 与平台脚本，只保留一个 console command 和一个 task runner。
- [ ] 评估后将 torch/FAISS/sentence-transformers 降为可选 extra，或彻底移除。
- [ ] 使用锁文件、依赖分组、多版本 CI、容器 smoke、安全扫描、SBOM 和备份恢复测试。
- [ ] 重写 README、CHANGELOG、release checklist，统一版本。

验收：目标结构成为唯一运行路径；兼容层与旧依赖完全删除；新 clone、升级、备份和恢复都有自动化证明。

## 6. 明确删除/合并候选

可直接删除或在近期清退：

- `scripts/preprocess.py`：旧 CWD 路径、旧英文 prompt、无当前调用。
- `src/infrastructure/vector_store/base.py`：只有一个实现且上层仍依赖具体 FAISS。
- `resolve_llm_model_name()`、`VectorStoreError`：无引用。
- Vite/Vue 示例资源、`*:Zone.Identifier`、模板前端 README、未使用 `axios`。
- Docker 启动时 `init_vector_db.py || true`。
- `src/main.py` 的第二个 reload 启动入口。

应合并或迁移：

- corpus 构建、promotion、索引和评测 → `tools/knowledge` / `tools/evaluation`。
- 多套 JSONL loader、pair extractor、dataset summary → 单一严格 schema/loader。
- `logger/audit/metrics/observability/tracing` → 小型 telemetry 模块并优先使用成熟库。
- `/v1/chat` 与 `/v1/chat/stream` → 同一 service stream，非流式只是消费它。
- shell/bat/launch/Makefile → 一个 console command。

## 7. 执行纪律与状态更新

- 不读取、打印或提交 `.env` 中的值。
- 不把本地 `venv`、model cache、vector artifact 或私有 Pack 当作源码。
- 不在没有原创/许可替代 Pack 前直接删掉唯一可运行数据基线。
- 不执行 Git 历史重写、凭据轮换、外部发布或真实群聊发送，除非用户明确授权。
- 每个实现批次结束必须运行与风险相称的测试，并在下面记录结果。

## 8. 实施日志

### 2026-07-13 — 全仓库审计

- 完成后端、前端、测试、脚本、依赖、CI、部署、数据和产品方向审计。
- 确认 Persona Studio / 角色 Agent Runtime 方向。
- 建立本长期记忆和分阶段迁移契约。
- Phase 0 第一批修复完成：
  - 修复默认鉴权 403、配置 fail-open 和 token 片段日志；scope dependency 改为 async，避免真实 ASGI 请求卡住。
  - LLM stream 改为首块立即透传；首块前允许重试，首块后失败不重试。
  - 新增 `/livez`、`/readyz`、`/ops/health`；Railway 改用最小 readiness；空/不一致索引不再 ready。
  - RAG 低于阈值时返回空上下文；修复粘连的 system prompt 规则。
  - 修复 `.gitignore`，恢复前端 manifest/lock；增加白名单 `.dockerignore` 和前后端 CI 门禁。
  - 删除旧 `scripts/preprocess.py`、模板前端文件、示例 SVG、Zone.Identifier 和未使用 axios。
  - 前端版本更新为 `0.7.0-beta.1`，HTML 语言与标题修正。
- 验证：93 tests passed；Ruff format/lint 通过；Mypy 50 files 通过；`npm ci` 与 Vite production build 通过；`git diff --check` 通过。
- 此批之后已在 Phase 0 收口中将 Vite 与间接构建依赖升级到安全补丁，最终 `npm audit` 为 0；当前环境没有 Docker daemon，镜像构建验证未执行；第三方内容清退留到 Phase 1。
- 下一入口：补 SSE 断连/429 ASGI 测试，限制 query/session，禁用不安全在线 knowledge mutation，并开始不可变 knowledge artifact 设计。

### 2026-07-13 — Knowledge 止血与 Character Pack/Artifact 基础

- `POST /admin/api/knowledge/import` 与 `/rebuild` 默认 fail closed（503），overview 暴露 `offline_artifacts_only` 策略；legacy 路径需显式设置 `NENEBOT_ENABLE_LEGACY_ONLINE_KNOWLEDGE_MUTATIONS=true`。
- 新增严格 JSON Character Pack v1：拒绝未知字段、重复 key/id/content、路径穿越、symlink；Pack 和每条 record 必须带来源、许可证、权利基础与安全结论。
- 每条 knowledge record 的 `content_sha256` 对 trigger/response/sorted tags/provenance/safety canonical JSON 重算验证，为后续索引 metadata 与按来源清退提供稳定关联键。
- 新增自验证 Artifact manifest：包含 Pack/content/file hash、artifact version/hash、embedding model、vector dimension、record count 和 provenance。
- Artifact 在同文件系统 stage，发布为不可变版本目录，再原子切换小型 current pointer；失败构建不影响活动版本，resolve 严格只读且对 pointer/额外文件/内容篡改 fail closed。
- JSON 取代原计划 YAML 是刻意决策：不引入解析依赖与隐式类型，便于严格 schema、重复 key 拒绝和 canonical hashing。未来 YAML 仅可作为 authoring 输入并先编译为 canonical JSON。
- 已知下一步：真实索引器还需把 `record.id`、`content_sha256`、provenance 写入 vector metadata；同一 Pack 的并发 publish 暂由外部串行，后续增加 per-pack 锁。

### 2026-07-13 — Phase 0 完成

- 新增真实 ASGI 回归：默认鉴权可访问 `/v1`，SSE 验证 `meta/chunk/done`、provider 中断、客户端断连取消及 upstream `aclose()`，限流稳定返回标准 429 与 `Retry-After`。
- 请求边界完成：query 去空白、拒绝空输入、4,000 字符上限；公共 session 仅接收 canonical UUID v4，内部 Telegram namespace 严格校验。
- Redis history append 改为 `WATCH/MULTI` 乐观事务并保留 TTL，覆盖冲突重试和多线程不丢 turn；生产环境强制 Redis 且连接失败 fail fast，开发环境才允许显式降级到内存。
- 配置增加 environment/provider/backend、URL、端口、温度、token、history、TTL、限流、timeout/retry 等范围校验；staging/prod 缺失知识 artifact 时启动失败，不再运行时偷偷构建。
- Redis health ping 仅在 worker thread 执行，避免阻塞事件循环；FAISS 状态留在原线程，修复真实 ASGI 下跨线程挂起回归。
- Docker 启动不再执行 `init_vector_db.py || true`，新增 `/livez` healthcheck；Railway 使用 `/readyz` 和 `npm ci`。严格 `.dockerignore` 默认排除全部，仅重新纳入构建所需源码与数据。
- Vite 升至 7.3.6；esbuild、picomatch、postcss 锁定到其允许范围内的安全补丁。CI 新增前端 audit，最终 npm 安全审计为 0。
- README 中英文版改为 Persona Studio 迁移预览，明确区分已实现兼容运行时与规划能力，删除版权角色营销、夸张能力承诺和绝对本机链接。
- 最终验证：`scripts/run_linter.sh` 通过；Ruff format/lint 覆盖 82 files；Mypy strict 覆盖 53 source files；`156 passed`（仅 5 个既有 FAISS/SWIG 弃用警告）；`npm ci` clean install、Vite 7.3.6 production build、`npm audit --audit-level=high`（0 vulnerabilities）与 `git diff --check` 全部通过。
- 环境限制：已尝试 `docker build --check`，但当前主机 Docker daemon/socket 不存在，无法执行镜像层级验证。这不改变已完成的 Dockerfile/context 防泄漏修复，后续可在有 daemon 的 CI 或开发机补跑。
- 用户当前只要求 Phase 0；Phase 1 及以后保持暂停。已落下的 Character Pack/Artifact 骨架仅作为下一阶段安全接口，不代表 Phase 1 已整体完成。
