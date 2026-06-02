/* global api */

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

const state = {
  remote: 'gdrive',
  currentPath: '',
  cache: new Map(),       // path -> Item[]
  sizeCache: new Map(),   // path -> bytes
  currentItems: [],
  pendingSizes: new Set(),
  navGen: 0,              // incremented on each navigation; stale callbacks bail out
  sortBy: 'size',         // 'size' | 'name'
  sortDir: 'desc',        // 'asc' | 'desc'
}

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------

document.addEventListener('DOMContentLoaded', () => {
  bindEvents()
  startup()
})

async function startup() {
  const prefs = await api.getPrefs()
  state.remote = prefs.rcloneRemote || 'gdrive'

  const check = await api.checkRclone()
  if (!check.ok) {
    show('setup-screen')
    return
  }

  show('browser-screen')
  await navigate(prefs.rootPath || '')
}

// ---------------------------------------------------------------------------
// Navigation
// ---------------------------------------------------------------------------

async function navigate(path) {
  state.currentPath = path
  state.navGen++
  updateBreadcrumb()
  await loadFolder(path, state.navGen)
}

function navigateUp() {
  if (state.currentPath === '') return
  const parts = state.currentPath.split('/')
  parts.pop()
  navigate(parts.join('/'))
}

async function loadFolder(path, gen) {
  if (state.cache.has(path)) {
    if (gen !== state.navGen) return
    renderItems(state.cache.get(path))
    return
  }

  showLoading(true)

  const result = await api.listFolder({ remote: state.remote, remotePath: path })
  if (gen !== state.navGen) return

  showLoading(false)

  if (!result.ok) {
    showMessage(result.error, 'error')
    return
  }

  const items = result.data.map(raw => ({
    name: raw.Name,
    path: path ? `${path}/${raw.Name}` : raw.Name,
    size: (raw.IsDir || raw.Size < 0) ? null : raw.Size,
    isDir: raw.IsDir,
    sizeResolved: !raw.IsDir,
  }))

  sortItems(items)
  state.cache.set(path, items)
  renderItems(items)
  fetchDirSizes(items, path, gen)
}

// ---------------------------------------------------------------------------
// Background size fetching
// ---------------------------------------------------------------------------

async function fetchDirSizes(items, basePath, gen) {
  const dirs = items.filter(d => d.isDir && d.size === null)
  if (dirs.length === 0) return

  // Mark all as pending immediately for the spinner
  dirs.forEach(d => {
    if (!state.sizeCache.has(d.path)) state.pendingSizes.add(d.path)
    else d.size = state.sizeCache.get(d.path)
  })

  const CONCURRENCY = 3
  const queue = dirs.filter(d => !state.sizeCache.has(d.path))

  const worker = async () => {
    while (queue.length > 0) {
      const item = queue.shift()

      if (gen !== state.navGen) return

      const result = await api.getFolderSize({ remote: state.remote, remotePath: item.path })

      state.pendingSizes.delete(item.path)
      if (gen !== state.navGen) return

      if (result.ok) {
        item.size = result.data.bytes
        item.sizeResolved = true
        state.sizeCache.set(item.path, result.data.bytes)
        // Update the cache entry too
        const cached = state.cache.get(basePath)
        if (cached) {
          const ci = cached.find(c => c.path === item.path)
          if (ci) { ci.size = item.size; ci.sizeResolved = true }
        }
      }

      updateRow(item, basePath)
    }
  }

  const workers = Array.from({ length: Math.min(CONCURRENCY, queue.length) }, worker)
  await Promise.all(workers)

  if (gen !== state.navGen) return

  // Final sort & re-render with all resolved sizes
  const cached = state.cache.get(basePath)
  if (cached) {
    sortItems(cached)
    renderItems(cached)
  }
}

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

function renderItems(items) {
  state.currentItems = items
  const list = el('item-list')
  list.innerHTML = ''

  if (items.length === 0) {
    list.innerHTML = '<div class="empty-msg">Empty folder</div>'
    updateStatus()
    return
  }

  const maxSize = maxKnownSize(items)

  items.forEach(item => list.appendChild(makeRow(item, maxSize)))
  updateStatus()
}

function makeRow(item, maxSize) {
  const row = document.createElement('div')
  row.className = `item-row ${item.isDir ? 'is-dir' : 'is-file'}`
  row.dataset.itemPath = item.path

  const icon = item.isDir ? '▶' : '·'
  const { sizeText, sizeClass } = sizeDisplay(item)
  const barW = item.size !== null ? Math.max(1, Math.round((item.size / maxSize) * 100)) : 0

  row.innerHTML = `
    <span class="item-icon">${icon}</span>
    <span class="item-name">${esc(item.name)}</span>
    <div class="item-bar-wrap col-bar">
      <div class="item-bar" style="width:${barW}%"></div>
    </div>
    <span class="item-size col-size${sizeClass ? ' ' + sizeClass : ''}">${sizeText}</span>
  `

  if (item.isDir) {
    row.addEventListener('dblclick', () => navigate(item.path))
  }

  return row
}

function updateRow(item, basePath) {
  const list = el('item-list')
  const row = list.querySelector(`[data-item-path="${CSS.escape(item.path)}"]`)
  if (!row) return

  const items = state.cache.get(basePath) || []
  const maxSize = maxKnownSize(items)
  const barW = item.size !== null ? Math.max(1, Math.round((item.size / maxSize) * 100)) : 0
  const { sizeText, sizeClass } = sizeDisplay(item)

  const barEl = row.querySelector('.item-bar')
  const sizeEl = row.querySelector('.item-size')

  if (barEl) barEl.style.width = `${barW}%`
  if (sizeEl) {
    sizeEl.textContent = sizeText
    sizeEl.className = `item-size col-size${sizeClass ? ' ' + sizeClass : ''}`
  }

  updateStatus()
}

// ---------------------------------------------------------------------------
// Breadcrumb
// ---------------------------------------------------------------------------

function updateBreadcrumb() {
  const path = state.currentPath
  const parts = path ? path.split('/') : []
  const remote = state.remote

  let html = ''
  let accumulated = ''

  if (parts.length === 0) {
    html = `<span class="crumb crumb-current">${esc(remote + ':')}</span>`
  } else {
    html += `<span class="crumb crumb-link" data-nav-path="">${esc(remote + ':')}</span>`
    html += `<span class="crumb-sep">›</span>`

    for (let i = 0; i < parts.length; i++) {
      accumulated = accumulated ? `${accumulated}/${parts[i]}` : parts[i]
      const isLast = i === parts.length - 1
      if (isLast) {
        html += `<span class="crumb crumb-current">${esc(parts[i])}</span>`
      } else {
        html += `<span class="crumb crumb-link" data-nav-path="${accumulated}">${esc(parts[i])}</span>`
        html += `<span class="crumb-sep">›</span>`
      }
    }
  }

  const bc = el('breadcrumb')
  bc.innerHTML = html
  bc.querySelectorAll('[data-nav-path]').forEach(span => {
    span.addEventListener('click', () => navigate(span.dataset.navPath))
  })

  el('up-btn').disabled = path === ''
}

// ---------------------------------------------------------------------------
// Status bar
// ---------------------------------------------------------------------------

function updateStatus() {
  const items = state.currentItems
  const known = items.filter(i => i.size !== null)
  const total = known.reduce((s, i) => s + i.size, 0)
  const pending = state.pendingSizes.size
  const pendingNote = pending > 0 ? `  (${pending} folder${pending > 1 ? 's' : ''} calculating…)` : ''
  el('status-bar').textContent =
    `${items.length} item${items.length !== 1 ? 's' : ''}  ·  ${formatSize(total)} known${pendingNote}`
}

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------

function openSettings() {
  api.getPrefs().then(prefs => {
    el('remote-input').value = prefs.rcloneRemote || 'gdrive'
    el('root-path-input').value = prefs.rootPath || ''
    show('settings-overlay')
  })
}

function closeSettings() { hide('settings-overlay') }

async function saveSettings() {
  const remote = el('remote-input').value.trim() || 'gdrive'
  const rootPath = el('root-path-input').value.trim()
  await api.setPrefs({ rcloneRemote: remote, rootPath })
  state.remote = remote
  state.cache.clear()
  state.sizeCache.clear()
  closeSettings()
  await navigate(rootPath)
}

// ---------------------------------------------------------------------------
// Event wiring
// ---------------------------------------------------------------------------

function bindEvents() {
  el('up-btn').addEventListener('click', navigateUp)
  el('settings-btn').addEventListener('click', openSettings)
  el('settings-save-btn').addEventListener('click', saveSettings)
  el('settings-cancel-btn').addEventListener('click', closeSettings)
  el('sort-name').addEventListener('click', () => setSort('name'))
  el('sort-size').addEventListener('click', () => setSort('size'))
  updateSortHeaders()

  // Setup screen
  el('setup-docs-btn').addEventListener('click', () =>
    api.openExternal('https://rclone.org/install/')
  )
  el('setup-retry-btn').addEventListener('click', startup)

  document.addEventListener('keydown', e => {
    if (isInputActive()) return
    if (e.key === 'Backspace') navigateUp()
    if (e.key === 'Escape') closeSettings()
  })
}

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

function sortItems(items) {
  items.sort((a, b) => {
    // Dirs always above files regardless of sort column
    if (a.isDir !== b.isDir) return a.isDir ? -1 : 1

    if (state.sortBy === 'name') {
      const cmp = a.name.localeCompare(b.name, undefined, { sensitivity: 'base' })
      return state.sortDir === 'asc' ? cmp : -cmp
    }

    // sort by size
    const sa = a.size ?? -1
    const sb = b.size ?? -1
    return state.sortDir === 'desc' ? sb - sa : sa - sb
  })
}

function setSort(by) {
  if (state.sortBy === by) {
    state.sortDir = state.sortDir === 'desc' ? 'asc' : 'desc'
  } else {
    state.sortBy = by
    state.sortDir = by === 'size' ? 'desc' : 'asc'
  }
  updateSortHeaders()
  // Re-sort current view and cached copy
  sortItems(state.currentItems)
  const cached = state.cache.get(state.currentPath)
  if (cached) sortItems(cached)
  renderItems(state.currentItems)
}

function updateSortHeaders() {
  const arrow = state.sortDir === 'desc' ? ' ▼' : ' ▲'
  const nameEl = el('sort-name')
  const sizeEl = el('sort-size')
  nameEl.textContent = 'Name' + (state.sortBy === 'name' ? arrow : '')
  sizeEl.textContent = 'Size' + (state.sortBy === 'size' ? arrow : '')
  nameEl.classList.toggle('sort-active', state.sortBy === 'name')
  sizeEl.classList.toggle('sort-active', state.sortBy === 'size')
}

function maxKnownSize(items) {
  return Math.max(...items.map(i => i.size ?? 0), 1)
}

function sizeDisplay(item) {
  if (item.size !== null) return { sizeText: formatSize(item.size), sizeClass: '' }
  if (state.pendingSizes.has(item.path)) return { sizeText: '…', sizeClass: 'size-pending' }
  return { sizeText: '—', sizeClass: '' }
}

function formatSize(bytes) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
  const exp = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  const val = bytes / Math.pow(1024, exp)
  return `${val.toFixed(exp > 0 ? 1 : 0)} ${units[exp]}`
}

function esc(str) {
  return str
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}

function el(id) { return document.getElementById(id) }

function show(id) {
  el(id).classList.remove('hidden')
}

function hide(id) {
  el(id).classList.add('hidden')
}

function showLoading(on) {
  el('loading').classList.toggle('hidden', !on)
  el('item-list').classList.toggle('hidden', on)
}

function showMessage(msg, type = 'info') {
  el('item-list').innerHTML = `<div class="${type}-msg">${esc(msg)}</div>`
  el('item-list').classList.remove('hidden')
}

function isInputActive() {
  const tag = document.activeElement?.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA'
}
