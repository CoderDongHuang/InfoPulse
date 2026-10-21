import { computed, ref, watch } from 'vue'
import { defineStore } from 'pinia'
import { stage3Api, type WatchedTopicData } from '@/api/stage3'
import { useUserStore } from '@/stores/user'

export interface WatchedTopic {
  id: string
  title: string
  category: string
  addedAt: string
}

const STORAGE_KEY = 'infopulse.watchlist.v1'

function readStored(): { title: string }[] {
  try {
    const value = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
    return Array.isArray(value) ? value.filter(item => item && typeof item.title === 'string' && item.title.trim()).slice(0, 30) : []
  } catch {
    return []
  }
}

export const useWatchlistStore = defineStore('watchlist', () => {
  const user = useUserStore(), items = ref<WatchedTopic[]>([]), loading = ref(false), busy = ref(false)
  const error = ref(''), legacy = ref(readStored()), importing = ref(false)
  const scope = computed(() => user.userInfo?.id || '')
  let epoch = 0, readVersion = 0
  watch(scope, () => { epoch++; readVersion++; items.value = []; loading.value = false; busy.value = false; importing.value = false; error.value = '' }, { flush: 'sync' })
  const count = computed(() => items.value.length)
  function topicItem(row: WatchedTopicData): WatchedTopic {
    return { id: row.id, title: row.name, category: row.enabled ? '已关注主题' : '已停用主题', addedAt: row.created_at }
  }
  function has(title: string) {
    return items.value.some(item => item.title === title)
  }
  function assertScope(start: number) {
    if (!scope.value || epoch !== start) throw new Error('账号已变化，请重新加载关注列表。')
  }
  async function load() {
    if (busy.value) return
    const start = epoch, version = ++readVersion
    if (!scope.value) return
    loading.value = true; error.value = ''
    try {
      const rows = await stage3Api.topics()
      assertScope(start)
      if (version === readVersion) items.value = rows.map(topicItem)
    } catch (cause) {
      if (start === epoch && version === readVersion) error.value = '关注列表加载失败，请重试。'
      throw cause
    } finally { if (start === epoch && version === readVersion) loading.value = false }
  }
  async function remove(title: string) {
    if (busy.value) return
    const row = items.value.find(item => item.title === title)
    if (!row) return
    const start = epoch
    busy.value = true; error.value = ''; readVersion++
    try {
      await stage3Api.removeTopic(row.id)
      assertScope(start)
      items.value = items.value.filter(item => item.id !== row.id)
    } catch (cause) { if (start === epoch) error.value = '取消关注失败，记录已保留，请重试。'; throw cause }
    finally { if (start === epoch) { busy.value = false; loading.value = false } }
  }
  async function add(topic: { title: string }) {
    if (busy.value) return false
    if (topic.title.length > 120) throw new Error('关注主题最多 120 个字符，请使用较短的关键词。原记录仍保留。')
    const start = epoch
    assertScope(start)
    busy.value = true; error.value = ''; readVersion++
    try {
      const row: WatchedTopicData = await stage3Api.addTopic(topic.title)
      assertScope(start)
      items.value = [topicItem(row), ...items.value.filter(item => item.id !== row.id)]
      return true
    } catch (cause) { if (start === epoch) error.value = '关注未能保存，请刷新列表后重试。'; throw cause }
    finally { if (start === epoch) { busy.value = false; loading.value = false } }
  }
  async function toggle(topic: { title: string }) {
    if (busy.value || loading.value || importing.value) return
    if (has(topic.title)) { await remove(topic.title); return false }
    return await add(topic)
  }
  async function importLegacy() {
    if (busy.value || importing.value) return
    const start = epoch
    importing.value = true
    try {
      await load()
      for (const topic of [...legacy.value]) {
        assertScope(start)
        if (!has(topic.title) && !await add(topic)) throw new Error('关注正在保存，请稍后重试导入。')
        assertScope(start)
        legacy.value = legacy.value.filter(item => item.title !== topic.title)
        localStorage.setItem(STORAGE_KEY, JSON.stringify(legacy.value))
      }
    } finally { if (start === epoch) importing.value = false }
  }
  return { items, count, has, add, remove, toggle, load, loading, busy, error, legacy, importLegacy, importing }
})
