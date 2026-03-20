<template>
  <div class="relative w-full h-screen font-sans overflow-hidden select-none bg-slate-900">

    <div class="absolute inset-0 bg-[url('/bg_room.png')] bg-cover bg-center bg-no-repeat opacity-90 z-0"></div>

    <div class="absolute bottom-[12vh] left-1/2 -translate-x-1/2 w-full max-w-4xl flex justify-center pointer-events-none z-10">
      <img
        src="/nene_sprite.png"
        alt="Ayachi Nene"
        class="h-[75vh] object-contain drop-shadow-[0_15px_35px_rgba(0,0,0,0.6)] transition-all duration-700 ease-in-out"
        style="image-rendering: -webkit-optimize-contrast; image-rendering: crisp-edges;"
      />
    </div>

    <div class="absolute bottom-6 left-1/2 -translate-x-1/2 w-[95%] max-w-6xl h-[35vh] flex flex-col bg-slate-900/65 backdrop-blur-xl border-t border-white/10 rounded-2xl shadow-[0_0_50px_rgba(0,0,0,0.6)] z-20">

      <!-- Name tag + clear button -->
      <div class="absolute -top-5 left-0 right-0 flex items-end justify-between px-4 pointer-events-none z-30">
        <div class="bg-indigo-600/90 backdrop-blur-md text-white px-8 py-2 rounded-t-xl rounded-br-2xl shadow-[0_5px_15px_rgba(0,0,0,0.3)] border border-white/20 border-b-0 tracking-[0.2em] text-xl font-bold pointer-events-auto">
          绫地宁宁
        </div>
        <button
          @click="clearSession"
          title="清空对话记忆"
          class="mb-1 text-xs text-slate-400 hover:text-slate-200 transition-colors duration-200 pointer-events-auto"
        >
          清空对话
        </button>
      </div>

      <!-- Message list -->
      <div
        class="flex-1 overflow-y-auto p-8 pt-10 scroll-smooth flex flex-col gap-6"
        ref="chatContainer"
      >
        <div
          v-for="(msg, index) in messages"
          :key="index"
          class="w-full flex flex-col"
          :class="msg.role === 'user' ? 'items-end' : 'items-start'"
        >
          <div
            v-if="msg.role === 'user'"
            class="max-w-[60%] bg-indigo-500/30 backdrop-blur-sm text-indigo-50 px-5 py-3 rounded-2xl rounded-tr-sm shadow-inner border border-indigo-400/20 text-md tracking-wide"
          >
            {{ msg.content }}
          </div>

          <div
            v-else
            class="max-w-[85%] text-white text-lg leading-relaxed tracking-wider font-medium mt-2"
            :class="{ 'animate-pulse text-indigo-300': msg.streaming }"
            style="text-shadow: 1px 2px 4px rgba(0,0,0,0.9);"
          >
            {{ msg.content }}<span v-if="msg.streaming" class="inline-block w-1 h-4 ml-1 bg-indigo-300 animate-pulse align-middle"></span>
          </div>
        </div>
      </div>

      <!-- Input bar -->
      <div class="p-4 bg-slate-950/40 border-t border-white/5 rounded-b-2xl">
        <form @submit.prevent="sendMessage" class="flex gap-4 items-center max-w-4xl mx-auto">
          <input
            v-model="userInput"
            type="text"
            placeholder="回应她..."
            class="flex-1 bg-white/5 border border-white/10 focus:outline-none focus:border-indigo-400/50 focus:bg-white/10 rounded-full px-6 py-3 text-gray-200 placeholder-gray-500 transition-all duration-300 tracking-wider"
            :disabled="isStreaming"
          />
          <button
            type="submit"
            :disabled="!userInput.trim() || isStreaming"
            class="bg-indigo-600/80 hover:bg-indigo-500 disabled:bg-slate-700 disabled:text-gray-400 text-white rounded-full px-8 py-3 font-bold transition-all duration-200 active:scale-95 tracking-widest border border-white/10 hover:shadow-[0_0_15px_rgba(99,102,241,0.5)]"
          >
            SEND
          </button>
        </form>
      </div>

    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted } from 'vue';

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
const userInput  = ref('');
const isStreaming = ref(false);
const messages   = ref([
  { role: 'assistant', content: '保科君，今天想聊些什么呢？', streaming: false },
]);
const chatContainer = ref(null);

// Session ID – persisted in localStorage so memory survives page reloads.
const sessionId = ref(null);

// Dev:  Vite proxy forwards /v1/* → http://127.0.0.1:8000
// Prod: same origin (FastAPI serves both frontend and API)
const STREAM_URL  = '/v1/chat/stream';
const SESSION_KEY = 'nenebot_session_id';

onMounted(() => {
  sessionId.value = localStorage.getItem(SESSION_KEY) || null;
});

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
const scrollToBottom = async () => {
  await nextTick();
  if (chatContainer.value) {
    chatContainer.value.scrollTop = chatContainer.value.scrollHeight;
  }
};

function clearSession() {
  sessionId.value = null;
  localStorage.removeItem(SESSION_KEY);
  messages.value = [
    { role: 'assistant', content: '保科君，今天想聊些什么呢？', streaming: false },
  ];
}

// ---------------------------------------------------------------------------
// SSE streaming chat
// ---------------------------------------------------------------------------
const sendMessage = async () => {
  const text = userInput.value.trim();
  if (!text || isStreaming.value) return;

  messages.value.push({ role: 'user', content: text, streaming: false });
  userInput.value = '';
  isStreaming.value = true;
  await scrollToBottom();

  // Placeholder message that we'll stream into
  messages.value.push({ role: 'assistant', content: '', streaming: true });
  const assistantIdx = messages.value.length - 1;

  try {
    const response = await fetch(STREAM_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: text, session_id: sessionId.value, top_k: 3 }),
    });

    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const reader  = response.body.getReader();
    const decoder = new TextDecoder();
    let   buffer  = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // SSE events are separated by double newlines
      const events = buffer.split('\n\n');
      buffer = events.pop(); // keep incomplete tail for next chunk

      for (const event of events) {
        const line = event.trim();
        if (!line.startsWith('data: ')) continue;
        try {
          const data = JSON.parse(line.slice(6));

          if (data.type === 'meta') {
            // Server confirmed (or assigned) the session ID
            if (data.session_id) {
              sessionId.value = data.session_id;
              localStorage.setItem(SESSION_KEY, data.session_id);
            }
          } else if (data.type === 'chunk') {
            messages.value[assistantIdx].content += data.content;
            await scrollToBottom();
          } else if (data.type === 'done') {
            messages.value[assistantIdx].streaming = false;
          }
        } catch (_) { /* malformed JSON – ignore */ }
      }
    }
  } catch (err) {
    console.error('Stream error:', err);
    messages.value[assistantIdx].content = '（大脑连接断开了，保科君能检查一下服务器吗……）';
  } finally {
    messages.value[assistantIdx].streaming = false;
    isStreaming.value = false;
    await scrollToBottom();
  }
};
</script>
