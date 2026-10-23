import { onMounted, onUnmounted, ref, unref, watch } from 'vue'

/**
 * 自适应增量同步：
 * 有待回复/正在输入时 0.8s，空闲 10s，隐藏时暂停。
 * options.enabled：未登录时不轮询。
 */
export function useSync(store, options = {}) {
  const timer = ref(null)
  let stopped = false
  let typingTick = null

  function isEnabled() {
    const e = options.enabled
    if (e == null) return true
    return !!unref(e)
  }

  function clear() {
    if (timer.value != null) {
      clearTimeout(timer.value)
      timer.value = null
    }
  }

  function intervalMs() {
    if (
      store.needFastSync ||
      (store.busyContactIds || []).length > 0 ||
      (store.typingContactIds || []).length > 0
    ) {
      return 800
    }
    return 10000
  }

  async function tick() {
    if (stopped) return
    if (!isEnabled()) {
      schedule()
      return
    }
    if (typeof document !== 'undefined' && document.hidden) {
      schedule()
      return
    }
    try {
      await store.pullSync()
    } catch {
      /* 网络错误下次再试 */
    }
    schedule()
  }

  function schedule() {
    clear()
    if (stopped) return
    timer.value = setTimeout(tick, intervalMs())
  }

  function onVisibility() {
    if (!document.hidden && isEnabled()) {
      clear()
      tick()
    }
  }

  function onOnline() {
    if (!isEnabled()) return
    clear()
    tick()
  }

  onMounted(() => {
    stopped = false
    tick()
    document.addEventListener('visibilitychange', onVisibility)
    window.addEventListener('online', onOnline)
    typingTick = setInterval(() => {
      if (store.activeContactId && Object.keys(store.typingHoldUntil || {}).length) {
        store.typingHoldUntil = { ...store.typingHoldUntil }
      }
    }, 1000)
  })

  onUnmounted(() => {
    stopped = true
    clear()
    if (typingTick) clearInterval(typingTick)
    document.removeEventListener('visibilitychange', onVisibility)
    window.removeEventListener('online', onOnline)
  })

  watch(
    () => store.needFastSync,
    () => {
      if (store.needFastSync && isEnabled()) {
        clear()
        tick()
      }
    },
  )

  if (options.enabled != null) {
    watch(
      () => unref(options.enabled),
      (ok) => {
        if (ok) {
          clear()
          tick()
        } else {
          clear()
        }
      },
    )
  }
}
