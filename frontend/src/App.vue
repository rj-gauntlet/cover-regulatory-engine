<script setup lang="ts">
import { RouterView } from 'vue-router'
</script>

<template>
  <div class="h-full flex flex-col">
    <header class="h-14 bg-cover-black border-b border-cover-dark px-6 flex items-center justify-between shrink-0">
      <router-link to="/" class="flex items-center gap-2 no-underline">
        <svg class="w-7 h-7" viewBox="0 0 43.4 48" fill="none">
          <path d="M17.8133 1.02168C20.2466 -0.365764 23.2379 -0.338384 25.6454 1.09337L33.514 5.77283C34.5694 6.40048 34.9162 7.76483 34.2885 8.82021C33.6609 9.87559 32.2965 10.2223 31.2411 9.5947L23.3725 4.91524C22.3407 4.30163 21.0587 4.28989 20.0159 4.88451L6.1298 12.8021C5.08917 13.3955 4.4467 14.5013 4.4467 15.6992V31.9977C4.4467 33.1866 5.07968 34.2856 6.10807 34.8823L19.5033 42.654V27.0903C19.5033 24.3117 20.9849 21.744 23.3904 20.3534L37.9342 11.9458C40.3428 10.5534 43.3554 12.2915 43.3554 15.0736V32.7296C43.3554 35.4904 40.3844 37.231 37.9761 35.8813L29.2062 30.9664C28.135 30.366 27.7533 29.011 28.3536 27.9399C28.954 26.8687 30.309 26.487 31.3802 27.0874L38.9087 31.3066V16.5187L25.6159 24.2031C24.585 24.799 23.95 25.8995 23.95 27.0903V44.1017C23.95 46.8863 20.9326 48.6241 18.524 47.2267L3.87652 38.7284C1.47693 37.3362 0 34.7718 0 31.9977V15.6992C0 12.9042 1.49908 10.3238 3.92722 8.93929L17.8133 1.02168Z" fill="white"/>
        </svg>
        <span class="text-[17px] text-white" style="font-family: 'Outfit', sans-serif; font-weight: 700;">Cover</span>
        <span class="font-light text-surface-400 text-[13px] tracking-normal ml-0.5">Regulatory Engine</span>
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
      <RouterView v-slot="{ Component }">
        <KeepAlive>
          <component :is="Component" />
        </KeepAlive>
      </RouterView>
    </main>
  </div>
</template>
