<script setup lang="ts">
import { RouterView } from 'vue-router'
</script>

<template>
  <div class="h-full flex flex-col">
    <header class="bg-white border-b border-surface-200 px-4 py-3 flex items-center justify-between shrink-0">
      <router-link to="/" class="flex items-center gap-2">
        <div class="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center">
          <span class="text-white font-bold text-sm">C</span>
        </div>
        <h1 class="text-lg font-semibold text-surface-900">Cover Regulatory Engine</h1>
      </router-link>
      <nav class="flex items-center gap-4">
        <router-link to="/" class="text-sm text-surface-600 hover:text-surface-900 transition-colors">
          Assessment
        </router-link>
        <router-link to="/admin" class="text-sm text-surface-600 hover:text-surface-900 transition-colors">
          Admin
        </router-link>
      </nav>
    </header>
    <main class="flex-1 overflow-hidden">
      <RouterView />
    </main>
  </div>
</template>
