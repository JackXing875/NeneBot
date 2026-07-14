# Character Pack 与不可变 Artifact v1

Character Pack 是 Persona Studio 唯一的角色内容边界。运行时不读取 Pack 源目录，也不接受在线
知识写入；它只读取离线构建、完整性复验并显式发布的 Artifact。

## Pack 目录契约

```text
pack/
├── manifest.json
├── persona.md
├── prompt.md
├── knowledge.jsonl
├── evaluation.json
└── theme.json
```

`manifest.json` 使用严格 JSON，必须声明 `schema_version`、`pack_id`、semantic `version`、
`display_name`、`default_locale`、上述五个内容路径，以及 Pack 级 `provenance`。未知字段、重复
key、绝对路径、`..`、反斜杠和符号链接都会使校验失败。

`provenance` 必须包含：

- `creator`：内容作者或权利主体；
- `source`：可定位的原始来源；
- `license`：明确的许可证或授权名称；
- `rights`：`owned`、`licensed` 或 `public-domain`。

## Knowledge Record

`knowledge.jsonl` 每个非空行是一个严格 v1 record：

```json
{
  "schema_version": 1,
  "id": "greeting-1",
  "content_sha256": "<64 lowercase hex>",
  "trigger": "你好",
  "response": "你好，很高兴见到你。",
  "tags": ["greeting"],
  "provenance": {
    "creator": "Example Studio",
    "source": "original/greetings.jsonl",
    "license": "CC0-1.0",
    "rights": "owned"
  },
  "safety": {
    "classification": "general",
    "reviewed": true,
    "notes": "Reviewed original fixture"
  }
}
```

`content_sha256` 覆盖 trigger、response、已排序 tags、provenance 和 safety 的 canonical JSON。
所有 id/hash 必须唯一；`reviewed=false` 不可发布。

`evaluation.json` 包含至少一个检索 case，每个 case 声明 query、top_k 和必须命中的 record id。
`theme.json` 只接受三种十六进制颜色和 `initials` 头像，因此公开 Pack 不需要绑定位图美术。

## 离线构建与发布

```bash
persona pack validate packs/demo
persona pack build packs/demo
persona pack promote mira-demo 1.0.0
persona pack eval packs/demo
persona pack rollback mira-demo
```

构建器把 trigger 编码到 FAISS，并把 record id/content hash、Pack id/version、回答、tags、完整
provenance 与 safety 写入 metadata。生成目录还包含运行时描述、评测文件和
`artifact-manifest.json`。Artifact manifest 记录 Pack hash、embedding model、维度、记录数、
每个文件的 size/hash，以及由这些内容推导的 artifact hash。

Artifact Store 的结构为：

```text
artifacts/<pack-id>/
├── current.json
└── versions/
    ├── 1.0.0-<hash-prefix>/
    └── 1.1.0-<hash-prefix>/
```

构建先进入同文件系统 staging 目录，完整复验后再原子移动到 `versions/`。`build` 默认不改变
`current.json`；`promote` 在 per-Pack 排他锁内原子替换指针。运行时每次启动都会重新核验指针、
manifest、文件集合、size/hash、向量数、metadata 数和来源字段。缺失、额外文件或篡改都会 fail
closed。`rollback` 激活当前版本之前的已安装版本。

## 按来源清退

来源删除必须形成新 Pack 版本：

```bash
persona pack derive private/source-pack \
  --exclude-source "vendor/export-2026-01.jsonl" \
  --output private/source-pack-2.1.0 \
  --version 2.1.0
```

匹配是对 `provenance.source` 的精确比较。工具不会修改源 Pack；它删除匹配记录、同步裁剪评测
期望，在临时目录中完整校验后才原子生成目标目录。若没有匹配、剩余知识为空或剩余评测为空，
操作失败。派生结果仍需执行 build/eval/promote，旧 Artifact 因而保持可审计、可回滚。

## 运行时边界

- `/v1/chat` 与 `/v1/chat/stream` 只使用当前 Artifact 的 persona、prompt 和 FAISS metadata；
- `/v1/character` 提供当前 Pack 身份、主题和权利信息；
- 返回的 references 保留 record id、content hash、Pack 版本、source、license 和安全分类；
- `/admin/api/knowledge/import`、`/admin/api/knowledge/rebuild` 是固定返回 `410` 的兼容墓碑；
- Admin 页面只读取 Artifact 状态，不具有内容写权限。

旧文件从当前工作树删除不等同于清除 Git 历史。公开仓库前如需历史重写、凭据轮换或法律审查，
应作为独立的发布运维工作执行。
