import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import './styles/wechat-theme.css'
import './styles/global.css'
import './styles/mobile.css'

createApp(App).use(createPinia()).mount('#app')
