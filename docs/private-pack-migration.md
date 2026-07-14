# 私有 Character Pack 迁移指南

本指南用于迁移你自己拥有或已获许可、但不适合提交到公共仓库的内容。它不授权使用任何第三方
材料，也不代替法律审核。

## 隔离原则

1. 把源材料保存在仓库外，或放入被忽略的 `private/` / `packs/private/`。
2. 不要把原始导出、图片、聊天记录、访问令牌或生成的 `artifacts/` 提交到 Git。
3. 为 Pack 和每条知识分别记录 creator、可定位 source、license 与 rights basis。
4. 在转成 `knowledge.jsonl` 前完成去重、安全审核和个人信息清理。
5. 使用代码原生主题；只有在确实拥有再分发权时才扩展 Pack 来引用美术资源。

## 最小流程

复制 `packs/demo` 的目录结构，在私有目录中替换 persona、prompt、knowledge、evaluation、theme 和
manifest。使用 `calculate_knowledge_content_sha256()` 计算每条记录 hash，然后执行：

```bash
persona pack validate packs/private/my-pack
persona pack build packs/private/my-pack
persona pack promote my-pack 1.0.0
persona pack eval packs/private/my-pack
```

不要用脚本直接覆盖 Artifact 内的 FAISS 或 metadata 文件；任何修改都应产生新的 Pack 版本和
Artifact hash。

## 撤销某个来源

```bash
persona pack derive packs/private/my-pack \
  --exclude-source "licensed/export-a.jsonl" \
  --output packs/private/my-pack-1.1.0 \
  --version 1.1.0
persona pack build packs/private/my-pack-1.1.0
persona pack promote my-pack 1.1.0
persona pack eval packs/private/my-pack-1.1.0
```

确认新版本后仍保留旧 Artifact 以支持审计与回滚。如果来源撤销意味着旧副本也必须销毁，应按
你的授权协议处理本地备份、构建缓存、部署卷和 Git 历史；这超出运行时 `rollback` 的职责。
