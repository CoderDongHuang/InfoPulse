import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import vm from 'node:vm'
import ts from 'typescript'
import * as iconComponents from '@element-plus/icons-vue'

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

test('mega-menu categories cover every visible destination exactly once', () => {
  for (const isAdmin of [false, true]) {
    for (const group of nav.visibleGroups(isAdmin)) {
      const categorized = group.sections.flatMap(section => section.items.map(item => item.path))
      assert.equal(categorized.length, new Set(categorized).size)
      assert.deepEqual(new Set(categorized), new Set(group.items.map(item => item.path)))
      assert.ok(group.sections.length >= 3 && group.sections.length <= 4)
    }
  }
})

test('every navigation icon exists and is registered as an actual Vue component', () => {
  const source = readFileSync(new URL('../src/main.ts', import.meta.url), 'utf8')
  const ast = ts.createSourceFile('main.ts', source, ts.ScriptTarget.Latest, true)
  const registered = new Set()
  function visit(node) {
    if (ts.isVariableDeclaration(node) && node.name.getText(ast) === 'icons') {
      for (const property of node.initializer.properties) registered.add(property.name.getText(ast))
    }
    ts.forEachChild(node, visit)
  }
  visit(ast)
  const items = [...nav.primaryNavigation, ...nav.visibleGroups(true).flatMap(group => group.items)]
  for (const { label, icon } of [...items, { label: '个人中心', icon: 'User' }, { label: '退出登录', icon: 'SwitchButton' }]) {
    assert.ok(iconComponents[icon], `${label}: missing icon export ${icon}`)
    assert.ok(registered.has(icon), `${label}: icon ${icon} is not registered`)
  }
  const header = readFileSync(new URL('../src/components/layout/AppHeader.vue', import.meta.url), 'utf8')
  assert.match(header, /command="profile"><el-icon[^>]*><User\s*\/>/)
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
