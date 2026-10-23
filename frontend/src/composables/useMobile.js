import { onMounted, onUnmounted, ref } from 'vue'

/** 与微信移动端类似的窄屏断点 */
export const MOBILE_BREAKPOINT = 768

/**
 * 监听视口是否为移动端宽度。
 */
export function useMobile() {
  const mq = () => window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT}px)`)
  const isMobile = ref(typeof window !== 'undefined' ? mq().matches : false)

  function update() {
    isMobile.value = mq().matches
  }

  onMounted(() => {
    update()
    window.addEventListener('resize', update)
  })

  onUnmounted(() => {
    window.removeEventListener('resize', update)
  })

  return { isMobile }
}
