<script setup>
defineProps({
  active: { type: String, required: true }, // chat | moments | me
})
defineEmits(['change'])
</script>

<template>
  <nav class="tab-bar" aria-label="主导航">
    <button
      type="button"
      class="tab"
      :class="{ active: active === 'chat' }"
      @click="$emit('change', 'chat')"
    >
      <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.7">
        <path
          d="M5 6.5A2.5 2.5 0 017.5 4h9A2.5 2.5 0 0119 6.5v7a2.5 2.5 0 01-2.5 2.5H11l-4 3v-3H7.5A2.5 2.5 0 015 13.5v-7z"
          stroke-linejoin="round"
        />
      </svg>
      <span>聊天</span>
    </button>
    <button
      type="button"
      class="tab"
      :class="{ active: active === 'moments' }"
      @click="$emit('change', 'moments')"
    >
      <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.7">
        <circle cx="12" cy="12" r="8" />
        <circle cx="12" cy="12" r="3" />
      </svg>
      <span>朋友圈</span>
    </button>
    <button
      type="button"
      class="tab"
      :class="{ active: active === 'me' }"
      @click="$emit('change', 'me')"
    >
      <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.7">
        <circle cx="12" cy="9" r="3.2" />
        <path d="M5.5 19c1.5-3 3.8-4.5 6.5-4.5S17 16 18.5 19" stroke-linecap="round" />
      </svg>
      <span>我的</span>
    </button>
  </nav>
</template>

<style scoped>
.tab-bar {
  display: flex;
  flex-shrink: 0;
  background: #f7f7f7;
  border-top: 1px solid rgba(0, 0, 0, 0.08);
  padding-bottom: env(safe-area-inset-bottom, 0px);
  z-index: 30;
}
.tab {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 2px;
  border: none;
  background: none;
  padding: 6px 0 4px;
  color: #191919;
  cursor: pointer;
  font-size: 10px;
  line-height: 1.2;
}
.tab.active {
  color: var(--wx-green, #07c160);
}
.tab svg {
  display: block;
}
</style>
