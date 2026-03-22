<template>
  <div class="min-h-screen bg-[radial-gradient(circle_at_top,#1f2937,transparent_45%),linear-gradient(135deg,#07111f,#111827_55%,#0f172a)] text-slate-100">
    <div class="mx-auto flex max-w-7xl flex-col gap-6 px-4 py-8 sm:px-6 lg:px-8">
      <header class="rounded-[28px] border border-cyan-400/15 bg-slate-950/55 p-6 shadow-[0_20px_80px_rgba(0,0,0,0.45)] backdrop-blur-xl">
        <div class="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p class="text-xs uppercase tracking-[0.5em] text-cyan-300/70">Admin Console</p>
            <h1 class="mt-3 text-3xl font-semibold tracking-[0.08em] text-white">NeneBot Operations Board</h1>
            <p class="mt-3 max-w-3xl text-sm leading-7 text-slate-300">
              只读后台 MVP。先把运行状态、模型配置、会话后端、鉴权身份和指标摘要集中到一个页面里。
            </p>
          </div>
          <div class="flex flex-wrap gap-3 text-xs">
            <span class="rounded-full border border-emerald-400/25 bg-emerald-500/10 px-4 py-2 tracking-[0.2em] text-emerald-200">
              ENV {{ overview.service?.environment || '--' }}
            </span>
            <span class="rounded-full border border-sky-400/25 bg-sky-500/10 px-4 py-2 tracking-[0.2em] text-sky-200">
              VERSION {{ overview.service?.version || '--' }}
            </span>
          </div>
        </div>
      </header>

      <div v-if="error" class="rounded-3xl border border-rose-500/30 bg-rose-500/10 px-5 py-4 text-sm text-rose-100">
        {{ error }}
      </div>

      <section class="grid gap-6 lg:grid-cols-[1.25fr_0.75fr]">
        <article class="rounded-[28px] border border-white/8 bg-white/5 p-6 shadow-[0_18px_60px_rgba(0,0,0,0.35)] backdrop-blur-xl">
          <div class="flex items-center justify-between gap-4">
            <div>
              <p class="text-xs uppercase tracking-[0.4em] text-slate-400">System Health</p>
              <h2 class="mt-2 text-xl font-semibold text-white">Service Overview</h2>
            </div>
            <button
              @click="loadDashboard"
              class="rounded-full border border-cyan-400/25 bg-cyan-400/10 px-4 py-2 text-xs tracking-[0.25em] text-cyan-100 transition hover:bg-cyan-400/20"
            >
              REFRESH
            </button>
          </div>

          <div class="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <div class="rounded-2xl border border-white/8 bg-slate-900/55 p-4">
              <p class="text-xs uppercase tracking-[0.35em] text-slate-500">Status</p>
              <p class="mt-3 text-2xl font-semibold" :class="statusClass(overview.health?.status)">
                {{ overview.health?.status || '--' }}
              </p>
            </div>
            <div class="rounded-2xl border border-white/8 bg-slate-900/55 p-4">
              <p class="text-xs uppercase tracking-[0.35em] text-slate-500">LLM</p>
              <p class="mt-3 text-lg font-semibold text-white">{{ overview.llm?.provider || '--' }}</p>
              <p class="mt-1 text-sm text-slate-400">{{ overview.llm?.model || '--' }}</p>
            </div>
            <div class="rounded-2xl border border-white/8 bg-slate-900/55 p-4">
              <p class="text-xs uppercase tracking-[0.35em] text-slate-500">Vector Index</p>
              <p class="mt-3 text-2xl font-semibold text-white">{{ overview.retrieval?.index_vectors ?? '--' }}</p>
              <p class="mt-1 text-sm text-slate-400">records {{ overview.retrieval?.metadata_records ?? '--' }}</p>
            </div>
            <div class="rounded-2xl border border-white/8 bg-slate-900/55 p-4">
              <p class="text-xs uppercase tracking-[0.35em] text-slate-500">Auth Identities</p>
              <p class="mt-3 text-2xl font-semibold text-white">{{ overview.auth?.identities?.length ?? 0 }}</p>
              <p class="mt-1 text-sm text-slate-400">scoped access tokens</p>
            </div>
          </div>

          <div class="mt-6 grid gap-4 xl:grid-cols-2">
            <div class="rounded-3xl border border-white/8 bg-slate-950/50 p-5">
              <p class="text-xs uppercase tracking-[0.4em] text-slate-500">Runtime</p>
              <dl class="mt-4 space-y-3 text-sm">
                <div class="flex items-center justify-between gap-4">
                  <dt class="text-slate-400">Request ID</dt>
                  <dd class="font-mono text-cyan-200">{{ overview.service?.request_id || '--' }}</dd>
                </div>
                <div class="flex items-center justify-between gap-4">
                  <dt class="text-slate-400">Session Backend</dt>
                  <dd class="text-white">{{ overview.sessions?.backend || '--' }}</dd>
                </div>
                <div class="flex items-center justify-between gap-4">
                  <dt class="text-slate-400">Threshold</dt>
                  <dd class="text-white">{{ overview.retrieval?.match_threshold ?? '--' }}</dd>
                </div>
                <div class="flex items-center justify-between gap-4">
                  <dt class="text-slate-400">Retries / Timeout</dt>
                  <dd class="text-white">{{ overview.llm?.max_retries ?? '--' }} / {{ overview.llm?.timeout_seconds ?? '--' }}s</dd>
                </div>
              </dl>
            </div>

            <div class="rounded-3xl border border-white/8 bg-slate-950/50 p-5">
              <p class="text-xs uppercase tracking-[0.4em] text-slate-500">Integrations</p>
              <dl class="mt-4 space-y-3 text-sm">
                <div class="flex items-center justify-between gap-4">
                  <dt class="text-slate-400">Metrics</dt>
                  <dd class="text-white">{{ boolLabel(overview.integrations?.metrics_enabled) }}</dd>
                </div>
                <div class="flex items-center justify-between gap-4">
                  <dt class="text-slate-400">Tracing</dt>
                  <dd class="text-white">{{ boolLabel(overview.integrations?.tracing_enabled) }} / {{ overview.integrations?.tracing_exporter || '--' }}</dd>
                </div>
                <div class="flex items-center justify-between gap-4">
                  <dt class="text-slate-400">Telegram</dt>
                  <dd class="text-white">{{ boolLabel(overview.integrations?.telegram_enabled) }} / {{ overview.integrations?.telegram_mode || '--' }}</dd>
                </div>
              </dl>
            </div>
          </div>
        </article>

        <article class="rounded-[28px] border border-white/8 bg-white/5 p-6 shadow-[0_18px_60px_rgba(0,0,0,0.35)] backdrop-blur-xl">
          <p class="text-xs uppercase tracking-[0.4em] text-slate-400">Access Control</p>
          <h2 class="mt-2 text-xl font-semibold text-white">Token Identity Summary</h2>
          <div class="mt-5 space-y-3">
            <div
              v-for="identity in overview.auth?.identities || []"
              :key="identity.name"
              class="rounded-2xl border border-white/8 bg-slate-950/45 p-4"
            >
              <div class="flex items-center justify-between gap-3">
                <p class="font-semibold text-white">{{ identity.name }}</p>
                <div class="flex flex-wrap justify-end gap-2">
                  <span
                    v-for="scope in identity.scopes"
                    :key="scope"
                    class="rounded-full border border-fuchsia-400/20 bg-fuchsia-500/10 px-3 py-1 text-[11px] uppercase tracking-[0.25em] text-fuchsia-200"
                  >
                    {{ scope }}
                  </span>
                </div>
              </div>
            </div>
            <p v-if="!(overview.auth?.identities || []).length" class="text-sm text-slate-400">
              No configured identities.
            </p>
          </div>
        </article>
      </section>

      <section class="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
        <article class="rounded-[28px] border border-white/8 bg-white/5 p-6 shadow-[0_18px_60px_rgba(0,0,0,0.35)] backdrop-blur-xl">
          <p class="text-xs uppercase tracking-[0.4em] text-slate-400">Metrics Snapshot</p>
          <h2 class="mt-2 text-xl font-semibold text-white">Prometheus Preview</h2>
          <p class="mt-2 text-sm text-slate-400">
            当前采集到的 metrics series 数量：{{ metrics.metric_series_count ?? 0 }}
          </p>
          <div class="mt-5 max-h-[420px] overflow-auto rounded-3xl border border-white/8 bg-slate-950/60 p-4 font-mono text-xs leading-6 text-emerald-200">
            <div v-for="line in metrics.preview || []" :key="line">{{ line }}</div>
          </div>
        </article>

        <article class="rounded-[28px] border border-white/8 bg-white/5 p-6 shadow-[0_18px_60px_rgba(0,0,0,0.35)] backdrop-blur-xl">
          <p class="text-xs uppercase tracking-[0.4em] text-slate-400">Verification</p>
          <h2 class="mt-2 text-xl font-semibold text-white">How To Use This MVP</h2>
          <div class="mt-5 space-y-4 text-sm leading-7 text-slate-300">
            <p>1. 先使用具备 <span class="font-mono text-cyan-200">ops</span> scope 的 token 访问 <span class="font-mono text-cyan-200">/admin</span>。</p>
            <p>2. 页面加载成功后，确认 health、LLM、vector index、auth identities 都能正常显示。</p>
            <p>3. 再对照 <span class="font-mono text-cyan-200">/metrics</span> 与本页 metrics preview，确认采集链路通畅。</p>
            <p>4. 这一版是只读后台，下一步最自然的扩展点就是 token 管理、知识库导入和会话浏览。</p>
          </div>
        </article>
      </section>

      <section class="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
        <article class="rounded-[28px] border border-white/8 bg-white/5 p-6 shadow-[0_18px_60px_rgba(0,0,0,0.35)] backdrop-blur-xl">
          <div class="flex items-center justify-between gap-4">
            <div>
              <p class="text-xs uppercase tracking-[0.4em] text-slate-400">Knowledge Base</p>
              <h2 class="mt-2 text-xl font-semibold text-white">Dataset Overview</h2>
            </div>
            <button
              @click="loadKnowledge"
              class="rounded-full border border-amber-400/25 bg-amber-400/10 px-4 py-2 text-xs tracking-[0.25em] text-amber-100 transition hover:bg-amber-400/20"
            >
              RELOAD
            </button>
          </div>

          <div class="mt-6 grid gap-4 sm:grid-cols-2">
            <div class="rounded-2xl border border-white/8 bg-slate-900/55 p-4">
              <p class="text-xs uppercase tracking-[0.35em] text-slate-500">Dataset Lines</p>
              <p class="mt-3 text-2xl font-semibold text-white">{{ knowledge.dataset?.line_count ?? '--' }}</p>
            </div>
            <div class="rounded-2xl border border-white/8 bg-slate-900/55 p-4">
              <p class="text-xs uppercase tracking-[0.35em] text-slate-500">Index Vectors</p>
              <p class="mt-3 text-2xl font-semibold text-white">{{ knowledge.vector_store?.index_vectors ?? '--' }}</p>
            </div>
          </div>

          <div class="mt-5 rounded-3xl border border-white/8 bg-slate-950/50 p-5">
            <p class="text-xs uppercase tracking-[0.35em] text-slate-500">Dataset Path</p>
            <p class="mt-3 break-all font-mono text-sm text-cyan-200">{{ knowledge.dataset?.path || '--' }}</p>
            <p class="mt-3 text-sm text-slate-400">Last Modified: {{ knowledge.dataset?.last_modified || '--' }}</p>
          </div>

          <div class="mt-5 rounded-3xl border border-white/8 bg-slate-950/50 p-5">
            <p class="text-xs uppercase tracking-[0.35em] text-slate-500">Preview</p>
            <div class="mt-4 space-y-3">
              <div
                v-for="(item, index) in knowledge.dataset?.preview || []"
                :key="index"
                class="rounded-2xl border border-white/8 bg-slate-900/50 p-4"
              >
                <p class="text-xs uppercase tracking-[0.25em] text-slate-500">User</p>
                <p class="mt-2 text-sm text-white">{{ item.user || '—' }}</p>
                <p class="mt-3 text-xs uppercase tracking-[0.25em] text-slate-500">Assistant</p>
                <p class="mt-2 text-sm text-slate-300">{{ item.assistant || '—' }}</p>
              </div>
            </div>
          </div>
        </article>

        <article class="rounded-[28px] border border-white/8 bg-white/5 p-6 shadow-[0_18px_60px_rgba(0,0,0,0.35)] backdrop-blur-xl">
          <p class="text-xs uppercase tracking-[0.4em] text-slate-400">Knowledge Operations</p>
          <h2 class="mt-2 text-xl font-semibold text-white">Import And Rebuild</h2>
          <p class="mt-2 text-sm leading-7 text-slate-400">
            这里做的是发布前可用的最小知识库运维：预校验 JSONL、导入数据集、重建向量索引。
          </p>

          <div v-if="knowledgeError" class="mt-5 rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">
            {{ knowledgeError }}
          </div>

          <div v-if="knowledgeSuccess" class="mt-5 rounded-2xl border border-emerald-500/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-100">
            {{ knowledgeSuccess }}
          </div>

          <label class="mt-5 block text-xs uppercase tracking-[0.35em] text-slate-500">JSONL Content</label>
          <textarea
            v-model="knowledgeInput"
            rows="12"
            placeholder='{"messages":[{"role":"system","content":"..."},{"role":"user","content":"你好"},{"role":"assistant","content":"你好呀"}]}'
            class="mt-3 w-full rounded-3xl border border-white/8 bg-slate-950/65 px-4 py-4 font-mono text-sm leading-6 text-slate-100 outline-none transition focus:border-cyan-400/35"
          ></textarea>

          <div class="mt-5 flex flex-wrap gap-3">
            <button
              @click="validateKnowledge"
              :disabled="isKnowledgeBusy || !knowledgeInput.trim()"
              class="rounded-full border border-emerald-400/25 bg-emerald-400/10 px-5 py-3 text-xs tracking-[0.25em] text-emerald-100 transition hover:bg-emerald-400/20 disabled:cursor-not-allowed disabled:opacity-50"
            >
              VALIDATE
            </button>
            <button
              @click="importKnowledge(true)"
              :disabled="isKnowledgeBusy || !knowledgeInput.trim()"
              class="rounded-full border border-cyan-400/25 bg-cyan-400/10 px-5 py-3 text-xs tracking-[0.25em] text-cyan-100 transition hover:bg-cyan-400/20 disabled:cursor-not-allowed disabled:opacity-50"
            >
              IMPORT + REBUILD
            </button>
            <button
              @click="importKnowledge(false)"
              :disabled="isKnowledgeBusy || !knowledgeInput.trim()"
              class="rounded-full border border-white/10 bg-white/5 px-5 py-3 text-xs tracking-[0.25em] text-slate-100 transition hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50"
            >
              IMPORT ONLY
            </button>
            <button
              @click="rebuildKnowledge"
              :disabled="isKnowledgeBusy"
              class="rounded-full border border-amber-400/25 bg-amber-400/10 px-5 py-3 text-xs tracking-[0.25em] text-amber-100 transition hover:bg-amber-400/20 disabled:cursor-not-allowed disabled:opacity-50"
            >
              REBUILD INDEX
            </button>
          </div>
          <p v-if="isKnowledgeBusy" class="mt-4 text-xs uppercase tracking-[0.25em] text-amber-200">
            knowledge operation in progress...
          </p>
        </article>
      </section>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'

const overview = ref({})
const metrics = ref({ preview: [], metric_series_count: 0 })
const knowledge = ref({ dataset: { preview: [] }, vector_store: {} })
const error = ref('')
const knowledgeError = ref('')
const knowledgeSuccess = ref('')
const knowledgeInput = ref('')
const isKnowledgeBusy = ref(false)

function getAdminHeaders() {
  const token = window.localStorage.getItem('nenebot_admin_token') || ''
  return token ? { Authorization: `Bearer ${token}` } : {}
}

function boolLabel(value) {
  return value ? 'enabled' : 'disabled'
}

function statusClass(status) {
  if (status === 'ok') return 'text-emerald-300'
  if (status === 'degraded') return 'text-amber-300'
  return 'text-slate-300'
}

async function loadDashboard() {
  error.value = ''
  try {
    const [overviewRes, metricsRes, knowledgeRes] = await Promise.all([
      fetch('/admin/api/overview', { headers: getAdminHeaders() }),
      fetch('/admin/api/metrics/summary', { headers: getAdminHeaders() }),
      fetch('/admin/api/knowledge/overview', { headers: getAdminHeaders() }),
    ])

    if (!overviewRes.ok) {
      throw new Error(`overview HTTP ${overviewRes.status}`)
    }
    if (!metricsRes.ok) {
      throw new Error(`metrics HTTP ${metricsRes.status}`)
    }
    if (!knowledgeRes.ok) {
      throw new Error(`knowledge HTTP ${knowledgeRes.status}`)
    }

    overview.value = await overviewRes.json()
    metrics.value = await metricsRes.json()
    knowledge.value = await knowledgeRes.json()
  } catch (err) {
    console.error(err)
    error.value = '后台数据加载失败。请确认你已在浏览器 localStorage 中写入 nenebot_admin_token，且该 token 拥有 ops scope。'
  }
}

async function loadKnowledge() {
  knowledgeError.value = ''
  knowledgeSuccess.value = ''
  try {
    const response = await fetch('/admin/api/knowledge/overview', { headers: getAdminHeaders() })
    if (!response.ok) throw new Error(`knowledge HTTP ${response.status}`)
    knowledge.value = await response.json()
  } catch (err) {
    console.error(err)
    knowledgeError.value = '知识库概览加载失败。'
  }
}

async function importKnowledge(rebuild) {
  knowledgeError.value = ''
  knowledgeSuccess.value = ''
  isKnowledgeBusy.value = true
  try {
    const response = await fetch('/admin/api/knowledge/import', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAdminHeaders(),
      },
      body: JSON.stringify({ content: knowledgeInput.value, rebuild, dry_run: false }),
    })
    const payload = await response.json()
    if (!response.ok) {
      throw new Error(payload?.detail || `import HTTP ${response.status}`)
    }
    knowledge.value = {
      dataset: payload.dataset,
      vector_store: payload.vector_store || knowledge.value.vector_store,
    }
    knowledgeSuccess.value = rebuild ? '数据集已导入并完成索引重建。' : '数据集已导入。'
  } catch (err) {
    console.error(err)
    knowledgeError.value = `导入失败：${err.message || err}`
  } finally {
    isKnowledgeBusy.value = false
  }
}

async function validateKnowledge() {
  knowledgeError.value = ''
  knowledgeSuccess.value = ''
  isKnowledgeBusy.value = true
  try {
    const response = await fetch('/admin/api/knowledge/import', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAdminHeaders(),
      },
      body: JSON.stringify({ content: knowledgeInput.value, rebuild: false, dry_run: true }),
    })
    const payload = await response.json()
    if (!response.ok) {
      throw new Error(payload?.detail || `validate HTTP ${response.status}`)
    }
    knowledgeSuccess.value = 'JSONL 结构校验通过，尚未写入磁盘。'
  } catch (err) {
    console.error(err)
    knowledgeError.value = `预校验失败：${err.message || err}`
  } finally {
    isKnowledgeBusy.value = false
  }
}

async function rebuildKnowledge() {
  knowledgeError.value = ''
  knowledgeSuccess.value = ''
  isKnowledgeBusy.value = true
  try {
    const response = await fetch('/admin/api/knowledge/rebuild', {
      method: 'POST',
      headers: getAdminHeaders(),
    })
    const payload = await response.json()
    if (!response.ok) {
      throw new Error(payload?.detail || `rebuild HTTP ${response.status}`)
    }
    knowledge.value = {
      dataset: payload.dataset,
      vector_store: payload.vector_store,
    }
    knowledgeSuccess.value = '索引重建完成。'
  } catch (err) {
    console.error(err)
    knowledgeError.value = `重建失败：${err.message || err}`
  } finally {
    isKnowledgeBusy.value = false
  }
}

onMounted(async () => {
  if (!window.localStorage.getItem('nenebot_admin_token')) {
    const token = window.prompt('请输入具备 ops scope 的后台 token') || ''
    if (token) {
      window.localStorage.setItem('nenebot_admin_token', token)
    }
  }
  await loadDashboard()
})
</script>
