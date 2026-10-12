import { createPinia } from 'pinia'
import { createApp } from 'vue'

import App from './App.vue'
import { setupRouter } from './router'

const pinia = createPinia()
createApp(App).use(pinia).use(setupRouter(pinia)).mount('#app')
