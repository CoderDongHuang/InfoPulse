/**
 * InfoPulse — Application Entry Point
 * ====================================
 * Creates the Vue app, registers plugins: Router, Pinia, Element Plus.
 */

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import {
  ElDrawer,
  ElDropdown,
  ElDropdownItem,
  ElDropdownMenu,
  ElIcon,
  ElInput,
  ElLoading,
  ElProgress,
  ElSlider,
} from 'element-plus'
import 'element-plus/dist/index.css'
import {
  ArrowDown, ArrowLeft, ArrowRight, Clock, Collection, CollectionTag,
  Connection, CopyDocument, DataAnalysis, Delete, Download, EditPen, Files, House, InfoFilled,
  MagicStick, Menu, Plus, QuestionFilled, Refresh, Right, Search, SwitchButton,
  TopRight, TrendCharts, Warning,
} from '@element-plus/icons-vue'

import App from './App.vue'
import router from './router'
import './assets/styles/global.css'
import './assets/styles/transitions.css'
import { useUserStore } from '@/stores/user'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)
app.use(ElLoading)

const elementComponents = { ElDrawer, ElDropdown, ElDropdownItem, ElDropdownMenu, ElIcon, ElInput, ElProgress, ElSlider }
const icons = {
  ArrowDown, ArrowLeft, ArrowRight, ArrowUpRight: TopRight, Clock, Collection, CollectionTag,
  Connection, CopyDocument, DataAnalysis, Delete, Download, EditPen, Files, House, InfoFilled,
  MagicStick, Menu, Plus, QuestionFilled, Refresh, Right, Search, SwitchButton,
  TopRight, TrendCharts, Warning,
}

for (const [key, component] of Object.entries({ ...elementComponents, ...icons })) {
  app.component(key, component)
}

void useUserStore(pinia).tryRestoreSession().finally(() => app.mount('#app'))
