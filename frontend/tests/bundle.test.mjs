import { test } from 'node:test'
import assert from 'node:assert/strict'
import { gzipSync } from 'node:zlib'
import { measureBundle, assertBudget } from '../scripts/check-bundle.mjs'

test('counts transitive/shared static imports and CSS once, not dynamic routes', () => {
  const assets = { 'entry.js': Buffer.from('entry'), 'vendor.js': Buffer.from('vendor'),
    'shared.js': Buffer.from('shared'), 'app.css': Buffer.from('styles') }
  const manifest = {
    entry: { isEntry: true, file: 'entry.js', css: ['app.css'], imports: ['vendor', 'shared'], dynamicImports: ['route'] },
    vendor: { file: 'vendor.js', css: ['app.css'], imports: ['shared'] },
    shared: { file: 'shared.js', imports: ['entry'] },
    route: { file: 'lazy.js' },
    second: { isEntry: true, file: 'shared.js' },
  }
  const result = measureBundle(manifest, file => assets[file])
  assert.equal(result.js.raw, 17)
  assert.equal(result.css.raw, 6)
  assert.equal(result.js.gzip, ['entry.js', 'vendor.js', 'shared.js'].reduce((sum, file) => sum + gzipSync(assets[file]).length, 0))
  assert.deepEqual(result.js.files, ['entry.js', 'shared.js', 'vendor.js'])
  assertBudget(result, { jsRaw: 17, cssRaw: 6 })
  assert.throws(() => assertBudget(result, { jsRaw: 16 }), /exceeds/)
  assert.throws(() => assertBudget(result, { jsGzip: 1 }), /exceeds/)
  assert.throws(() => assertBudget(result, { cssRaw: 5 }), /exceeds/)
})

test('fails closed on incomplete manifest and invalid budgets', () => {
  assert.throws(() => measureBundle({}, () => Buffer.alloc(1)), /No entry/)
  assert.throws(() => measureBundle({ entry: { isEntry: true, file: 'a.js', imports: ['missing'] } }, () => Buffer.alloc(1)), /Missing manifest import/)
  assert.throws(() => assertBudget({ js: {}, css: {} }, { jsRaw: 20 }), /Invalid budget/)
})
