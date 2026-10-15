import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import ts from 'typescript'

function moduleAt(path) {
  const source = readFileSync(new URL(path, import.meta.url), 'utf8')
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText
  const context = { exports: {}, URL }
  vm.runInNewContext(code, context)
  return context.exports
}
const nav = moduleAt('../src/components/layout/navigation.ts')
const profile = moduleAt('../src/utils/profile.ts')
const saved = { username: 'existing', email: 'existing@example.com', avatar_url: '' }

test('navigation retains every static destination, with profile in account menu', () => {
  const source = readFileSync(new URL('../src/router/index.ts', import.meta.url), 'utf8')
  const paths = [...source.matchAll(/path:\s*['"]([^'"]+)['"]/g)].map(match => match[1])
  const navigation = [...nav.primaryNavigation, ...nav.visibleGroups(true).flatMap(g => g.items)]
  const expected = new Set(paths.filter(path => !path.includes(':') && !['/auth', '/profile', '/anti-scam'].includes(path)))
  assert.deepEqual(new Set(navigation.map(item => item.path)), expected)
  assert.equal(navigation.length, expected.size, 'destinations must not be duplicated')
  assert.equal(nav.visibleGroups(false).flatMap(g => g.items).some(item => item.path === '/admin'), false)
})

test('nested route highlights parent without confusing path prefixes', () => {
  assert.equal(nav.isActivePath('/reports/123', '/reports'), true)
  assert.equal(nav.isActivePath('/events/123/graph', '/events'), true)
  assert.equal(nav.isActivePath('/reports-other', '/reports'), false)
  assert.equal(nav.isActivePath('/profile', '/'), false)
})

test('profile sends only changed fields, preserving unchanged legacy usernames', () => {
  assert.equal(JSON.stringify(profile.profilePatch({ ...saved }, saved)), '{}')
  const legacy = { ...saved, username: 'legacy@name' }
  const patch = profile.profilePatch({ ...legacy, email: ' New@Example.com ' }, legacy)
  assert.equal(JSON.stringify(patch), JSON.stringify({ email: 'new@example.com' }))
  assert.equal(profile.profilePatch({ ...saved, username: ' renamed ' }, saved).username, 'renamed')
  assert.equal(profile.profilePatch(saved, { ...saved, avatar_url: 'https://example.com/old.png' }).avatar_url, '')
})

test('profile rejects invalid changed fields and unrenderable avatar URLs', () => {
  for (const username of ['x', 'x@y', 'x'.repeat(51)]) assert.throws(() => profile.profilePatch({ ...saved, username }, saved))
  for (const avatar_url of ['javascript:alert(1)', 'data:image/png;base64,x', '/relative.png', 'https://user:pass@example.com/a']) {
    assert.equal(profile.safeAvatarUrl(avatar_url), '')
    assert.throws(() => profile.profilePatch({ ...saved, avatar_url }, saved))
  }
  assert.equal(profile.safeAvatarUrl('https://example.com/a.png'), 'https://example.com/a.png')
})

test('late profile response cannot replace the account after session changes', async () => {
  const source = readFileSync(new URL('../src/stores/user.ts', import.meta.url), 'utf8')
  const ast = ts.createSourceFile('user.ts', source, ts.ScriptTarget.Latest, true)
  let method
  function visit(node) { if (ts.isFunctionDeclaration(node) && node.name?.text === 'updateProfile') method = node.getText(ast); ts.forEachChild(node, visit) }
  visit(ast)
  assert.ok(method)
  let release
  const previous = { username: 'new-account' }
  const context = { sessionEpoch: 1, userInfo: { value: previous }, authApi: { updateMe: () => new Promise(resolve => { release = resolve }) } }
  vm.runInNewContext(ts.transpileModule(method, { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText, context)
  const result = context.updateProfile({ username: 'old-account' })
  context.sessionEpoch++
  release({ username: 'old-account' })
  await assert.rejects(result, /会话已变化/)
  assert.equal(context.userInfo.value, previous)
})
