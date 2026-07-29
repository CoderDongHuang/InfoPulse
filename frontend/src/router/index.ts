/**
 * InfoPulse — Vue Router Configuration
 * =====================================
 * Route definitions + navigation guard for auth.
 */

import {
  createRouter,
  createWebHistory,
  type RouteRecordRaw,
} from "vue-router";
import { useUserStore } from "@/stores/user";

const routes: RouteRecordRaw[] = [
  {
    path: "/",
    name: "Home",
    component: () => import("@/views/HomeView.vue"),
    meta: { title: "Workspace", requiresAuth: true },
  },
  {
    path: "/dashboard",
    name: "Dashboard",
    component: () => import("@/views/DashboardView.vue"),
    meta: { title: "Dashboard", requiresAuth: true },
  },
  {
    path: "/discover",
    name: "Discover",
    component: () => import("@/views/DiscoverView.vue"),
    meta: { title: "Discover", requiresAuth: true },
  },
  {
    path: "/analysis",
    name: "Analysis",
    component: () => import("@/views/AnalysisView.vue"),
    meta: { title: "AI 分析", requiresAuth: true },
  },
  {
    path: "/agent",
    name: "Agent",
    component: () => import("@/views/AgentView.vue"),
    meta: { title: "AI Agent", requiresAuth: true },
  },
  {
    path: "/reports",
    name: "Reports",
    component: () => import("@/views/ReportsView.vue"),
    meta: { title: "报告中心", requiresAuth: true },
  },
  {
    path: "/reports/:id",
    name: "ReportEditor",
    component: () => import("@/views/ReportEditorView.vue"),
    meta: { title: "报告编辑器", requiresAuth: true },
  },
  {
    path: "/subscriptions",
    name: "Subscriptions",
    component: () => import("@/views/SubscriptionsView.vue"),
    meta: { title: "订阅中心", requiresAuth: true },
  },
  {
    path: "/tasks",
    name: "Tasks",
    component: () => import("@/views/TasksView.vue"),
    meta: { title: "任务中心", requiresAuth: true },
  },
  {
    path: "/notifications",
    name: "Notifications",
    component: () => import("@/views/NotificationsView.vue"),
    meta: { title: "通知中心", requiresAuth: true },
  },
  {
    path: "/knowledge",
    name: "Knowledge",
    component: () => import("@/views/KnowledgeView.vue"),
    meta: { title: "知识库", requiresAuth: true },
  },
  {
    path: "/auth",
    name: "Auth",
    component: () => import("@/views/AuthView.vue"),
    meta: { title: "登录", guest: true },
  },
  { path: "/alerts", name: "Alerts", component: () => import("@/views/AlertsView.vue"), meta: { title: "预警中心", requiresAuth: true } },
  { path: "/bi", name: "ControlledBI", component: () => import("@/views/BIView.vue"), meta: { title: "自然语言 BI", requiresAuth: true } },
  { path: "/admin", name: "AdminOperations", component: () => import("@/views/AdminView.vue"), meta: { title: "运行管理", requiresAuth: true, adminOnly: true } },
  { path: "/enterprise", name: "EnterpriseGovernance", component: () => import("@/views/EnterpriseView.vue"), meta: { title: "企业治理", requiresAuth: true } },
  { path: "/developers", name: "DeveloperPlatform", component: () => import("@/views/DeveloperPlatformView.vue"), meta: { title: "开发者平台", requiresAuth: true } },
  { path: "/orchestration", name: "AgentOrchestration", component: () => import("@/views/OrchestrationView.vue"), meta: { title: "Agent 编排", requiresAuth: true } },
  { path: "/help", name: "Help", component: () => import("@/views/HelpView.vue"), meta: { title: "帮助中心", requiresAuth: true } },
  {
    path: "/insight",
    name: "Insight",
    component: () => import("@/views/insight/InsightView.vue"),
    meta: { title: "热点洞察", requiresAuth: true },
  },
  { path: "/anti-scam", redirect: "/insight" },
  {
    path: "/mouthpiece",
    name: "Mouthpiece",
    component: () => import("@/views/mouthpiece/MouthpieceView.vue"),
    meta: { title: "表达工作室", requiresAuth: true },
  },
  {
    path: "/timeline",
    name: "Timeline",
    component: () => import("@/views/timeline/TimelineView.vue"),
    meta: { title: "事件脉络", requiresAuth: true },
  },
  {
    path: "/hot-search",
    name: "HotSearch",
    component: () => import("@/views/HotSearchView.vue"),
    meta: { title: "真实情报信号榜" },
  },
  {
    path: "/history",
    name: "History",
    component: () => import("@/views/HistoryView.vue"),
    meta: { title: "历史报告", requiresAuth: true },
  },
  {
    path: "/watchlist",
    name: "Watchlist",
    component: () => import("@/views/WatchlistView.vue"),
    meta: { title: "关注话题" },
  },
  {
    path: "/search",
    name: "Search",
    component: () => import("@/views/SearchView.vue"),
    meta: { title: "搜索中心", requiresAuth: true },
  },
  {
    path: "/events",
    name: "Events",
    component: () => import("@/views/EventsView.vue"),
    meta: { title: "事件中心", requiresAuth: true },
  },
  {
    path: "/events/:id",
    name: "EventDetail",
    component: () => import("@/views/EventDetailView.vue"),
    meta: { title: "事件详情", requiresAuth: true },
  },
  { path: "/events/:id/graph", name: "EventGraph", component: () => import("@/views/GraphView.vue"), meta: { title: "知识图谱与传播路径", requiresAuth: true } },
  {
    path: "/sources",
    name: "Sources",
    component: () => import("@/views/SourcesView.vue"),
    meta: { title: "数据源中心", requiresAuth: true },
  },
  {
    path: "/:pathMatch(.*)*",
    redirect: "/",
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 }),
});

// --- Navigation Guard ---
router.beforeEach(async (to, _from, next) => {
  // Update document title
  document.title = `${to.meta.title || "InfoPulse"} — InfoPulse`;

  const userStore = useUserStore();

  // If route requires auth and user is not logged in
  if (to.meta.requiresAuth && !userStore.isLoggedIn) {
    next({ path: "/auth", query: { redirect: to.fullPath } });
    return;
  }

  // If user is already logged in and visits auth page
  if (to.meta.guest && userStore.isLoggedIn) {
    next({ path: "/" });
    return;
  }

  if (to.meta.adminOnly) {
    if (!userStore.userInfo && userStore.isLoggedIn) {
      try { await userStore.fetchUserInfo() } catch { userStore.logout() }
    }
    if (!userStore.userInfo?.is_admin) {
      next({ path: "/" })
      return
    }
  }

  next();
});

export default router;
