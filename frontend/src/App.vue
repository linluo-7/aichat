<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import AuthPage from './components/AuthPage.vue'
import ChatPanel from './components/ChatPanel.vue'
import ContactSidebar from './components/ContactSidebar.vue'
import CreateContactModal from './components/CreateContactModal.vue'
import ProfileSettingsModal from './components/ProfileSettingsModal.vue'
import ContactDetailPage from './components/ContactDetailPage.vue'
import EditContactModal from './components/EditContactModal.vue'
import MemoryPage from './components/MemoryPage.vue'
import UpdatePrompt from './components/UpdatePrompt.vue'
import { useMobile } from './composables/useMobile'
import { useSync } from './composables/useSync'
import { useAuthStore } from './stores/auth'
import { useChatStore } from './stores/chat'
import { useProfileStore } from './stores/profile'

const auth = useAuthStore()
const store = useChatStore()
const profile = useProfileStore()
const { isMobile } = useMobile()
const showCreate = ref(false)
const createFormKey = ref(0)
const showProfile = ref(false)
const detailContactId = ref(null)
const editContactId = ref(null)
const memoryContactId = ref(null)
const syncEnabled = computed(() => auth.isLoggedIn)

const showSidebar = computed(
  () =>
    !isMobile.value ||
    (!store.activeContactId && detailContactId.value == null && memoryContactId.value == null),
)
const showMainPane = computed(
  () =>
    !isMobile.value ||
    !!store.activeContactId ||
    detailContactId.value != null ||
    memoryContactId.value != null,
)

function openCreate() {
  createFormKey.value += 1
  showCreate.value = true
}

function openContactDetail(id) {
  detailContactId.value = id
}

function closeContactDetail() {
  detailContactId.value = null
}

function openEditContact(id) {
  editContactId.value = id
}

function onDetailChat() {
  detailContactId.value = null
}

function openMemory(id) {
  memoryContactId.value = id
}

function closeMemory() {
  memoryContactId.value = null
}

function onUnauthorized() {
  auth.logout()
  store.$reset()
  localStorage.removeItem('aichat_last_sync_id')
  detailContactId.value = null
  memoryContactId.value = null
  editContactId.value = null
  showProfile.value = false
  showCreate.value = false
}

async function afterLogin() {
  await profile.fetchProfile()
  await store.fetchContacts()
}

useSync(store, { enabled: syncEnabled })

watch(
  () => auth.isLoggedIn,
  async (ok) => {
    if (ok) await afterLogin()
  },
)

onMounted(async () => {
  window.addEventListener('aichat:unauthorized', onUnauthorized)
  await auth.bootstrap()
  if (auth.isLoggedIn) await afterLogin()
})

onUnmounted(() => {
  window.removeEventListener('aichat:unauthorized', onUnauthorized)
})
</script>

<template>
  <AuthPage v-if="auth.bootstrapped && !auth.isLoggedIn" @done="afterLogin" />
  <div v-else-if="auth.isLoggedIn" class="wx-app" :class="{ 'is-mobile': isMobile }">
    <UpdatePrompt />
    <ContactSidebar
      v-show="showSidebar"
      class="wx-session-pane"
      :class="{ 'pane-full': isMobile }"
      @create="openCreate"
      @profile="showProfile = true"
    />

    <main v-show="showMainPane" class="wx-chat-main" :class="{ 'pane-full': isMobile }">
      <MemoryPage
        v-if="memoryContactId != null"
        :contact-id="memoryContactId"
        :contact-name="store.contacts.find((c) => c.id === memoryContactId)?.name || ''"
        @back="closeMemory"
      />
      <ContactDetailPage
        v-else-if="detailContactId != null"
        :contact-id="detailContactId"
        show-back
        @back="closeContactDetail"
        @edit="openEditContact"
        @chat="onDetailChat"
        @memory="openMemory"
        @deleted="closeContactDetail"
      />
      <ChatPanel
        v-else-if="store.activeContact"
        :show-back="isMobile"
        @back="store.backToList()"
        @view-contact="openContactDetail"
      />
      <div v-else-if="!isMobile" class="wx-empty">
        <svg class="empty-icon" viewBox="0 0 120 120" width="120" height="120">
          <circle cx="60" cy="60" r="56" fill="#e5e5e5" />
          <path
            d="M38 52c0-12 10-22 22-22s22 10 22 22-10 22-22 22c-2.5 0-5-.4-7.2-1.2L38 78V52z"
            fill="#cfcfcf"
          />
        </svg>
        <p class="empty-text">选择一个联系人开始聊天</p>
        <button type="button" class="wx-btn wx-btn-primary" @click="openCreate">
          添加联系人
        </button>
      </div>
    </main>

    <CreateContactModal v-if="showCreate" :key="createFormKey" @close="showCreate = false" />
    <ProfileSettingsModal v-if="showProfile" @close="showProfile = false" />
    <EditContactModal
      v-if="editContactId != null"
      :key="editContactId"
      :contact-id="editContactId"
      @close="editContactId = null"
    />
  </div>
  <div v-else class="boot-splash">加载中…</div>
</template>

<style scoped>
.boot-splash {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #888;
  font-size: 14px;
}
.wx-app {
  display: flex;
  height: 100vh;
  height: 100dvh;
  max-width: 1400px;
  margin: 0 auto;
  background: #fff;
  box-shadow: 0 0 0 1px var(--wx-border);
  overflow: hidden;
}

.wx-app.is-mobile {
  max-width: none;
  margin: 0;
  box-shadow: none;
}

.wx-session-pane {
  flex-shrink: 0;
}

.pane-full {
  flex: 1;
  width: 100%;
  min-width: 0;
}

.wx-chat-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: var(--wx-bg-panel);
}

.wx-empty {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  background: var(--wx-bg-panel);
}

.empty-icon {
  opacity: 0.85;
}

.empty-text {
  margin: 0;
  font-size: 14px;
  color: var(--wx-text-muted);
}
</style>
