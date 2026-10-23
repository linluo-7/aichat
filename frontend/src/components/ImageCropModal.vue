<script setup>
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import Cropper from 'cropperjs'
import 'cropperjs/dist/cropper.css'
import { MOBILE_BREAKPOINT } from '../composables/useMobile'

const props = defineProps({
  src: { type: String, required: true },
  aspectRatio: { type: Number, default: 1 },
  title: { type: String, default: '裁剪图片' },
  maxWidth: { type: Number, default: 1024 },
  maxHeight: { type: Number, default: 1024 },
  /** 竖屏背景裁剪：移动端占满可视区域 */
  portraitCrop: { type: Boolean, default: false },
})

const emit = defineEmits(['confirm', 'cancel'])

const imgRef = ref(null)
const stageRef = ref(null)
const processing = ref(false)
const isNarrow = ref(false)
let cropper = null

function updateNarrow() {
  isNarrow.value = window.innerWidth <= MOBILE_BREAKPOINT
}

function destroyCropper() {
  cropper?.destroy()
  cropper = null
}

function onResize() {
  updateNarrow()
  cropper?.resize()
}

async function initCropper() {
  await nextTick()
  destroyCropper()
  if (!imgRef.value || !props.src) return
  const ratio = props.aspectRatio
  cropper = new Cropper(imgRef.value, {
    aspectRatio: Number.isNaN(ratio) ? NaN : ratio,
    viewMode: 1,
    dragMode: 'move',
    autoCropArea: props.portraitCrop ? 1 : 0.92,
    responsive: true,
    background: false,
    zoomOnWheel: !isNarrow.value,
    zoomOnTouch: true,
    movable: true,
    scalable: false,
    guides: true,
    center: true,
    highlight: true,
  })
}

watch(
  () => props.src,
  (v) => {
    if (v) initCropper()
    else destroyCropper()
  },
  { immediate: true },
)

onMounted(() => {
  updateNarrow()
  window.addEventListener('resize', onResize)
  window.addEventListener('orientationchange', onResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', onResize)
  window.removeEventListener('orientationchange', onResize)
  destroyCropper()
})

function onCancel() {
  emit('cancel')
}

function onConfirm() {
  if (!cropper || processing.value) return
  processing.value = true
  try {
    const canvas = cropper.getCroppedCanvas({
      maxWidth: props.maxWidth,
      maxHeight: props.maxHeight,
      imageSmoothingEnabled: true,
      imageSmoothingQuality: 'high',
    })
    canvas.toBlob(
      (blob) => {
        processing.value = false
        if (!blob) return
        const file = new File([blob], 'cropped.jpg', { type: 'image/jpeg', lastModified: Date.now() })
        emit('confirm', file)
      },
      'image/jpeg',
      0.9,
    )
  } catch {
    processing.value = false
  }
}
</script>

<template>
  <div
    class="crop-mask"
    :class="{ 'is-portrait': portraitCrop, 'is-narrow': isNarrow }"
    role="dialog"
    aria-modal="true"
  >
    <div class="crop-panel">
      <header class="crop-head">
        <button type="button" class="crop-head-btn" @click="onCancel">取消</button>
        <h2 class="crop-title">{{ title }}</h2>
        <button type="button" class="crop-head-btn primary" :disabled="processing" @click="onConfirm">
          {{ processing ? '处理中…' : '完成' }}
        </button>
      </header>
      <div ref="stageRef" class="crop-stage">
        <img ref="imgRef" :src="src" alt="" class="crop-source" />
      </div>
      <p class="crop-tip">
        {{ portraitCrop ? '双指缩放、拖动图片，竖框内为聊天背景区域' : '拖动、缩放图片，框选需要保留的区域' }}
      </p>
    </div>
  </div>
</template>

<style scoped>
.crop-mask {
  position: fixed;
  inset: 0;
  z-index: 2000;
  background: #111;
  display: flex;
  flex-direction: column;
  padding: env(safe-area-inset-top, 0px) env(safe-area-inset-right, 0px)
    env(safe-area-inset-bottom, 0px) env(safe-area-inset-left, 0px);
}

.crop-panel {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.crop-head {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  height: 48px;
  padding: 0 4px;
  color: #fff;
}

.crop-title {
  margin: 0;
  font-size: 16px;
  font-weight: 500;
  max-width: 46vw;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.crop-head-btn {
  min-width: 64px;
  height: 40px;
  border: none;
  background: none;
  color: #ccc;
  font-size: 15px;
  cursor: pointer;
}

.crop-head-btn.primary {
  color: var(--wx-green, #07c160);
  font-weight: 500;
}

.crop-head-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.crop-stage {
  flex: 1;
  min-height: 240px;
  background: #000;
  overflow: hidden;
  touch-action: none;
}

.crop-source {
  display: block;
  max-width: 100%;
}

.crop-tip {
  flex-shrink: 0;
  margin: 0;
  padding: 10px 16px 14px;
  text-align: center;
  font-size: 12px;
  color: #888;
  line-height: 1.45;
}

.crop-mask.is-portrait.is-narrow .crop-stage {
  min-height: 0;
  flex: 1;
}

.crop-mask.is-portrait.is-narrow .crop-tip {
  padding-bottom: calc(14px + env(safe-area-inset-bottom, 0px));
}
</style>
