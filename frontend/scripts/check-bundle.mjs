import { readFileSync, writeFileSync } from 'node:fs'
import { resolve, relative, isAbsolute } from 'node:path'
import { pathToFileURL } from 'node:url'
import { gzipSync, brotliCompressSync } from 'node:zlib'

// Bytes, not rounded kB. Budget covers the union of ALL static entry imports.
// Route dynamic imports and image assets are explicitly outside this budget.
export const limits = { jsRaw: 600000, jsGzip: 200000, cssRaw: 160000 }

export function measureBundle(manifest, readAsset) {
  const entries = Object.keys(manifest).filter(key => manifest[key].isEntry)
  if (!entries.length) throw new Error('No entry found in Vite manifest')
  const seen = new Set(), files = new Set()
  function visit(key) {
    if (seen.has(key)) return
    const chunk = manifest[key]
    if (!chunk?.file) throw new Error('Missing manifest import: ' + key)
    seen.add(key)
    files.add(chunk.file)
    for (const css of chunk.css || []) files.add(css)
    for (const dependency of chunk.imports || []) visit(dependency)
  }
  entries.forEach(visit)
  const report = { entries, js: { files: [], raw: 0, gzip: 0, brotli: 0 }, css: { files: [], raw: 0, gzip: 0, brotli: 0 } }
  for (const file of [...files].sort()) {
    const kind = file.endsWith('.js') ? 'js' : file.endsWith('.css') ? 'css' : null
    if (!kind) continue
    const bytes = readAsset(file)
    report[kind].files.push(file)
    report[kind].raw += bytes.length
    report[kind].gzip += gzipSync(bytes).length
    report[kind].brotli += brotliCompressSync(bytes).length
  }
  if (!report.js.files.length) throw new Error('No entry JavaScript measured')
  return report
}

export function assertBudget(report, budget = limits) {
  const actual = { jsRaw: report.js.raw, jsGzip: report.js.gzip, cssRaw: report.css.raw }
  for (const [metric, limit] of Object.entries(budget)) {
    if (!Number.isFinite(limit) || !Number.isFinite(actual[metric])) throw new Error('Invalid budget metric: ' + metric)
    if (actual[metric] > limit) throw new Error(metric + ': ' + actual[metric] + ' exceeds ' + limit)
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(resolve(process.argv[1])).href) {
  const dist = resolve('dist')
  const manifest = JSON.parse(readFileSync(resolve(dist, '.vite/manifest.json'), 'utf8'))
  const report = measureBundle(manifest, file => {
    const target = resolve(dist, file), inside = relative(dist, target)
    if (isAbsolute(file) || isAbsolute(inside) || inside === '..' || inside.startsWith('..' + '/')
        || inside.startsWith('..' + '\\')) throw new Error('Asset escapes dist: ' + file)
    return readFileSync(target)
  })
  writeFileSync(resolve(dist, 'bundle-budget.json'), JSON.stringify({ ...report, limits }, null, 2) + '\n')
  console.log(JSON.stringify({ ...report, limits }, null, 2))
  assertBudget(report)
}
