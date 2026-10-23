import { onMounted, onUnmounted, ref, watch } from 'vue'

/**
 * 自适应增量同步：
 * 有待回复/正在输入时 0.8s，空闲 10s，隐藏时暂停。
 * isTyping 依赖时间 hold，定时刷新以保证最短展示结束后能关掉提示。
 */
export function useSync(store) {
  const timer = ref(null)
  let stopped = false
  let typingTick = null

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
    if (!document.hidden) {
      clear()
      tick()
    }
  }

  function onOnline() {
    clear()
    tick()
  }

  onMounted(() => {
    stopped = false
    tick()
    document.addEventListener('visibilitychange', onVisibility)
    window.addEventListener('online', onOnline)
    // 每秒刷新一次，让 typingHold 到期后标题提示能消失
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
      if (store.needFastSync) {
        clear()
        tick()
      }
    },
  )
}
