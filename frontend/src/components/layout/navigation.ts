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
  return navigationGroups.map(group => {
    const items = group.items.filter(item => !item.adminOnly || isAdmin)
    return { ...group, items, sections: navigationSections.map(section => ({
      label: section.label, description: section.description,
      items: items.filter(item => section.paths.includes(item.path)),
    })).filter(section => section.items.length) }
  })
}

// One destination belongs to one category; desktop and mobile use the same data.
export const navigationSections = [
  { label: '寻找信号', description: '从信息检索到事件追踪', paths: ['/search', '/events', '/alerts'] },
  { label: '分析与问答', description: '围绕问题理解信息', paths: ['/analysis', '/agent', '/bi'] },
  { label: '沉淀知识', description: '积累证据与研究成果', paths: ['/knowledge', '/reports'] },
  { label: '工作流与执行', description: '组织任务，跟进行动', paths: ['/orchestration', '/action-loop', '/tasks'] },
  { label: '情报与决策', description: '连接多种信息视角', paths: ['/multimodal', '/global-intelligence'] },
  { label: '订阅与动态', description: '持续关注重要变化', paths: ['/subscriptions', '/notifications', '/watchlist', '/history'] },
  { label: '数据与工具', description: '管理来源，探索内容', paths: ['/sources', '/insight', '/timeline', '/mouthpiece', '/hot-search'] },
  { label: '组织与平台', description: '组织管理与开放集成', paths: ['/enterprise', '/developers', '/commercial-operations', '/help', '/admin'] },
  { label: '治理实验室', description: '规则计算与治理探索', paths: ['/autonomy', '/trust-network', '/global-coordination', '/adaptive-os'] },
  { label: '前沿实验室', description: '探索中的能力与模型', paths: ['/provable-autonomy', '/planetary-resilience', '/cognitive-infrastructure', '/cognitive-commons'] },
]
export function isActivePath(current: string, target: string) {
  return current === target || (target !== '/' && current.startsWith(target + '/'))
}
