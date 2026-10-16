<template>
  <footer class="app-footer">
    <a href="https://github.com/CoderDongHuang" target="_blank" rel="noopener noreferrer" aria-label="CoderDongHuang 的 GitHub 主页">CoderDongHuang <span aria-hidden="true">↗</span></a>
    <span>汇聚公开信号，让信息成为洞察。</span>
  </footer>
</template>

<style scoped>
.app-footer { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px 24px; min-height: 48px; padding: 12px 24px; box-sizing: border-box; border-top: 1px solid var(--border-color); background: #fff; font-size: 12px; color: var(--text-secondary); }
.app-footer a { color: #475569; font-weight: 600; }
.app-footer a:hover { color: #2563eb; }
.app-footer a:focus-visible { outline: 2px solid #2563eb; outline-offset: 4px; border-radius: 2px; }
@media (max-width: 600px) { .app-footer { padding: 14px 16px; flex-direction: column; align-items: flex-start; } }
</style>
