import { defineStore } from 'pinia'
import {
  clearBackground,
  createContact,
  deleteContact,
  listContacts,
  listMessages,
  postMessage,
  postMessageFile,
  retryJob,
  syncAfter,
  updateContact as updateContactApi,
  uploadAvatar,
  uploadBackground,
} from '../api/client'

const SYNC_ID_KEY = 'aichat_last_sync_id'
const MSG_CAP = 500
/** 正在输入提示最短展示毫秒，避免无流式时一闪而过 */
const TYPING_HOLD_MS = 2500

function loadSyncId() {
  const n = Number(localStorage.getItem(SYNC_ID_KEY) || '0')
  return Number.isFinite(n) && n >= 0 ? n : 0
}

function saveSyncId(id) {
  localStorage.setItem(SYNC_ID_KEY, String(id))
}

export const useChatStore = defineStore('chat', {
  state: () => ({
    contacts: [],
    activeContactId: null,
    /** @type {Record<number, Array>} */
    messagesByContact: {},
    /** @type {Record<number, boolean>} */
    hasMoreHistory: {},
    lastSyncId: loadSyncId(),
    typingContactIds: [],
    busyContactIds: [],
    /** @type {Record<number, number>} contactId -> 最短展示截止时间戳 */
    typingHoldUntil: {},
    /** @type {Record<number, {id:number,error?:string}>} */
    failedJobsByContact: {},
    loadingContacts: false,
    loadingMessages: false,
    loadingMore: false,
    sending: false,
    syncing: false,
    needFastSync: false,
  }),
  getters: {
    activeContact(state) {
      return state.contacts.find((c) => c.id === state.activeContactId) || null
    },
    messages(state) {
      if (!state.activeContactId) return []
      return state.messagesByContact[state.activeContactId] || []
    },
    isTyping(state) {
      if (!state.activeContactId) return false
      const id = state.activeContactId
      if (state.typingContactIds.includes(id)) return true
      const hold = state.typingHoldUntil[id] || 0
      return Date.now() < hold
    },
    failedJob(state) {
      if (!state.activeContactId) return null
      return state.failedJobsByContact[state.activeContactId] || null
    },
  },
  actions: {
    /** 乐观显示正在输入，并锁定最短展示时间 */
    _markTypingLocal(contactId) {
      if (!contactId) return
      const ids = new Set(this.typingContactIds)
      ids.add(contactId)
      this.typingContactIds = [...ids]
      const busy = new Set(this.busyContactIds)
      busy.add(contactId)
      this.busyContactIds = [...busy]
      this.typingHoldUntil = {
        ...this.typingHoldUntil,
        [contactId]: Date.now() + TYPING_HOLD_MS,
      }
      this.needFastSync = true
    },
    _mergeTypingFromServer(serverTyping, serverBusy) {
      const now = Date.now()
      const hold = { ...this.typingHoldUntil }
      const typing = new Set(serverTyping || [])
      const busy = new Set(serverBusy || [])
      // 最短展示期内服务器已结束，仍保留本地提示
      for (const [cid, until] of Object.entries(hold)) {
        const id = Number(cid)
        if (until > now) {
          typing.add(id)
          busy.add(id)
        } else {
          delete hold[id]
        }
      }
      // 服务器仍在忙的，刷新 hold，保证气泡间隙也看得见
      for (const id of serverTyping || []) {
        hold[id] = Math.max(hold[id] || 0, now + TYPING_HOLD_MS)
      }
      this.typingHoldUntil = hold
      this.typingContactIds = [...typing]
      this.busyContactIds = [...busy]
      this.needFastSync = busy.size > 0
    },

    _setMessages(contactId, list) {
      const capped = list.length > MSG_CAP ? list.slice(list.length - MSG_CAP) : list
      this.messagesByContact = { ...this.messagesByContact, [contactId]: capped }
    },
    _appendMessages(contactId, newOnes) {
      const cur = this.messagesByContact[contactId] || []
      const seen = new Set(cur.map((m) => m.id))
      const merged = [...cur]
      for (const m of newOnes) {
        if (seen.has(m.id)) continue
        seen.add(m.id)
        merged.push(m)
      }
      merged.sort((a, b) => a.id - b.id)
      this._setMessages(contactId, merged)
    },
    _prependMessages(contactId, older) {
      const cur = this.messagesByContact[contactId] || []
      const seen = new Set(cur.map((m) => m.id))
      const merged = []
      for (const m of older) {
        if (seen.has(m.id)) continue
        merged.push(m)
      }
      merged.push(...cur)
      this._setMessages(contactId, merged)
    },
    _bumpSyncId(id) {
      if (id > this.lastSyncId) {
        this.lastSyncId = id
        saveSyncId(id)
      }
    },
    async fetchContacts(opts = {}) {
      const silent = opts.silent === true
      if (!silent) this.loadingContacts = true
      try {
        this.contacts = await listContacts()
        if (this.activeContactId && !this.contacts.some((c) => c.id === this.activeContactId)) {
          this.activeContactId = null
        }
      } finally {
        if (!silent) this.loadingContacts = false
      }
    },
    async selectContact(id) {
      this.activeContactId = id
      await this.fetchMessages()
    },
    backToList() {
      this.activeContactId = null
    },
    async fetchMessages(opts = {}) {
      const silent = opts.silent === true
      if (!this.activeContactId) return
      if (!silent) this.loadingMessages = true
      try {
        const data = await listMessages(this.activeContactId, { limit: 50 })
        this._setMessages(this.activeContactId, data.messages || [])
        this.hasMoreHistory = {
          ...this.hasMoreHistory,
          [this.activeContactId]: !!data.has_more,
        }
        for (const m of data.messages || []) this._bumpSyncId(m.id)
      } finally {
        if (!silent) this.loadingMessages = false
      }
    },
    async loadOlderMessages() {
      if (!this.activeContactId || this.loadingMore) return
      if (!this.hasMoreHistory[this.activeContactId]) return
      const cur = this.messagesByContact[this.activeContactId] || []
      if (!cur.length) return
      this.loadingMore = true
      try {
        const beforeId = cur[0].id
        const data = await listMessages(this.activeContactId, { beforeId, limit: 50 })
        this._prependMessages(this.activeContactId, data.messages || [])
        this.hasMoreHistory = {
          ...this.hasMoreHistory,
          [this.activeContactId]: !!data.has_more,
        }
      } finally {
        this.loadingMore = false
      }
    },
    async pullSync() {
      if (this.syncing) return
      this.syncing = true
      try {
        let after = this.lastSyncId
        // eslint-disable-next-line no-constant-condition
        while (true) {
          const data = await syncAfter(after)
          const msgs = data.messages || []
          const byContact = {}
          for (const m of msgs) {
            if (!byContact[m.contact_id]) byContact[m.contact_id] = []
            byContact[m.contact_id].push(m)
            this._bumpSyncId(m.id)
            after = Math.max(after, m.id)
          }
          for (const [cid, list] of Object.entries(byContact)) {
            this._appendMessages(Number(cid), list)
          }
          this._mergeTypingFromServer(
            data.typing_contact_ids || [],
            data.busy_contact_ids || data.typing_contact_ids || [],
          )
          if (data.contacts?.length) {
            this.contacts = data.contacts
          }
          const failedMap = {}
          for (const j of data.failed_jobs || []) {
            failedMap[j.contact_id] = j
          }
          this.failedJobsByContact = failedMap
          if (!data.has_more) break
        }
      } finally {
        this.syncing = false
      }
    },

    async addContact(form) {
      const contact = await createContact(form)
      await this.fetchContacts({ silent: true })
      this.activeContactId = contact.id
      this._setMessages(contact.id, [])
      return contact
    },
    async updateContact(id, payload) {
      const updated = await updateContactApi(id, payload)
      this._patchContact(updated)
      return updated
    },
    async setAvatar(contactId, file) {
      const updated = await uploadAvatar(contactId, file)
      this._patchContact(updated)
    },
    async setBackground(contactId, file, platform) {
      const updated = await uploadBackground(contactId, file, platform)
      this._patchContact(updated)
    },
    async removeBackground(contactId, platform) {
      const updated = await clearBackground(contactId, platform)
      this._patchContact(updated)
    },
    async removeContact(id) {
      await deleteContact(id)
      this.contacts = this.contacts.filter((c) => c.id !== id)
      if (this.activeContactId === id) this.activeContactId = null
      const next = { ...this.messagesByContact }
      delete next[id]
      this.messagesByContact = next
    },
    _patchContact(updated) {
      const idx = this.contacts.findIndex((c) => c.id === updated.id)
      if (idx >= 0) {
        this.contacts[idx] = { ...this.contacts[idx], ...updated }
      }
    },
    async sendMessage(text) {
      if (!this.activeContactId) return
      const content = text.trim()
      if (!content) return
      const contactId = this.activeContactId
      const tempId = `temp-u-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`
      const temp = {
        id: tempId,
        contact_id: contactId,
        role: 'user',
        content,
        created_at: new Date().toISOString(),
        _pending: true,
      }
      this._appendMessages(contactId, [temp])
      this._markTypingLocal(contactId)
      try {
        const real = await postMessage(contactId, content)
        const cur = (this.messagesByContact[contactId] || []).filter((m) => m.id !== tempId)
        this._setMessages(contactId, cur)
        this._appendMessages(contactId, [real])
        this._bumpSyncId(real.id)
        this._markTypingLocal(contactId)
      } catch (e) {
        const cur = (this.messagesByContact[contactId] || []).map((m) =>
          m.id === tempId ? { ...m, _failed: true, _pending: false } : m,
        )
        this._setMessages(contactId, cur)
        throw e
      }
    },
    async sendFile(file) {
      if (!this.activeContactId || !file) return
      const contactId = this.activeContactId
      const isImage = file.type.startsWith('image/')
      const tempId = `temp-f-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`
      const temp = {
        id: tempId,
        contact_id: contactId,
        role: 'user',
        content: isImage ? '' : `[文件] ${file.name}`,
        attachment_url: isImage ? URL.createObjectURL(file) : null,
        attachment_kind: isImage ? 'image' : 'file',
        attachment_name: file.name,
        created_at: new Date().toISOString(),
        _pending: true,
      }
      this._appendMessages(contactId, [temp])
      this._markTypingLocal(contactId)
      try {
        const real = await postMessageFile(contactId, file)
        const cur = (this.messagesByContact[contactId] || []).filter((m) => m.id !== tempId)
        this._setMessages(contactId, cur)
        this._appendMessages(contactId, [real])
        this._bumpSyncId(real.id)
        this._markTypingLocal(contactId)
      } catch (e) {
        const cur = (this.messagesByContact[contactId] || []).map((m) =>
          m.id === tempId ? { ...m, _failed: true, _pending: false } : m,
        )
        this._setMessages(contactId, cur)
        throw e
      }
    },
    async retryFailed() {
      const job = this.failedJob
      if (!job) return
      this._markTypingLocal(job.contact_id)
      await retryJob(job.id)
      await this.pullSync()
    },
  },
})
