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
      
      <div class="absolute -top-5 left-10 bg-indigo-600/90 backdrop-blur-md text-white px-8 py-2 rounded-t-xl rounded-br-2xl shadow-[0_5px_15px_rgba(0,0,0,0.3)] border border-white/20 border-b-0 tracking-[0.2em] text-xl font-bold z-30">
        绫地宁宁
      </div>

      <div class="flex-1 overflow-y-auto p-8 pt-10 scroll-smooth flex flex-col gap-6" ref="chatContainer">
        <div 
          v-for="(msg, index) in messages" 
          :key="index"
          class="w-full flex flex-col"
          :class="msg.role === 'user' ? 'items-end' : 'items-start'"
        >
          <div v-if="msg.role === 'user'" class="max-w-[60%] bg-indigo-500/30 backdrop-blur-sm text-indigo-50 px-5 py-3 rounded-2xl rounded-tr-sm shadow-inner border border-indigo-400/20 text-md tracking-wide">
            {{ msg.content }}
          </div>
          
          <div v-else class="max-w-[85%] text-white text-lg leading-relaxed tracking-wider text-shadow-sm font-medium mt-2">
            {{ msg.content }}
          </div>
        </div>
        
        <div v-if="isLoading" class="text-indigo-300 text-xl tracking-widest animate-pulse mt-2">
          正在思考中...
        </div>
      </div>

      <div class="p-4 bg-slate-950/40 border-t border-white/5 rounded-b-2xl">
        <form @submit.prevent="sendMessage" class="flex gap-4 items-center max-w-4xl mx-auto">
          <input 
            v-model="userInput" 
            type="text" 
            placeholder="回应她..." 
            class="flex-1 bg-white/5 border border-white/10 focus:outline-none focus:border-indigo-400/50 focus:bg-white/10 rounded-full px-6 py-3 text-gray-200 placeholder-gray-500 transition-all duration-300 tracking-wider"
            :disabled="isLoading"
          />
          <button 
            type="submit" 
            :disabled="!userInput.trim() || isLoading"
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
import { ref, nextTick } from 'vue';
import axios from 'axios';

// --- State Management ---
const userInput = ref('');
const isLoading = ref(false);
const messages = ref([
  { role: 'assistant', content: '保科君，今天想聊些什么呢？' }
]);
const chatContainer = ref(null);

// --- Backend API Configuration ---
const API_URL = 'http://127.0.0.1:8000/v1/chat';

// --- Helper: Auto-scroll to the latest message ---
const scrollToBottom = async () => {
  await nextTick();
  if (chatContainer.value) {
    chatContainer.value.scrollTop = chatContainer.value.scrollHeight;
  }
};

// --- Main Chat Logic ---
const sendMessage = async () => {
  const text = userInput.value.trim();
  if (!text) return;

  // 1. Add user message
  messages.value.push({ role: 'user', content: text });
  userInput.value = '';
  isLoading.value = true;
  await scrollToBottom();

  try {
    // 2. Call FastAPI RAG backend
    const response = await axios.post(API_URL, {
      query: text,
      top_k: 3
    });
    
    // 3. Add bot response
    messages.value.push({ role: 'assistant', content: response.data.reply });
  } catch (error) {
    console.error('API Error:', error);
    messages.value.push({ role: 'assistant', content: '（大脑连接断开了，保科君能检查一下服务器吗...）' });
  } finally {
    isLoading.value = false;
    await scrollToBottom();
  }
};
</script>

<style scoped>
/* Adds a subtle shadow to text to ensure readability against dynamic backgrounds */
.text-shadow-sm {
  text-shadow: 1px 2px 4px rgba(0, 0, 0, 0.9);
}
</style>