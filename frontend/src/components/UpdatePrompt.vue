<script setup>
import { onMounted, ref } from 'vue'

const needRefresh = ref(false)
const offline = ref(typeof navigator !== 'undefined' ? !navigator.onLine : false)
let updateSW = null

onMounted(async () => {
  window.addEventListener('online', () => {
    offline.value = false
  })
  window.addEventListener('offline', () => {
    offline.value = true
  })

  try {
    const { registerSW } = await import('virtual:pwa-register')
    updateSW = registerSW({
      immediate: true,
      onNeedRefresh() {
        needRefresh.value = true
      },
    })
  } catch {
    /* 开发模式可能无 virtual:pwa-register */
  }
})

function refresh() {
  needRefresh.value = false
  updateSW?.(true)
}
</script>

<template>
  <div v-if="offline" class="banner warn">网络不可用</div>
  <div v-else-if="needRefresh" class="banner">
    有新版本
    <button type="button" @click="refresh">点击刷新</button>
  </div>
</template>

<style scoped>
.banner {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 9999;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 12px;
  background: #323232;
  color: #fff;
  font-size: 14px;
}
.banner.warn {
  background: #8a6d3b;
}
.banner button {
  border: none;
  background: #07c160;
  color: #fff;
  padding: 6px 12px;
  border-radius: 4px;
  cursor: pointer;
}
</style>
