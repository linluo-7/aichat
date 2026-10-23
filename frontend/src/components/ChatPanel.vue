<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import ImageCropModal from './ImageCropModal.vue'
import {
  CROP_PRESET_BACKGROUND_DESKTOP,
  CROP_PRESET_BACKGROUND_MOBILE,
  useImageCrop,
} from '../composables/useImageCrop'
import { useMobile } from '../composables/useMobile'
import { formatChatMessageTime, shouldShowChatTime } from '../utils/beijingTime'
import { useChatStore } from '../stores/chat'
import { useProfileStore } from '../stores/profile'

defineProps({
  showBack: { type: Boolean, default: false },
})

const emit = defineEmits(['view-contact', 'back'])

const store = useChatStore()
const profile = useProfileStore()
const { isMobile } = useMobile()
const { cropOpen, cropSrc, cropOptions, handleCropConfirm, handleCropCancel, onImageSelected } =
  useImageCrop()
/** 当前正在设置哪一端背景：desktop | mobile */
const bgPlatform = ref('desktop')
const input = ref('')
const listRef = ref(null)
const bgInput = ref(null)
const fileInput = ref(null)
const historySearchInput = ref(null)
const showMenu = ref(false)
const showHistorySearch = ref(false)
const historyQuery = ref('')
const activeMatchIdx = ref(0)

const contact = computed(() => store.activeContact)

/** 当前关键词命中的消息在 messages 数组中的下标 */
const matchIndices = computed(() => {
  const q = historyQuery.value.trim().toLowerCase()
  if (!q) return []
  return store.messages.reduce((acc, msg, index) => {
    const haystack = [msg.content, msg.attachment_name, msg.attachment_kind === 'image' ? '图片' : '']
      .filter(Boolean)
      .join(' ')
      .toLowerCase()
    if (haystack.includes(q)) acc.push(index)
    return acc
  }, [])
})

const matchCount = computed(() => matchIndices.value.length)

const matchCounterText = computed(() => {
  if (!historyQuery.value.trim()) return ''
  if (!matchCount.value) return '无结果'
  return `${activeMatchIdx.value + 1}/${matchCount.value}`
})

const matchIndexSet = computed(() => new Set(matchIndices.value))

function isSearchHighlight(msgIndex) {
  if (!historyQuery.value.trim()) return false
  return matchIndexSet.value.has(msgIndex)
}

function isActiveSearchHit(msgIndex) {
  if (!matchCount.value) return false
  return matchIndices.value[activeMatchIdx.value] === msgIndex
}

const chatStyle = computed(() => {
  const c = contact.value
  const url = isMobile.value ? c?.chat_background_mobile_url : c?.chat_background_url
  if (url) {
    return {
      backgroundImage: `url(${url})`,
      backgroundSize: 'cover',
      backgroundPosition: 'center',
    }
  }
  return { backgroundColor: 'var(--wx-bg-chat)' }
})

const hasDesktopBg = computed(() => !!contact.value?.chat_background_url)
const hasMobileBg = computed(() => !!contact.value?.chat_background_mobile_url)

function avatarSrc(c) {
  return c?.avatar_url || '/default-avatar.svg'
}

function scrollBottom() {
  nextTick(() => {
    const el = listRef.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

watch(
  () => store.messages.length,
  () => {
    if (!showHistorySearch.value) scrollBottom()
  },
)

/** 上滑加载更早消息 */
function onMessagesScroll() {
  const el = listRef.value
  if (!el || el.scrollTop > 40) return
  const prevHeight = el.scrollHeight
  store.loadOlderMessages().then(() => {
    nextTick(() => {
      const next = listRef.value
      if (next) next.scrollTop = next.scrollHeight - prevHeight
    })
  })
}

watch(
  () => store.activeContactId,
  () => closeHistorySearch(),
)

watch(historyQuery, () => {
  activeMatchIdx.value = 0
  scrollToActiveMatch()
})

watch(activeMatchIdx, () => scrollToActiveMatch())

function scrollToActiveMatch() {
  if (!showHistorySearch.value || !matchCount.value) return
  const msgIndex = matchIndices.value[activeMatchIdx.value]
  const msg = store.messages[msgIndex]
  if (!msg) return
  nextTick(() => {
    const el = document.getElementById(`msg-${msg.id}`)
    el?.scrollIntoView({ block: 'center', behavior: 'smooth' })
  })
}

function openHistorySearch() {
  showHistorySearch.value = true
  nextTick(() => historySearchInput.value?.focus())
}

function closeHistorySearch() {
  showHistorySearch.value = false
  historyQuery.value = ''
  activeMatchIdx.value = 0
}

function prevHistoryMatch() {
  if (!matchCount.value) return
  activeMatchIdx.value = (activeMatchIdx.value - 1 + matchCount.value) % matchCount.value
}

function nextHistoryMatch() {
  if (!matchCount.value) return
  activeMatchIdx.value = (activeMatchIdx.value + 1) % matchCount.value
}

function onHistorySearchKeydown(e) {
  if (e.key === 'Enter') {
    e.preventDefault()
    if (e.shiftKey) prevHistoryMatch()
    else nextHistoryMatch()
  }
  if (e.key === 'Escape') closeHistorySearch()
}

async function send() {
  const text = input.value
  input.value = ''
  await store.sendMessage(text)
}

function onBgPick() {
  showMenu.value = false
  bgPlatform.value = isMobile.value ? 'mobile' : 'desktop'
  bgInput.value?.click()
}

function bgPlatformLabel() {
  return isMobile.value ? 'mobile' : 'desktop'
}

function bgCropPreset(platform) {
  return platform === 'mobile' ? CROP_PRESET_BACKGROUND_MOBILE : CROP_PRESET_BACKGROUND_DESKTOP
}

function onBgChange(e) {
  if (!contact.value) return
  const contactId = contact.value.id
  const platform = bgPlatform.value
  onImageSelected(e, bgCropPreset(platform), async (file) => {
    if (!file) return
    await store.setBackground(contactId, file, platform)
  })
}

function onCroppedBg(file) {
  handleCropConfirm(file)
}

function onCropDismiss() {
  handleCropCancel()
}

async function clearBg(platform) {
  if (!contact.value) return
  showMenu.value = false
  await store.removeBackground(contact.value.id, platform)
}

function onFilePick() {
  fileInput.value?.click()
}

async function onFileChange(e) {
  const file = e.target.files?.[0]
  if (!file) return
  e.target.value = ''
  await store.sendFile(file)
}

function hasBubbleBody(msg) {
  return !!(msg.content?.trim() || msg.attachment_url)
}

</script>

<template>
  <div class="wx-chat">
    <header class="wx-chat-head">
      <button
        v-if="showBack"
        type="button"
        class="head-back"
        aria-label="返回"
        @click="emit('back')"
      >
        ‹
      </button>
      <div class="head-title-wrap">
        <span class="head-name">{{ contact?.name }}</span>
        <span v-if="store.isTyping" class="head-typing">对方正在输入…</span>
      </div>
      <div class="head-menu-wrap">
        <button type="button" class="head-more" aria-label="更多" @click="showMenu = !showMenu">⋯</button>
        <div v-if="showMenu" class="head-dropdown">
          <button type="button" @click="onBgPick">设置聊天背景</button>
          <button
            v-if="isMobile ? hasMobileBg : hasDesktopBg"
            type="button"
            @click="clearBg(bgPlatformLabel())"
          >
            恢复默认背景
          </button>
        </div>
      </div>
      <input ref="bgInput" type="file" accept="image/*" hidden @change="onBgChange" />
    </header>

    <div ref="listRef" class="wx-messages" :style="chatStyle" @scroll="onMessagesScroll">
      <div v-if="store.loadingMessages && !store.messages.length" class="loading">加载中…</div>
      <template v-else>
        <div v-if="store.loadingMore" class="loading-more">加载更早消息…</div>
        <template v-for="(msg, msgIndex) in store.messages" :key="msg.id">
          <div v-if="shouldShowChatTime(store.messages, msgIndex)" class="msg-time">
            {{ formatChatMessageTime(msg.created_at) }}
          </div>
          <div
            :id="`msg-${msg.id}`"
            class="msg-row"
            :class="{
              'is-self': msg.role === 'user',
              'is-other': msg.role !== 'user',
              'search-hit': isSearchHighlight(msgIndex),
              'search-active': isActiveSearchHit(msgIndex),
            }"
          >
          <button
            v-if="msg.role !== 'user'"
            type="button"
            class="msg-avatar-btn"
            title="查看资料"
            @click="emit('view-contact', contact.id)"
          >
            <img :src="avatarSrc(contact)" alt="" class="msg-avatar" />
          </button>
          <div class="msg-bubble">
            <img
              v-if="msg.attachment_kind === 'image' && msg.attachment_url"
              :src="msg.attachment_url"
              alt="图片"
              class="msg-image"
            />
            <a
              v-else-if="msg.attachment_kind === 'file' && msg.attachment_url"
              class="msg-file"
              :href="msg.attachment_url"
              :download="msg.attachment_name || true"
              target="_blank"
              rel="noopener"
            >
              📎 {{ msg.attachment_name || '文件' }}
            </a>
            <p v-if="msg.content?.trim()" class="msg-text">{{ msg.content }}</p>
            <span v-else-if="!hasBubbleBody(msg)">…</span>
            <span v-if="msg._failed" class="msg-failed">发送失败</span>
          </div>
          <img v-if="msg.role === 'user'" :src="profile.displayAvatar" alt="" class="msg-avatar" />
          </div>
        </template>
        <div v-if="store.failedJob" class="sys-fail">
          回复失败：{{ store.failedJob.error || '未知错误' }}
          <button type="button" class="sys-fail-retry" @click="store.retryFailed()">重试</button>
        </div>
      </template>
    </div>

    <footer class="wx-composer">
      <div class="composer-tools">
        <button
          type="button"
          class="tool-btn"
          title="发送图片或文件"
          @click="onFilePick"
        >
          <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="#666" stroke-width="1.5">
            <path d="M12 5v14M5 12h14" stroke-linecap="round" />
          </svg>
        </button>

        <div class="tools-spacer" />

        <div v-if="showHistorySearch" class="history-search">
          <svg class="history-search-icon" viewBox="0 0 16 16" width="14" height="14">
            <circle cx="7" cy="7" r="4.5" fill="none" stroke="#999" stroke-width="1.2" />
            <path d="M10.5 10.5L14 14" stroke="#999" stroke-width="1.2" stroke-linecap="round" />
          </svg>
          <input
            ref="historySearchInput"
            v-model="historyQuery"
            type="text"
            class="history-search-input"
            placeholder="搜索聊天记录"
            @keydown="onHistorySearchKeydown"
          />
          <span class="history-search-count">{{ matchCounterText }}</span>
          <button type="button" class="history-nav-btn" title="上一条" @click="prevHistoryMatch">↑</button>
          <button type="button" class="history-nav-btn" title="下一条" @click="nextHistoryMatch">↓</button>
          <button type="button" class="history-close-btn" title="关闭" @click="closeHistorySearch">×</button>
        </div>
        <button
          v-else
          type="button"
          class="tool-btn"
          title="查找聊天记录"
          @click="openHistorySearch"
        >
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="#666" stroke-width="1.8">
            <circle cx="11" cy="11" r="6" />
            <path d="M16 16l4 4" stroke-linecap="round" />
          </svg>
        </button>
      </div>
      <input
        ref="fileInput"
        type="file"
        hidden
        accept="image/jpeg,image/png,image/gif,image/webp,.txt,.md,.json,.pdf,.doc,.docx"
        @change="onFileChange"
      />
      <textarea
        v-model="input"
        class="composer-input"
        rows="2"
        placeholder=""
        @keydown.enter.exact.prevent="send"
      />
      <div class="composer-foot">
        <span class="composer-hint">Enter 发送</span>
        <button
          type="button"
          class="send-btn"
          :disabled="!input.trim()"
          @click="send"
        >
          发送(S)
        </button>
      </div>
    </footer>

    <ImageCropModal
      v-if="cropOpen"
      :src="cropSrc"
      :aspect-ratio="cropOptions.aspectRatio"
      :title="cropOptions.title"
      :max-width="cropOptions.maxWidth"
      :max-height="cropOptions.maxHeight"
      :portrait-crop="!!cropOptions.portraitCrop"
      @confirm="onCroppedBg"
      @cancel="onCropDismiss"
    />
  </div>
</template>

<style scoped>
.wx-chat {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--wx-bg-panel);
}

.wx-chat-head {
  height: calc(52px + env(safe-area-inset-top, 0px));
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  position: relative;
  background: var(--wx-bg-panel);
  border-bottom: 1px solid var(--wx-border);
  padding-top: env(safe-area-inset-top, 0px);
}

.head-back {
  position: absolute;
  left: max(4px, env(safe-area-inset-left, 0px));
  top: env(safe-area-inset-top, 0px);
  bottom: 0;
  margin: auto 0;
  border: none;
  background: none;
  color: #191919;
  font-size: 32px;
  line-height: 1;
  padding: 0 12px;
  min-width: 44px;
  min-height: 44px;
  cursor: pointer;
}

.head-title-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  min-width: 0;
}

.head-name {
  font-size: 15px;
  font-weight: 500;
  color: var(--wx-text);
}

.head-typing {
  font-size: 12px;
  color: var(--wx-text-muted, #999);
  font-weight: 400;
}

.loading-more {
  text-align: center;
  font-size: 12px;
  color: #999;
  padding: 8px;
}

.sys-fail {
  text-align: center;
  font-size: 12px;
  color: #888;
  padding: 10px 16px 16px;
}

.sys-fail-retry {
  margin-left: 8px;
  border: none;
  background: none;
  color: var(--wx-green, #07c160);
  cursor: pointer;
  font-size: 12px;
}

.msg-failed {
  display: block;
  margin-top: 4px;
  font-size: 11px;
  color: #e64545;
}

.msg-avatar-btn {
  padding: 0;
  border: none;
  background: none;
  cursor: pointer;
  flex-shrink: 0;
}

.head-menu-wrap {
  position: absolute;
  right: 16px;
  top: 50%;
  transform: translateY(-50%);
}

.head-more {
  border: none;
  background: none;
  font-size: 22px;
  line-height: 1;
  color: #666;
  cursor: pointer;
  padding: 4px 8px;
  letter-spacing: 2px;
}

.head-dropdown {
  position: absolute;
  right: 0;
  top: 100%;
  margin-top: 4px;
  background: #fff;
  border: 1px solid var(--wx-border);
  border-radius: 4px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  min-width: 140px;
  z-index: 10;
  overflow: hidden;
}

.head-dropdown button {
  display: block;
  width: 100%;
  border: none;
  background: #fff;
  text-align: left;
  padding: 10px 14px;
  font-size: 13px;
  cursor: pointer;
  color: #333;
}

.head-dropdown button:hover {
  background: #f5f5f5;
}

.head-dropdown button.danger {
  color: #fa5151;
}

.wx-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px 20px;
}

.loading {
  text-align: center;
  color: #999;
  padding: 24px;
  font-size: 13px;
}

.msg-time {
  text-align: center;
  font-size: 12px;
  line-height: 1.4;
  color: #b2b2b2;
  padding: 6px 0 10px;
  user-select: none;
}

.msg-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 14px;
  width: 100%;
}

/* 对方：左对齐，头像在左、气泡在右 */
.msg-row.is-other {
  justify-content: flex-start;
}

/* 自己：右对齐，气泡在左、头像在右（与微信一致） */
.msg-row.is-self {
  justify-content: flex-end;
}

.msg-avatar {
  width: 36px;
  height: 36px;
  border-radius: var(--wx-avatar-radius);
  object-fit: cover;
  background: #ddd;
  flex-shrink: 0;
}

.msg-bubble {
  max-width: min(420px, 62%);
  padding: 9px 12px;
  font-size: 14px;
  line-height: 1.5;
  word-break: break-word;
  position: relative;
}

.msg-text {
  margin: 0;
  white-space: pre-wrap;
}

.msg-image {
  max-width: 220px;
  max-height: 220px;
  border-radius: 4px;
  display: block;
  cursor: pointer;
}

.msg-file {
  color: #576b95;
  text-decoration: none;
  font-size: 13px;
  word-break: break-all;
}

.msg-file:hover {
  text-decoration: underline;
}

.is-other .msg-bubble {
  background: var(--wx-bubble-other);
  border-radius: 4px;
  box-shadow: 0 1px 1px rgba(0, 0, 0, 0.06);
}

.is-self .msg-bubble {
  background: var(--wx-bubble-self);
  border-radius: 4px;
}

.wx-composer {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  background: var(--wx-bg-panel);
  border-top: 1px solid var(--wx-border);
}

.composer-tools {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px 0;
  min-height: 32px;
}

.tools-spacer {
  flex: 1;
}

.history-search {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 1;
  max-width: 420px;
  background: #ebebeb;
  border-radius: 4px;
  padding: 4px 8px;
}

.history-search-icon {
  flex-shrink: 0;
}

.history-search-input {
  flex: 1;
  min-width: 0;
  border: none;
  background: transparent;
  font-size: 13px;
  outline: none;
}

.history-search-count {
  font-size: 11px;
  color: #888;
  white-space: nowrap;
  min-width: 36px;
  text-align: center;
}

.history-nav-btn,
.history-close-btn {
  border: none;
  background: transparent;
  color: #666;
  cursor: pointer;
  padding: 2px 6px;
  font-size: 14px;
  line-height: 1;
  border-radius: 3px;
}

.history-nav-btn:hover,
.history-close-btn:hover {
  background: rgba(0, 0, 0, 0.06);
}

.history-close-btn {
  font-size: 18px;
}

.msg-row.search-hit .msg-bubble {
  outline: 2px solid rgba(7, 193, 96, 0.35);
}

.msg-row.search-active .msg-bubble {
  outline: 2px solid var(--wx-green);
  box-shadow: 0 0 0 2px rgba(7, 193, 96, 0.2);
}

.tool-btn {
  border: none;
  background: none;
  padding: 4px;
  cursor: pointer;
  opacity: 0.85;
  border-radius: 4px;
}

.tool-btn:hover:not(:disabled) {
  background: rgba(0, 0, 0, 0.05);
}

.tool-btn:disabled {
  cursor: not-allowed;
  opacity: 0.4;
}

.composer-input {
  flex: 0 0 auto;
  border: none;
  resize: none;
  padding: 4px 16px 2px;
  font-size: 14px;
  line-height: 1.45;
  background: transparent;
  outline: none;
  max-height: 88px;
  min-height: 40px;
  field-sizing: content;
}

.composer-foot {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  padding: 2px 12px 8px;
}

.composer-hint {
  font-size: 12px;
  color: var(--wx-text-muted);
  margin-right: auto;
}

.send-btn {
  border: none;
  background: #e9e9e9;
  color: #07c160;
  font-size: 13px;
  padding: 5px 16px;
  border-radius: 4px;
  cursor: pointer;
  font-weight: 500;
  height: 32px;
}

.send-btn:not(:disabled) {
  background: var(--wx-green);
  color: #fff;
}

.send-btn:not(:disabled):hover {
  background: var(--wx-green-hover);
}

.send-btn:disabled {
  cursor: not-allowed;
  color: #bbb;
}

@media (max-width: 768px) {
  .wx-messages {
    padding: 12px 12px 16px;
    -webkit-overflow-scrolling: touch;
  }

  .msg-bubble {
    max-width: min(280px, 78%);
    font-size: 16px;
  }

  .msg-avatar {
    width: 40px;
    height: 40px;
  }

  .msg-image {
    max-width: min(200px, 70vw);
  }

  .wx-composer {
    padding-bottom: env(safe-area-inset-bottom, 0px);
  }

  .composer-input {
    min-height: 36px;
    max-height: 96px;
    font-size: 16px;
    padding: 4px 12px 2px;
  }

  .composer-hint {
    display: none;
  }

  .composer-foot {
    padding: 2px 12px calc(6px + env(safe-area-inset-bottom, 0px));
  }

  .send-btn {
    min-height: 36px;
    height: 36px;
    min-width: 56px;
    font-size: 15px;
  }

  .tool-btn {
    min-width: 44px;
    min-height: 44px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .history-search {
    max-width: none;
    flex: 1;
  }

  .head-name {
    font-size: 17px;
    max-width: 50vw;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .head-more {
    min-width: 44px;
    min-height: 44px;
    padding-right: max(8px, env(safe-area-inset-right, 0px));
  }
}
</style>
