import 'element-plus/dist/index.css'
import './styles.css'

import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import { createPinia } from 'pinia'
import { createApp } from 'vue'

import App from './App.vue'
import { setupRouter } from './router'

const pinia = createPinia()
createApp(App).use(pinia).use(setupRouter(pinia)).use(ElementPlus, { locale: zhCn }).mount('#app')
