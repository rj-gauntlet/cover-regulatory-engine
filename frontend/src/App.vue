<script setup lang="ts">
import { RouterView } from 'vue-router'
</script>

<template>
  <div class="h-full flex flex-col">
    <header class="h-14 bg-cover-black border-b border-cover-dark px-6 flex items-center justify-between shrink-0">
      <router-link to="/" class="flex items-center gap-1.5 no-underline">
        <svg class="w-6 h-6" viewBox="0 0 32 34" fill="none">
          <path d="M9 24 L3 18 L3 10 L9 4 L19 4" stroke="white" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round"/>
          <path d="M9 24 L17 31 L26 14" stroke="white" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <span class="text-[16px] text-white" style="font-family: 'Outfit', sans-serif; font-weight: 500;">Cover</span>
        <span class="font-light text-surface-400 text-[13px] tracking-normal ml-1">Regulatory Engine</span>
      </router-link>
      <nav class="flex items-center gap-2">
        <router-link
          to="/"
          active-class="!text-white !bg-cover-dark"
          class="text-[11px] font-medium uppercase tracking-widest text-surface-400 hover:text-white hover:bg-cover-dark px-3.5 py-1.5 rounded transition-colors"
        >
          Assessment
        </router-link>
        <router-link
          to="/admin"
          active-class="!text-white !bg-cover-dark"
          class="text-[11px] font-medium uppercase tracking-widest text-surface-400 hover:text-white hover:bg-cover-dark px-3.5 py-1.5 rounded transition-colors"
        >
          Admin
        </router-link>
      </nav>
    </header>
    <main class="flex-1 overflow-hidden">
      <RouterView />
    </main>
  </div>
</template>
