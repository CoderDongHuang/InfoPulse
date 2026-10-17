/**
 * InfoPulse — Application Entry Point
 * ====================================
 * Creates the Vue app, registers plugins: Router, Pinia, Element Plus.
 */

import { createApp } from "vue";
import { createPinia } from "pinia";
import { installElement } from "./plugins/element";
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
  ChatDotRound,
  Compass,
  Connection,
  Cpu,
  CopyDocument,
  DataAnalysis,
  Delete,
  Document,
  DocumentChecked,
  Download,
  EditPen,
  Files,
  House,
  InfoFilled,
  List,
  LocationInformation,
  MagicStick,
  Menu,
  Message,
  Plus,
  QuestionFilled,
  Refresh,
  RefreshRight,
  Right,
  Search,
  SetUp,
  Share,
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
  User,
  VideoCamera,
  CircleCheck,
  Lock,
  Monitor,
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
installElement(app);
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
  ChatDotRound,
  Compass,
  Connection,
  Cpu,
  CopyDocument,
  DataAnalysis,
  Delete,
  Document,
  DocumentChecked,
  Download,
  EditPen,
  Files,
  House,
  InfoFilled,
  List,
  LocationInformation,
  MagicStick,
  Menu,
  Message,
  Plus,
  QuestionFilled,
  Refresh,
  RefreshRight,
  Right,
  Search,
  SetUp,
  Share,
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
  User,
  VideoCamera,
  CircleCheck,
  Lock,
  Monitor,
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
