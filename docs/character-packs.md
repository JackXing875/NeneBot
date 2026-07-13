# Character Pack 与不可变 Artifact（v1）

本页定义重构期间新增的最小安全边界。它不改变旧 `train.jsonl` 和离线脚本，
但新的知识内容应先成为可验证的 Character Pack，再离线构建并原子发布 Artifact。

## 为什么 manifest 使用 JSON

长期计划曾以 YAML 描述 Pack。v1 刻意改用严格 JSON：

- Python 标准库即可解析，不新增 YAML 解析器和隐式类型风险；
- 能拒绝重复 key、未知字段和类型转换；
- canonical JSON 可以稳定计算逐条内容 hash、Pack hash 与 Artifact hash。

如果未来增加 YAML authoring UI，应先把 YAML 编译成这里定义的 canonical JSON，运行时仍只消费
已验证 JSON。

## Pack 目录

```text
packs/demo-companion/
├── manifest.json
├── persona.md
└── knowledge.jsonl
```

`manifest.json` 必须完整声明身份、版本、入口文件和授权来源：

```json
{
  "schema_version": 1,
  "pack_id": "demo-companion",
  "version": "1.0.0",
  "display_name": "Demo Companion",
  "default_locale": "zh-CN",
  "persona_path": "persona.md",
  "knowledge_path": "knowledge.jsonl",
  "provenance": {
    "creator": "Example Studio",
    "source": "Original authored demo",
    "license": "CC0-1.0",
    "rights": "owned"
  }
}
```

`rights` 只能是 `owned`、`licensed` 或 `public-domain`。manifest 和入口文件禁止绝对路径、
`..`、反斜杠和符号链接。

## Knowledge Record

每行只能包含一个严格 v1 record，未知字段会导致整个 Pack 验证失败：

```json
{
  "schema_version": 1,
  "id": "greeting-1",
  "content_sha256": "<64 lowercase hex characters>",
  "trigger": "你好",
  "response": "你好，很高兴见到你。",
  "tags": ["greeting"],
  "provenance": {
    "creator": "Example Studio",
    "source": "Original authored demo line 1",
    "license": "CC0-1.0",
    "rights": "owned"
  },
  "safety": {
    "classification": "general",
    "reviewed": true,
    "notes": "Human-reviewed original fixture"
  }
}
```

`content_sha256` 是 `trigger`、`response`、排序后的 `tags`、`provenance` 和 `safety` 的
canonical JSON SHA-256。修改内容但不更新 hash 会 fail closed。可以由导入器调用
`calculate_knowledge_content_sha256()` 生成；不要手工猜测。记录 id 和 content hash 都必须唯一。

Pack 通过 `validate_character_pack()` 后会得到：

- manifest、persona、knowledge 三个文件 hash；
- Pack `content_hash`；
- 保留逐条 `content_sha256`、来源、许可证、权利基础和安全结论的 records。

后续索引器必须把 `id`、`content_sha256` 和 provenance 一起写入向量 metadata，不能再像 legacy
管线一样只保留回答文本。

## Artifact Manifest 与发布

构建器应在 `ArtifactStore.stage(pack_id)` 提供的同文件系统临时目录中生成索引和 metadata，
然后调用：

1. `build_artifact_manifest(...)`：扫描所有输出并记录逐文件 SHA-256/size；
2. `write_artifact_manifest(...)`：写入 canonical `artifact-manifest.json`；
3. `ArtifactStore.publish(stage)`：完整复验后发布。

Artifact manifest 包含：

- Pack id/version/content hash/manifest hash；
- Artifact semantic version 和 deterministic artifact hash；
- embedding model、vector dimension、record count；
- Pack provenance；
- 所有生成文件的 path、size 和 SHA-256。

Store 使用不可变目录和小指针：

```text
artifacts/demo-companion/
├── current.json
└── versions/
    ├── 1.0.0-<hash-prefix>/
    └── 1.1.0-<hash-prefix>/
```

stage 完成后以同文件系统 `os.replace` 移入 `versions/`，最后原子替换 `current.json`。
构建失败不会改动当前指针，旧版本保留用于回滚。解析当前版本是严格只读操作：目录缺失、pointer
损坏、额外文件、文件篡改、manifest hash 不一致都会拒绝加载，也不会顺手创建目录。

当前最小实现尚未加入跨进程发布锁；部署系统必须串行执行同一个 Pack 的 publish。下一阶段应增加
per-pack 文件锁或由单独 artifact builder 服务负责发布。

## 在线知识库止血策略

`GET /admin/api/knowledge/overview` 保持可用，并返回 `operations` 策略状态。旧的：

- `POST /admin/api/knowledge/import`
- `POST /admin/api/knowledge/rebuild`

默认返回 `503`，不会写活动数据集或重建活动索引。仅为短期回滚兼容，可以显式设置：

```bash
NENEBOT_ENABLE_LEGACY_ONLINE_KNOWLEDGE_MUTATIONS=true
```

该开关会恢复旧写路径，不具备版本化发布的完整保护，不应在正常生产环境开启。旧离线脚本和
`write_jsonl_dataset()` 暂时保留；后续迁移完成后删除这一逃生舱。
