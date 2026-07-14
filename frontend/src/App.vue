<template>
  <main
    class="min-h-screen overflow-hidden text-slate-100"
    :style="themeVariables"
  >
    <div class="fixed inset-0 -z-20 bg-[var(--pack-background)]"></div>
    <div class="fixed inset-0 -z-10 opacity-80 [background:radial-gradient(circle_at_18%_18%,color-mix(in_srgb,var(--pack-primary)_28%,transparent),transparent_34%),radial-gradient(circle_at_82%_78%,color-mix(in_srgb,var(--pack-accent)_18%,transparent),transparent_32%)]"></div>

    <div class="mx-auto grid min-h-screen max-w-7xl gap-6 px-4 py-5 md:px-7 lg:grid-cols-[320px_1fr] lg:py-8">
      <aside class="relative hidden overflow-hidden rounded-[32px] border border-white/10 bg-black/20 p-7 shadow-2xl backdrop-blur-xl lg:flex lg:flex-col">
        <div class="absolute -right-16 -top-16 h-48 w-48 rounded-full border border-white/10"></div>
        <div class="absolute -right-6 top-8 h-24 w-24 rounded-full border border-white/10"></div>

        <p class="text-[11px] uppercase tracking-[0.42em] text-white/45">Active character</p>
        <div class="mt-12 grid h-36 w-36 place-items-center rounded-[42px] border border-white/15 bg-white/10 text-6xl font-semibold shadow-[0_24px_80px_color-mix(in_srgb,var(--pack-primary)_34%,transparent)]">
          {{ character.theme.avatar.text }}
        </div>

        <h1 class="mt-8 text-3xl font-semibold tracking-wide">{{ character.display_name }}</h1>
        <p class="mt-2 font-mono text-xs text-[var(--pack-accent)]">
          {{ character.pack_id }} · {{ character.pack_version }}
        </p>
        <p class="mt-6 text-sm leading-7 text-white/60">
          当前对话只读取已发布的 Character Pack Artifact。引用卡片保留知识记录的来源与授权信息。
        </p>

        <div class="mt-auto rounded-2xl border border-white/10 bg-black/20 p-4 text-xs leading-6 text-white/55">
          <p class="uppercase tracking-[0.28em] text-white/35">Pack rights</p>
          <p class="mt-2 text-white/80">{{ character.provenance.license }}</p>
          <p class="truncate">{{ character.provenance.creator }}</p>
        </div>
      </aside>

      <section class="flex min-h-[calc(100vh-2.5rem)] flex-col overflow-hidden rounded-[32px] border border-white/10 bg-slate-950/55 shadow-2xl backdrop-blur-2xl lg:min-h-0">
        <header class="flex items-center justify-between gap-4 border-b border-white/8 px-5 py-4 sm:px-7">
          <div class="flex min-w-0 items-center gap-3">
            <div class="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-[var(--pack-primary)] text-lg font-semibold text-white lg:hidden">
              {{ character.theme.avatar.text }}
            </div>
            <div class="min-w-0">
              <p class="truncate font-semibold">{{ character.display_name }}</p>
              <p class="truncate text-xs text-white/45">Published Pack · {{ character.pack_version }}</p>
            </div>
          </div>
          <button
            class="rounded-full border border-white/10 px-4 py-2 text-xs tracking-wider text-white/55 transition hover:border-white/25 hover:text-white"
            @click="clearSession"
          >
            新对话
          </button>
        </header>

        <div ref="chatContainer" class="flex-1 space-y-7 overflow-y-auto px-5 py-7 sm:px-8">
          <article
            v-for="(message, index) in messages"
            :key="index"
            class="flex"
            :class="message.role === 'user' ? 'justify-end' : 'justify-start'"
          >
            <div class="max-w-[92%] sm:max-w-[78%]">
              <div
                class="rounded-3xl px-5 py-4 text-sm leading-7 sm:text-[15px]"
                :class="message.role === 'user'
                  ? 'rounded-br-md bg-[var(--pack-primary)] text-white'
                  : 'rounded-bl-md border border-white/8 bg-white/6 text-slate-100'"
              >
                {{ message.content }}
                <span v-if="message.streaming" class="ml-1 inline-block h-4 w-1 animate-pulse bg-[var(--pack-accent)] align-middle"></span>
              </div>

              <details
                v-if="message.references?.length"
                class="mt-3 rounded-2xl border border-white/8 bg-black/15 px-4 py-3 text-xs text-white/55"
              >
                <summary class="cursor-pointer select-none text-[var(--pack-accent)]">
                  {{ message.references.length }} 条可追溯引用
                </summary>
                <div class="mt-3 space-y-3">
                  <div
                    v-for="reference in message.references"
                    :key="reference.record_id || reference.content_sha256"
                    class="rounded-xl border border-white/8 bg-white/5 p-3 leading-5"
                  >
                    <p class="text-white/80">{{ reference.historical_query }}</p>
                    <p class="mt-1">{{ reference.source || 'source unavailable' }}</p>
                    <p class="font-mono text-[10px] text-white/35">
                      {{ reference.record_id }} · {{ reference.license }} · score {{ formatScore(reference.similarity_score) }}
                    </p>
                  </div>
                </div>
              </details>
            </div>
          </article>
        </div>

        <form class="border-t border-white/8 bg-black/15 p-4 sm:p-5" @submit.prevent="sendMessage">
          <div class="mx-auto flex max-w-4xl items-end gap-3 rounded-[26px] border border-white/10 bg-white/5 p-2 pl-5 focus-within:border-white/25">
            <textarea
              v-model="userInput"
              rows="1"
              class="max-h-32 min-h-11 flex-1 resize-none bg-transparent py-3 text-sm leading-5 text-white outline-none placeholder:text-white/30"
              placeholder="写下你想整理的问题……"
              :disabled="isStreaming"
              @keydown.enter.exact.prevent="sendMessage"
            ></textarea>
            <button
              type="submit"
              :disabled="!userInput.trim() || isStreaming"
              class="h-11 rounded-[20px] bg-[var(--pack-primary)] px-6 text-xs font-semibold tracking-[0.18em] text-white transition hover:brightness-110 disabled:cursor-not-allowed disabled:opacity-40"
            >
              SEND
            </button>
          </div>
          <p v-if="requestError" class="mt-3 text-center text-xs text-rose-300">{{ requestError }}</p>
        </form>
      </section>
    </div>
  </main>
</template>

<script setup>
import { computed, nextTick, onMounted, ref } from 'vue'

const DEFAULT_CHARACTER = {
  pack_id: 'mira-demo',
  pack_version: '1.0.0',
  display_name: '米拉 / Mira',
  theme: {
    primary_color: '#7C83FD',
    accent_color: '#5EEAD4',
    background_color: '#111827',
    avatar: { kind: 'initials', text: 'M' },
  },
  provenance: {
    creator: 'Persona Studio contributors',
    source: 'Original demo Pack',
    license: 'CC0-1.0',
    rights: 'owned',
  },
}

const STREAM_URL = '/v1/chat/stream'
const CHARACTER_URL = '/v1/character'
const SESSION_KEY = 'persona_studio_session_id'

const character = ref(DEFAULT_CHARACTER)
const userInput = ref('')
const isStreaming = ref(false)
const requestError = ref('')
const sessionId = ref(null)
const chatContainer = ref(null)
const messages = ref([
  { role: 'assistant', content: '你好，我是米拉。今晚想一起整理什么问题？', streaming: false, references: [] },
])

const themeVariables = computed(() => ({
  '--pack-primary': character.value.theme.primary_color,
  '--pack-accent': character.value.theme.accent_color,
  '--pack-background': character.value.theme.background_color,
}))

async function scrollToBottom() {
  await nextTick()
  if (chatContainer.value) chatContainer.value.scrollTop = chatContainer.value.scrollHeight
}

function formatScore(score) {
  return Number(score || 0).toFixed(2)
}

function clearSession() {
  sessionId.value = null
  localStorage.removeItem(SESSION_KEY)
  requestError.value = ''
  messages.value = [
    {
      role: 'assistant',
      content: `你好，我是${character.value.display_name}。我们从一个新问题开始吧。`,
      streaming: false,
      references: [],
    },
  ]
}

async function loadCharacter() {
  try {
    const response = await fetch(CHARACTER_URL)
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    character.value = await response.json()
    messages.value[0].content = `你好，我是${character.value.display_name}。今晚想一起整理什么问题？`
  } catch (error) {
    console.warn('Unable to load active Character Pack metadata.', error)
  }
}

async function sendMessage() {
  const text = userInput.value.trim()
  if (!text || isStreaming.value) return

  requestError.value = ''
  messages.value.push({ role: 'user', content: text, streaming: false, references: [] })
  userInput.value = ''
  isStreaming.value = true
  messages.value.push({ role: 'assistant', content: '', streaming: true, references: [] })
  const assistantIndex = messages.value.length - 1
  await scrollToBottom()

  try {
    const response = await fetch(STREAM_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: text, session_id: sessionId.value, top_k: 3 }),
    })
    if (!response.ok || !response.body) throw new Error(`HTTP ${response.status}`)

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const events = buffer.split('\n\n')
      buffer = events.pop() || ''
      for (const event of events) {
        const line = event.trim()
        if (!line.startsWith('data: ')) continue
        const data = JSON.parse(line.slice(6))
        if (data.type === 'meta') {
          if (data.session_id) {
            sessionId.value = data.session_id
            localStorage.setItem(SESSION_KEY, data.session_id)
          }
          messages.value[assistantIndex].references = data.references || []
        } else if (data.type === 'chunk') {
          messages.value[assistantIndex].content += data.content
        } else if (data.type === 'error') {
          throw new Error(data.message || 'stream interrupted')
        } else if (data.type === 'done') {
          messages.value[assistantIndex].streaming = false
        }
        await scrollToBottom()
      }
    }
  } catch (error) {
    console.error('Chat stream failed.', error)
    requestError.value = '生成连接中断，请稍后重试。'
    if (!messages.value[assistantIndex].content) {
      messages.value[assistantIndex].content = '这次连接没有完成。请稍后再试一次。'
    }
  } finally {
    messages.value[assistantIndex].streaming = false
    isStreaming.value = false
    await scrollToBottom()
  }
}

onMounted(async () => {
  sessionId.value = localStorage.getItem(SESSION_KEY) || null
  await loadCharacter()
})
</script>
