<script setup>
import { computed, ref } from 'vue'
import { useChatStore } from '../stores/chat'
import { formatSessionTime } from '../utils/sessionTime'

const emit = defineEmits(['create'])

const store = useChatStore()
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
      <button type="button" class="top-add-btn" title="添加联系人" @click="emit('create')">
        <svg viewBox="0 0 16 16" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.5">
          <path d="M8 3v10M3 8h10" stroke-linecap="round" />
        </svg>
      </button>
    </div>
    <header class="session-header">
      <div class="search-wrap">
        <svg class="search-icon" viewBox="0 0 16 16" width="14" height="14">
          <circle cx="7" cy="7" r="4.5" fill="none" stroke="#999" stroke-width="1.2" />
          <path d="M10.5 10.5L14 14" stroke="#999" stroke-width="1.2" stroke-linecap="round" />
        </svg>
        <input v-model="keyword" type="text" placeholder="搜索" />
      </div>
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
  background: #fff;
  border-radius: 4px;
  padding: 6px 10px;
}

.search-icon {
  flex-shrink: 0;
}

.search-wrap input {
  flex: 1;
  border: none;
  outline: none;
  background: transparent;
  font-size: 13px;
  min-width: 0;
}

.add-icon {
  border: none;
  background: #e7e7e7;
  width: 32px;
  height: 32px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: #191919;
  flex-shrink: 0;
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
  gap: 12px;
  padding: 12px;
  cursor: pointer;
  border-bottom: 1px solid rgba(0, 0, 0, 0.04);
}

.session-list li:hover,
.session-list li.active {
  background: #c4c4c4;
}

.avatar-wrap {
  flex-shrink: 0;
}

.avatar {
  width: 48px;
  height: 48px;
  border-radius: var(--wx-avatar-radius, 6px);
  object-fit: cover;
  display: block;
}

.item-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 4px;
}

.item-top {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}

.name {
  font-size: 16px;
  color: var(--wx-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.time {
  font-size: 11px;
  color: #999;
  flex-shrink: 0;
}

.preview {
  font-size: 13px;
  color: #999;
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

  .top-add-btn {
    position: absolute;
    right: max(12px, env(safe-area-inset-right, 0px));
    top: env(safe-area-inset-top, 0px);
    bottom: 0;
    margin: auto 0;
    border: none;
    background: none;
    color: #191919;
    min-width: 44px;
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
}
</style>
