<script setup>
import { computed } from 'vue'
import { formatShanghai } from '../utils/beijingTime'
import { useChatStore } from '../stores/chat'

const props = defineProps({
  contactId: { type: Number, required: true },
  showBack: { type: Boolean, default: true },
})

const emit = defineEmits(['back', 'edit', 'chat', 'memory', 'deleted'])

const store = useChatStore()

const contact = computed(() => store.contacts.find((c) => c.id === props.contactId) || null)

function avatarSrc(c) {
  return c?.avatar_url || '/default-avatar.svg'
}

function formatDate(iso) {
  if (!iso) return '—'
  return formatShanghai(iso, {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  })
}

function onChat() {
  store.selectContact(props.contactId)
  emit('chat')
}

/** 删除当前联系人 */
async function removeContact() {
  const c = contact.value
  if (!c) return
  if (!confirm(`确定删除联系人「${c.name}」？聊天记录将无法恢复。`)) return
  await store.removeContact(c.id)
  emit('deleted')
}
</script>

<template>
  <div v-if="contact" class="contact-detail-page">
    <header class="detail-nav">
      <button v-if="showBack" type="button" class="nav-back" aria-label="返回" @click="emit('back')">
        <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M15 18l-6-6 6-6" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
      </button>
      <h1 class="nav-title">详细资料</h1>
      <span class="nav-spacer" aria-hidden="true" />
    </header>

    <div class="detail-scroll">
      <section class="hero">
        <img :src="avatarSrc(contact)" alt="" class="hero-avatar" />
        <p class="hero-name">{{ contact.name }}</p>
      </section>

      <section class="cell-group">
        <div class="cell">
          <span class="cell-label">添加时间</span>
          <span class="cell-value">{{ formatDate(contact.created_at) }}</span>
        </div>
        <div v-if="contact.last_message_at" class="cell">
          <span class="cell-label">最近聊天</span>
          <span class="cell-value">{{ formatDate(contact.last_message_at) }}</span>
        </div>
      </section>

      <section class="action-group">
        <button type="button" class="action-btn primary" @click="onChat">发消息</button>
        <button type="button" class="action-btn" @click="emit('memory', contact.id)">
          记忆
          <span v-if="contact.memory_unseen" class="badge">{{ contact.memory_unseen }}</span>
        </button>
        <button type="button" class="action-btn" @click="emit('edit', contact.id)">编辑资料</button>
        <button type="button" class="action-btn danger" @click="removeContact">删除联系人</button>
      </section>
    </div>
  </div>
  <div v-else class="contact-detail-page">
    <header class="detail-nav">
      <button type="button" class="nav-back" @click="emit('back')">返回</button>
    </header>
    <p class="missing">联系人不存在</p>
  </div>
</template>

<style scoped>
.contact-detail-page {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: var(--wx-bg-panel);
}

.detail-nav {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 48px;
  padding: 0 8px;
  border-bottom: 1px solid var(--wx-border);
  background: var(--wx-bg-panel);
  padding-top: env(safe-area-inset-top, 0px);
}

.nav-back {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 44px;
  height: 44px;
  border: none;
  background: none;
  color: #333;
  cursor: pointer;
}

.nav-title {
  margin: 0;
  font-size: 17px;
  font-weight: 500;
}

.nav-spacer {
  width: 44px;
}

.detail-scroll {
  flex: 1;
  overflow-y: auto;
  padding-bottom: calc(24px + env(safe-area-inset-bottom, 0px));
}

.hero {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 32px 16px 24px;
  background: #fff;
  border-bottom: 1px solid var(--wx-border);
}

.hero-avatar {
  width: 72px;
  height: 72px;
  border-radius: var(--wx-avatar-radius);
  object-fit: cover;
  margin-bottom: 12px;
}

.hero-name {
  margin: 0;
  font-size: 20px;
  font-weight: 500;
}

.cell-group {
  margin-top: 12px;
  background: #fff;
  border-top: 1px solid var(--wx-border);
  border-bottom: 1px solid var(--wx-border);
}

.cell {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 14px 16px;
  font-size: 15px;
  border-bottom: 1px solid #f0f0f0;
}

.cell:last-child {
  border-bottom: none;
}

.cell-block {
  flex-direction: column;
  align-items: stretch;
}

.cell-label {
  color: #888;
  font-size: 13px;
  flex-shrink: 0;
}

.cell-block .cell-label {
  margin-bottom: 8px;
}

.cell-body {
  margin: 0;
  color: #333;
  line-height: 1.55;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 15px;
}

.cell-value {
  color: #333;
  text-align: right;
  font-size: 14px;
}

.action-group {
  margin-top: 24px;
  padding: 0 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.action-btn {
  width: 100%;
  height: 44px;
  border: none;
  border-radius: 6px;
  font-size: 16px;
  cursor: pointer;
  background: #fff;
  color: #333;
  border: 1px solid var(--wx-border);
}

.action-btn.primary {
  background: var(--wx-green, #07c160);
  color: #fff;
  border-color: var(--wx-green, #07c160);
}

.action-btn.danger {
  color: #e64340;
  border-color: #f0c0be;
  margin-top: 8px;
}

.badge {
  display: inline-block;
  margin-left: 6px;
  min-width: 18px;
  padding: 0 6px;
  height: 18px;
  line-height: 18px;
  border-radius: 9px;
  background: #fa5151;
  color: #fff;
  font-size: 11px;
  vertical-align: middle;
}

.missing {
  padding: 24px;
  text-align: center;
  color: #888;
}
</style>
