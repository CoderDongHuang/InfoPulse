import { computed, ref } from 'vue'
import { defineStore } from 'pinia'

export interface WatchedTopic {
  title: string
  category: string
  heat: number
  sourceUrl: string
  addedAt: string
}

const STORAGE_KEY = 'infopulse.watchlist.v1'

function readStored(): WatchedTopic[] {
  try {
    const value = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
    return Array.isArray(value) ? value.slice(0, 30) : []
  } catch {
    return []
  }
}

export const useWatchlistStore = defineStore('watchlist', () => {
  const items = ref<WatchedTopic[]>(readStored())
  const count = computed(() => items.value.length)

  function persist() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(items.value))
  }

  function has(title: string) {
    return items.value.some(item => item.title === title)
  }

  function add(topic: Partial<WatchedTopic> & { title: string }) {
    if (has(topic.title)) return false
    items.value.unshift({
      title: topic.title,
      category: topic.category || '未分类',
      heat: Number(topic.heat || 0),
      sourceUrl: topic.sourceUrl || '',
      addedAt: new Date().toISOString(),
    })
    items.value = items.value.slice(0, 30)
    persist()
    return true
  }

  function remove(title: string) {
    items.value = items.value.filter(item => item.title !== title)
    persist()
  }

  function toggle(topic: Partial<WatchedTopic> & { title: string }) {
    if (has(topic.title)) {
      remove(topic.title)
      return false
    }
    add(topic)
    return true
  }

  return { items, count, has, add, remove, toggle }
})
