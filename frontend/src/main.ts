/**
 * InfoPulse — Application Entry Point
 * ====================================
 * Creates the Vue app, registers plugins: Router, Pinia, Element Plus.
 */

import { createApp } from "vue";
import { createPinia } from "pinia";
import ElementPlus from "element-plus";
import "element-plus/dist/index.css";
import {
  Aim,
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  Bell,
  Check,
  Clock,
  Close,
  Collection,
  CollectionTag,
  Connection,
  CopyDocument,
  DataAnalysis,
  Delete,
  Document,
  Download,
  EditPen,
  Files,
  House,
  InfoFilled,
  List,
  MagicStick,
  Menu,
  Message,
  Plus,
  QuestionFilled,
  Refresh,
  RefreshRight,
  Right,
  Search,
  Setting,
  SwitchButton,
  Timer,
  TopRight,
  TrendCharts,
  VideoPause,
  VideoPlay,
  Warning,
  FolderOpened,
  Upload,
  Link,
} from "@element-plus/icons-vue";

import App from "./App.vue";
import router from "./router";
import "./assets/styles/global.css";
import "./assets/styles/transitions.css";
import { useUserStore } from "@/stores/user";

const app = createApp(App);
const pinia = createPinia();

app.use(pinia);
app.use(router);
app.use(ElementPlus);
const icons = {
  Aim,
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  ArrowUpRight: TopRight,
  Bell,
  Check,
  Clock,
  Close,
  Collection,
  CollectionTag,
  Connection,
  CopyDocument,
  DataAnalysis,
  Delete,
  Document,
  Download,
  EditPen,
  Files,
  House,
  InfoFilled,
  List,
  MagicStick,
  Menu,
  Message,
  Plus,
  QuestionFilled,
  Refresh,
  RefreshRight,
  Right,
  Search,
  Setting,
  SwitchButton,
  Timer,
  TopRight,
  TrendCharts,
  VideoPause,
  VideoPlay,
  Warning,
  FolderOpened,
  Upload,
  Link,
};

for (const [key, component] of Object.entries({
  ...icons,
})) {
  app.component(key, component);
}

void useUserStore(pinia)
  .tryRestoreSession()
  .finally(() => app.mount("#app"));
