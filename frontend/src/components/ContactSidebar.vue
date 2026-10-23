<script setup>
import { computed, ref } from 'vue'
import { useChatStore } from '../stores/chat'
import { useProfileStore } from '../stores/profile'
import { formatSessionTime } from '../utils/sessionTime'

const emit = defineEmits(['create', 'profile', 'moments'])

const store = useChatStore()
const profile = useProfileStore()
const keyword = ref('')

const filteredContacts = computed(() => {
  const q = keyword.value.trim().toLowerCase()
  if (!q) return store.contacts
  return store.contacts.filter((c) => c.name.toLowerCase().includes(q))
})

function avatarSrc(contact) {
  return contact.avatar_url || '/default-avatar.svg'
}

function previewText(contact) {
  return contact.last_message_preview || '暂无消息'
}

</script>

<template>
  <aside class="wx-session">
    <div class="list-top-bar">
      <h1 class="list-title">聊天</h1>
      <div class="top-actions">
        <button type="button" class="top-add-btn" title="朋友圈" @click="emit('moments')">
          <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.6">
            <circle cx="12" cy="12" r="8" />
            <circle cx="12" cy="12" r="3" />
          </svg>
        </button>
        <button type="button" class="top-add-btn" title="添加联系人" @click="emit('create')">
          <svg viewBox="0 0 16 16" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M8 3v10M3 8h10" stroke-linecap="round" />
          </svg>
        </button>
      </div>
    </div>
    <header class="session-header">
      <div class="search-wrap">
        <svg class="search-icon" viewBox="0 0 16 16" width="14" height="14">
          <circle cx="7" cy="7" r="4.5" fill="none" stroke="#999" stroke-width="1.2" />
          <path d="M10.5 10.5L14 14" stroke="#999" stroke-width="1.2" stroke-linecap="round" />
        </svg>
        <input v-model="keyword" type="text" placeholder="搜索" />
      </div>
      <button type="button" class="add-icon" title="朋友圈" @click="emit('moments')">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.6">
          <circle cx="12" cy="12" r="8" />
          <circle cx="12" cy="12" r="3" />
        </svg>
      </button>
      <button type="button" class="add-icon" title="添加联系人" @click="emit('create')">
        <svg viewBox="0 0 16 16" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M8 3v10M3 8h10" stroke-linecap="round" />
        </svg>
      </button>
    </header>

    <ul class="session-list">
      <li
        v-for="c in filteredContacts"
        :key="c.id"
        :class="{ active: c.id === store.activeContactId }"
        @click="store.selectContact(c.id)"
      >
        <div class="avatar-wrap">
          <img :src="avatarSrc(c)" alt="" class="avatar" />
        </div>
        <div class="item-body">
          <div class="item-top">
            <span class="name">{{ c.name }}</span>
            <span v-if="c.last_message_at" class="time">{{ formatSessionTime(c.last_message_at) }}</span>
          </div>
          <span class="preview">{{ previewText(c) }}</span>
        </div>
      </li>
    </ul>

    <p v-if="!store.contacts.length && !store.loadingContacts" class="tip">暂无聊天，点击 + 添加联系人</p>

    <footer class="session-footer">
      <button type="button" class="me-profile" @click="emit('profile')">
        <img :src="profile.displayAvatar" alt="" class="avatar" />
        <span class="me-name">{{ profile.nickname }}</span>
      </button>
    </footer>
  </aside>
</template>

<style scoped>
.wx-session {
  width: 280px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: var(--wx-bg-session);
  border-right: 1px solid var(--wx-border);
  height: 100%;
}

.session-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 18px 12px 10px;
}

.search-wrap {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 6px;
  background: #e2e2e2;
  border-radius: 4px;
  padding: 6px 8px;
}

.search-wrap input {
  flex: 1;
  border: none;
  background: transparent;
  font-size: 12px;
  outline: none;
  color: var(--wx-text);
}

.search-wrap input::placeholder {
  color: #999;
}

.search-icon {
  flex-shrink: 0;
}

.add-icon {
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  color: #666;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
}

.add-icon:hover {
  background: rgba(0, 0, 0, 0.06);
}

.avatar-wrap {
  flex-shrink: 0;
  border-radius: var(--wx-avatar-radius);
}

.avatar {
  width: 40px;
  height: 40px;
  border-radius: var(--wx-avatar-radius);
  object-fit: cover;
  background: #ddd;
  display: block;
}

.session-list {
  list-style: none;
  margin: 0;
  padding: 0;
  overflow-y: auto;
  flex: 1;
}

.session-list li {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  cursor: pointer;
  border-bottom: 1px solid rgba(0, 0, 0, 0.04);
  transition: background 0.1s;
}

.session-list li:hover {
  background: #dcdcdc;
}

.session-list li.active {
  background: #c9c9c9;
}

.item-body {
  flex: 1;
  min-width: 0;
}

.item-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.name {
  font-size: 14px;
  font-weight: 400;
  color: var(--wx-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  min-width: 0;
}

.time {
  font-size: 11px;
  color: var(--wx-text-muted);
  flex-shrink: 0;
}

.preview {
  font-size: 12px;
  color: var(--wx-text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  display: block;
}

.tip {
  text-align: center;
  font-size: 12px;
  color: #999;
  padding: 16px;
  margin: 0;
}

.session-footer {
  flex-shrink: 0;
  border-top: 1px solid var(--wx-border);
  background: #e3e3e3;
  padding: 10px 12px;
}

.me-profile {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
  border: none;
  background: transparent;
  cursor: pointer;
  padding: 6px 4px;
  border-radius: 4px;
  text-align: left;
}

.me-profile:hover {
  background: rgba(0, 0, 0, 0.05);
}

.me-name {
  font-size: 14px;
  color: var(--wx-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.list-top-bar {
  display: none;
}

@media (max-width: 768px) {
  .wx-session {
    width: 100%;
    border-right: none;
  }

  .list-top-bar {
    display: flex;
    align-items: center;
    justify-content: center;
    position: relative;
    flex-shrink: 0;
    height: calc(44px + env(safe-area-inset-top, 0px));
    padding: env(safe-area-inset-top, 0px) 12px 0;
    background: var(--wx-bg-session);
    border-bottom: 1px solid rgba(0, 0, 0, 0.06);
  }

  .list-title {
    margin: 0;
    font-size: 17px;
    font-weight: 600;
    color: var(--wx-text);
  }

  .top-actions {
    position: absolute;
    right: max(4px, env(safe-area-inset-right, 0px));
    top: env(safe-area-inset-top, 0px);
    bottom: 0;
    margin: auto 0;
    display: flex;
    align-items: center;
    height: 44px;
  }

  .top-add-btn {
    border: none;
    background: none;
    color: #191919;
    min-width: 40px;
    min-height: 44px;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
  }

  .session-header {
    padding: 10px 12px;
  }

  .session-header .add-icon {
    display: none;
  }

  .search-wrap {
    padding: 8px 10px;
  }

  .search-wrap input {
    font-size: 14px;
  }

  .session-list li {
    padding: 14px 16px;
    -webkit-tap-highlight-color: transparent;
  }

  .avatar {
    width: 48px;
    height: 48px;
  }

  .session-footer {
    padding-bottom: calc(10px + env(safe-area-inset-bottom, 0px));
  }
}
</style>
