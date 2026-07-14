<template>
  <main class="min-h-screen bg-[radial-gradient(circle_at_top_left,#17304a,transparent_38%),linear-gradient(135deg,#07111f,#111827_60%,#0f172a)] text-slate-100">
    <div class="mx-auto flex max-w-7xl flex-col gap-6 px-4 py-8 sm:px-7">
      <header class="rounded-[30px] border border-cyan-400/15 bg-slate-950/55 p-7 shadow-2xl backdrop-blur-xl">
        <div class="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p class="text-xs uppercase tracking-[0.5em] text-cyan-300/70">Persona Studio</p>
            <h1 class="mt-3 text-3xl font-semibold tracking-wide">Artifact Operations</h1>
            <p class="mt-3 max-w-3xl text-sm leading-7 text-slate-400">
              只读运行面板。内容变更只能通过离线 Character Pack 构建、评测、发布与回滚流程进入运行时。
            </p>
          </div>
          <button class="rounded-full border border-cyan-400/25 bg-cyan-400/10 px-5 py-3 text-xs tracking-[0.25em] text-cyan-100 hover:bg-cyan-400/20" @click="loadDashboard">
            REFRESH
          </button>
        </div>
      </header>

      <div v-if="error" class="rounded-2xl border border-rose-500/25 bg-rose-500/10 px-5 py-4 text-sm text-rose-100">{{ error }}</div>

      <section class="grid gap-5 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Health" :value="overview.health?.status || '--'" />
        <StatCard label="Active Pack" :value="overview.pack?.pack_id || '--'" :detail="overview.pack?.version" />
        <StatCard label="Artifact Records" :value="knowledge.vector_store?.index_vectors ?? '--'" />
        <StatCard label="Installed Versions" :value="knowledge.versions?.length ?? 0" />
      </section>

      <section class="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
        <article class="rounded-[28px] border border-white/8 bg-white/5 p-6 shadow-xl backdrop-blur-xl">
          <p class="text-xs uppercase tracking-[0.4em] text-slate-500">Active immutable artifact</p>
          <h2 class="mt-2 text-xl font-semibold">{{ knowledge.pack?.display_name || 'Unavailable' }}</h2>
          <dl class="mt-6 grid gap-4 text-sm sm:grid-cols-2">
            <InfoRow label="Pack ID" :value="knowledge.pack?.pack_id" />
            <InfoRow label="Pack Version" :value="knowledge.pack?.version" />
            <InfoRow label="Artifact Version" :value="knowledge.pack?.artifact?.artifact_version" />
            <InfoRow label="Embedding" :value="knowledge.pack?.artifact?.embedding_model" />
            <InfoRow label="Artifact Hash" :value="shortHash(knowledge.pack?.artifact?.artifact_hash)" mono />
            <InfoRow label="Content Hash" :value="shortHash(knowledge.pack?.content_hash)" mono />
            <InfoRow label="Creator" :value="knowledge.pack?.provenance?.creator" />
            <InfoRow label="License" :value="knowledge.pack?.provenance?.license" />
          </dl>
          <div class="mt-5 rounded-2xl border border-white/8 bg-black/15 p-4 text-xs leading-6 text-slate-400">
            <p class="uppercase tracking-[0.3em] text-slate-500">Source</p>
            <p class="mt-2 break-all text-slate-200">{{ knowledge.pack?.provenance?.source || '--' }}</p>
          </div>
        </article>

        <article class="rounded-[28px] border border-white/8 bg-white/5 p-6 shadow-xl backdrop-blur-xl">
          <p class="text-xs uppercase tracking-[0.4em] text-slate-500">Offline-only operations</p>
          <h2 class="mt-2 text-xl font-semibold">Release commands</h2>
          <p class="mt-3 text-sm leading-7 text-slate-400">
            此服务不接受在线知识写入。命令在可信构建环境执行，运行时只读取已激活 Artifact。
          </p>
          <div class="mt-5 space-y-3">
            <div v-for="(command, name) in knowledge.operations?.commands || {}" :key="name" class="rounded-2xl border border-white/8 bg-slate-950/60 p-4">
              <p class="text-[10px] uppercase tracking-[0.3em] text-cyan-300/65">{{ name }}</p>
              <code class="mt-2 block break-all text-xs leading-6 text-slate-200">{{ command }}</code>
            </div>
          </div>
        </article>
      </section>

      <section class="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <article class="rounded-[28px] border border-white/8 bg-white/5 p-6 shadow-xl backdrop-blur-xl">
          <p class="text-xs uppercase tracking-[0.4em] text-slate-500">Installed history</p>
          <h2 class="mt-2 text-xl font-semibold">Traceable versions</h2>
          <div class="mt-5 overflow-x-auto">
            <table class="w-full min-w-[680px] text-left text-sm">
              <thead class="text-xs uppercase tracking-[0.2em] text-slate-500">
                <tr><th class="pb-3">Version</th><th class="pb-3">Created</th><th class="pb-3">Records</th><th class="pb-3">Artifact hash</th></tr>
              </thead>
              <tbody class="divide-y divide-white/8">
                <tr v-for="item in knowledge.versions || []" :key="item.artifact_hash">
                  <td class="py-4 text-white">{{ item.artifact_version }}</td>
                  <td class="py-4 text-slate-400">{{ item.created_at }}</td>
                  <td class="py-4 text-slate-300">{{ item.record_count }}</td>
                  <td class="py-4 font-mono text-xs text-cyan-200">{{ shortHash(item.artifact_hash) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </article>

        <article class="rounded-[28px] border border-white/8 bg-white/5 p-6 shadow-xl backdrop-blur-xl">
          <p class="text-xs uppercase tracking-[0.4em] text-slate-500">Runtime diagnostics</p>
          <h2 class="mt-2 text-xl font-semibold">Service & metrics</h2>
          <dl class="mt-5 space-y-3 text-sm">
            <InfoRow label="Environment" :value="overview.service?.environment" />
            <InfoRow label="API Version" :value="overview.service?.version" />
            <InfoRow label="LLM" :value="`${overview.llm?.provider || '--'} / ${overview.llm?.model || '--'}`" />
            <InfoRow label="Sessions" :value="overview.sessions?.backend" />
            <InfoRow label="Metric series" :value="metrics.metric_series_count" />
          </dl>
          <div class="mt-5 max-h-56 overflow-auto rounded-2xl border border-white/8 bg-slate-950/60 p-4 font-mono text-[11px] leading-6 text-emerald-200">
            <div v-for="line in metrics.preview || []" :key="line">{{ line }}</div>
          </div>
        </article>
      </section>
    </div>
  </main>
</template>

<script setup>
import { defineComponent, h, onMounted, ref } from 'vue'

const TOKEN_KEY = 'persona_studio_admin_token'
const overview = ref({})
const metrics = ref({ preview: [], metric_series_count: 0 })
const knowledge = ref({ versions: [], vector_store: {}, operations: { commands: {} } })
const error = ref('')

const StatCard = defineComponent({
  props: { label: String, value: [String, Number], detail: String },
  setup(props) {
    return () => h('article', { class: 'rounded-[24px] border border-white/8 bg-white/5 p-5 shadow-xl backdrop-blur-xl' }, [
      h('p', { class: 'text-[10px] uppercase tracking-[0.35em] text-slate-500' }, props.label),
      h('p', { class: 'mt-3 truncate text-2xl font-semibold text-white' }, String(props.value ?? '--')),
      props.detail ? h('p', { class: 'mt-1 text-xs text-cyan-200' }, props.detail) : null,
    ])
  },
})

const InfoRow = defineComponent({
  props: { label: String, value: [String, Number], mono: Boolean },
  setup(props) {
    return () => h('div', { class: 'rounded-2xl border border-white/8 bg-slate-950/45 p-4' }, [
      h('dt', { class: 'text-[10px] uppercase tracking-[0.28em] text-slate-500' }, props.label),
      h('dd', { class: `mt-2 break-all text-slate-100 ${props.mono ? 'font-mono text-xs text-cyan-200' : ''}` }, String(props.value ?? '--')),
    ])
  },
})

function headers() {
  const token = localStorage.getItem(TOKEN_KEY) || ''
  return token ? { Authorization: `Bearer ${token}` } : {}
}

function shortHash(value) {
  return value ? `${value.slice(0, 12)}…${value.slice(-8)}` : '--'
}

async function loadDashboard() {
  error.value = ''
  try {
    const responses = await Promise.all([
      fetch('/admin/api/overview', { headers: headers() }),
      fetch('/admin/api/metrics/summary', { headers: headers() }),
      fetch('/admin/api/knowledge/overview', { headers: headers() }),
    ])
    const failed = responses.find((response) => !response.ok)
    if (failed) throw new Error(`HTTP ${failed.status}`)
    overview.value = await responses[0].json()
    metrics.value = await responses[1].json()
    knowledge.value = await responses[2].json()
  } catch (reason) {
    console.error(reason)
    error.value = '运行面板加载失败。请确认本地保存了具备 ops scope 的访问令牌。'
  }
}

onMounted(async () => {
  if (!localStorage.getItem(TOKEN_KEY)) {
    const token = window.prompt('请输入具备 ops scope 的后台 token') || ''
    if (token) localStorage.setItem(TOKEN_KEY, token)
  }
  await loadDashboard()
})
</script>
