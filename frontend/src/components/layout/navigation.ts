export interface NavItem { path: string; label: string; icon: string; adminOnly?: boolean }
export const primaryNavigation: NavItem[] = [
  { path: '/', label: '工作台', icon: 'House' },
  { path: '/dashboard', label: '数据概览', icon: 'TrendCharts' },
  { path: '/discover', label: '发现', icon: 'Compass' },
]
export const navigationGroups: { label: string; items: NavItem[] }[] = [
  { label: '研究分析', items: [
    { path: '/search', label: '搜索中心', icon: 'Search' },
    { path: '/events', label: '事件中心', icon: 'Collection' },
    { path: '/analysis', label: 'AI 分析', icon: 'MagicStick' },
    { path: '/agent', label: 'AI Agent', icon: 'ChatDotRound' },
    { path: '/knowledge', label: '知识库', icon: 'FolderOpened' },
    { path: '/reports', label: '报告中心', icon: 'Document' },
    { path: '/alerts', label: '预警中心', icon: 'Warning' },
    { path: '/bi', label: '自然语言 BI', icon: 'TrendCharts' },
  ] },
  { label: '协作与行动', items: [
    { path: '/orchestration', label: 'Agent 编排', icon: 'Share' },
    { path: '/multimodal', label: '多模态情报', icon: 'VideoCamera' },
    { path: '/global-intelligence', label: '全球情报与决策', icon: 'LocationInformation' },
    { path: '/action-loop', label: '行动闭环', icon: 'CircleCheck' },
    { path: '/subscriptions', label: '订阅中心', icon: 'Bell' },
    { path: '/tasks', label: '任务中心', icon: 'Timer' },
    { path: '/notifications', label: '通知中心', icon: 'Message' },
    { path: '/watchlist', label: '关注话题', icon: 'CollectionTag' },
    { path: '/history', label: '历史报告', icon: 'Files' },
  ] },
  { label: '平台与工具', items: [
    { path: '/sources', label: '数据源中心', icon: 'Collection' },
    { path: '/enterprise', label: '企业治理', icon: 'Lock' },
    { path: '/developers', label: '开发者平台', icon: 'Monitor' },
    { path: '/commercial-operations', label: '商业运营', icon: 'DataAnalysis' },
    { path: '/autonomy', label: '自治与合规', icon: 'CircleCheck' },
    { path: '/trust-network', label: '可信网络', icon: 'Connection' },
    { path: '/global-coordination', label: '全球协同', icon: 'Share' },
    { path: '/adaptive-os', label: '自适应 OS', icon: 'Cpu' },
    { path: '/provable-autonomy', label: '可证明自治', icon: 'DocumentChecked' },
    { path: '/planetary-resilience', label: '行星韧性', icon: 'Aim' },
    { path: '/cognitive-infrastructure', label: '认知基建', icon: 'SetUp' },
    { path: '/cognitive-commons', label: '认知公地', icon: 'Connection' },
    { path: '/insight', label: '热点洞察', icon: 'DataAnalysis' },
    { path: '/timeline', label: '事件脉络', icon: 'Clock' },
    { path: '/mouthpiece', label: '表达工具', icon: 'EditPen' },
    { path: '/hot-search', label: '兼容热搜', icon: 'Search' },
    { path: '/help', label: '帮助中心', icon: 'QuestionFilled' },
    { path: '/admin', label: '运行管理', icon: 'Setting', adminOnly: true },
  ] },
]

export function visibleGroups(isAdmin: boolean) {
  return navigationGroups.map(group => ({ ...group, items: group.items.filter(item => !item.adminOnly || isAdmin) }))
}
export function isActivePath(current: string, target: string) {
  return current === target || (target !== '/' && current.startsWith(target + '/'))
}
