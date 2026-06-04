/* global api */

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

const state = {
  screen: 'setup',
  setup: { rcloneVersion: null, hasGdrive: false, hasGphotos: false, error: null },
  config: { drivePath: '', driveRemote: 'gdrive', photosRemote: 'gphotos', includePhotos: true },
  scan:   { phase: null, scanned: 0, total: null, currentFile: '' },
  results: { groups: [], selected: new Set(), totalRecoverable: 0, selectedBytes: 0 },
  scanGen: 0,
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
  state.config.driveRemote  = prefs.driveRemote  || 'gdrive'
  state.config.photosRemote = prefs.photosRemote || 'gphotos'
  state.config.drivePath    = prefs.drivePath    || ''
  state.config.includePhotos = prefs.includePhotos !== false

  const check = await api.checkSetup()
  state.setup = { ...check }

  if (!check.ok || !check.hasGdrive) {
    renderSetupScreen(check)
    showScreen('setup')
    return
  }

  renderConfigScreen()
  showScreen('config')
}

// ---------------------------------------------------------------------------
// Setup screen
// ---------------------------------------------------------------------------

function renderSetupScreen(check) {
  el('setup-rclone-missing').classList.toggle('hidden', check.ok !== false || check.hasGdrive !== undefined)
  el('setup-gdrive-missing').classList.toggle('hidden', check.ok && !check.hasGdrive ? false : true)
  el('setup-gphotos-missing').classList.toggle('hidden', check.hasGphotos !== false)

  if (!check.ok) {
    el('setup-rclone-missing').classList.remove('hidden')
    el('setup-gdrive-missing').classList.add('hidden')
    el('setup-gphotos-missing').classList.add('hidden')
  } else if (!check.hasGdrive) {
    el('setup-rclone-missing').classList.add('hidden')
    el('setup-gdrive-missing').classList.remove('hidden')
    el('setup-gphotos-missing').classList.add('hidden')
  } else if (!check.hasGphotos) {
    el('setup-rclone-missing').classList.add('hidden')
    el('setup-gdrive-missing').classList.add('hidden')
    el('setup-gphotos-missing').classList.remove('hidden')
    el('setup-continue-btn').classList.remove('hidden')
  }
}

// ---------------------------------------------------------------------------
// Config screen
// ---------------------------------------------------------------------------

function renderConfigScreen() {
  el('config-drive-remote').value  = state.config.driveRemote
  el('config-drive-path').value    = state.config.drivePath
  el('config-photos-remote').value = state.config.photosRemote
  el('config-include-photos').checked = state.config.includePhotos
  el('config-rclone-ver').textContent = state.setup.rcloneVersion || ''

  const hasPh = state.setup.hasGphotos
  el('config-photos-badge').classList.toggle('hidden', !hasPh)
  el('config-photos-remote-label').classList.toggle('hidden', !el('config-include-photos').checked)

  if (state.setup.rcloneVersion) {
    el('config-rclone-ver').textContent = state.setup.rcloneVersion
  }
}

// ---------------------------------------------------------------------------
// Scan
// ---------------------------------------------------------------------------

async function startScan() {
  const driveRemote  = el('config-drive-remote').value.trim()  || 'gdrive'
  const drivePath    = el('config-drive-path').value.trim()
  const photosRemote = el('config-photos-remote').value.trim() || 'gphotos'
  const includePhotos = el('config-include-photos').checked

  await api.setPrefs({ driveRemote, drivePath, photosRemote, includePhotos })
  state.config = { driveRemote, drivePath, photosRemote, includePhotos }

  state.scanGen++
  const gen = state.scanGen

  api.offScanListeners()
  api.onScanProgress(data => { if (gen === state.scanGen) handleProgress(data) })
  api.onScanDone(data     => { if (gen === state.scanGen) handleDone(data) })

  // Reset progress UI
  el('scan-phase').textContent = 'Starting…'
  el('scan-file').textContent  = ''
  el('scan-count').textContent = ''
  el('scan-bar').style.width   = '0%'
  el('scan-bar').classList.add('progress-bar-indeterminate')

  showScreen('scanning')
  api.startScan({ drivePath, includePhotos, driveRemote, photosRemote })
}

function handleProgress(data) {
  if (data.phase === 'listing') {
    const sourceLabel = data.source === 'drive' ? 'Google Drive' : 'Google Photos'
    el('scan-phase').textContent = `Scanning ${sourceLabel}…`
    el('scan-file').textContent  = data.currentFile || ''

    if (data.total !== null && data.total > 0) {
      el('scan-bar').classList.remove('progress-bar-indeterminate')
      el('scan-bar').style.width = `${Math.round((data.scanned / data.total) * 100)}%`
      el('scan-count').textContent = `${data.scanned.toLocaleString()} / ${data.total.toLocaleString()} photos`
    } else {
      el('scan-bar').classList.add('progress-bar-indeterminate')
      if (data.scanned > 0) el('scan-count').textContent = `${data.scanned.toLocaleString()} photos found`
    }
  } else if (data.phase === 'grouping') {
    el('scan-phase').textContent = 'Finding duplicates…'
    el('scan-file').textContent  = data.currentFile || ''
    el('scan-bar').classList.remove('progress-bar-indeterminate')
    el('scan-bar').style.width = '100%'
    el('scan-count').textContent = `${data.total.toLocaleString()} photos scanned`
  }
}

function handleDone(data) {
  if (!data.ok) {
    if (data.error && data.error.includes('cancelled')) {
      showScreen('config')
      return
    }
    showScreen('results')
    el('group-list').innerHTML = `<div class="error-msg">Scan failed: ${esc(data.error)}</div>`
    el('results-summary').textContent = 'Scan failed'
    return
  }

  state.results.groups = data.groups || []
  state.results.selected = new Set()

  const recoverable = state.results.groups
    .flatMap(g => g.files.filter(f => f.canDelete))
    .reduce((s, f) => s + f.size, 0)
  state.results.totalRecoverable = recoverable

  el('results-summary').textContent =
    `${state.results.groups.length} duplicate group${state.results.groups.length !== 1 ? 's' : ''} · ${formatSize(recoverable)} recoverable`

  renderResultsScreen()
  showScreen('results')
}

// ---------------------------------------------------------------------------
// Results screen
// ---------------------------------------------------------------------------

function renderResultsScreen() {
  const list = el('group-list')
  list.innerHTML = ''

  if (state.results.groups.length === 0) {
    list.innerHTML = '<div class="empty-msg">No duplicate photos found.<br>Try scanning a different folder or check your Google Photos remote.</div>'
    return
  }

  state.results.groups.forEach((group, idx) => {
    list.appendChild(makeGroupCard(group, idx))
  })

  updateDeleteFooter()
}

function makeGroupCard(group) {
  const recoverable = group.files
    .filter(f => f.canDelete)
    .reduce((s, f) => s + f.size, 0)

  const card = document.createElement('div')
  card.className = 'group-card'
  card.dataset.groupId = group.id

  // Header
  const header = document.createElement('div')
  header.className = 'group-header'
  header.innerHTML = `
    <span class="group-norm-name">${esc(group.normName)}</span>
    ${recoverable > 0 ? `<span class="group-recoverable">-${formatSize(recoverable)}</span>` : ''}
    <button class="verify-btn" data-group="${esc(group.id)}">Verify ▶</button>
  `
  card.appendChild(header)

  // File rows
  group.files.forEach(file => {
    card.appendChild(makeFileRow(file, group.id))
  })

  return card
}

function makeFileRow(file, groupId) {
  const row = document.createElement('div')
  row.className = 'file-row'
  row.dataset.key = `${file.remote}:${file.path}`

  const sourceLabel = file.remote === state.config.driveRemote ? 'Drive' : 'Photos'
  const sourceCls   = file.remote === state.config.driveRemote ? 'badge-drive' : 'badge-photos'
  const keepBadge   = file.isKeep ? `<span class="badge badge-keep">Keep</span>` : ''
  const verifiedEl  = verifiedBadge(file)
  const checkDisabled = (!file.canDelete || file.isKeep) ? 'disabled' : ''

  row.innerHTML = `
    <div class="thumb-placeholder" data-key="${esc(row.dataset.key)}">🖼</div>
    <div class="file-info">
      <span class="file-name">${esc(file.name)}</span>
      <div class="file-meta">
        <span class="badge ${sourceCls}">${sourceLabel}</span>
        <span class="file-size">${formatSize(file.size)}</span>
        ${keepBadge}
        ${verifiedEl}
      </div>
      <span class="file-path-dim">${esc(file.path)}</span>
    </div>
    <input type="checkbox" class="delete-check" ${checkDisabled}
      data-key="${esc(row.dataset.key)}" data-group="${esc(groupId)}">
  `

  // If thumb already loaded (after verify), swap placeholder for img
  if (file.thumbPath) swapThumb(row, file.thumbPath, row.dataset.key)

  return row
}

function verifiedBadge(file) {
  if (file.hashVerified === true)  return `<span class="verified-match">✓ Confirmed duplicate</span>`
  if (file.hashVerified === false) return `<span class="verified-nomatch">✗ Different photo</span>`
  if (file.hashVerified === 'unsupported') return `<span class="verified-unknown">Size comparison only (HEIC)</span>`
  return ''
}

function swapThumb(row, thumbPath, key) {
  const placeholder = row.querySelector(`[data-key="${CSS.escape(key)}"]`)
  if (!placeholder) return
  const img = document.createElement('img')
  img.className = 'thumb'
  img.src = `file://${thumbPath}`
  img.onerror = () => { /* keep placeholder on load error */ }
  placeholder.replaceWith(img)
}

// ---------------------------------------------------------------------------
// Verify
// ---------------------------------------------------------------------------

async function onVerifyClick(groupId) {
  const group = state.results.groups.find(g => g.id === groupId)
  if (!group || group.files.length < 2) return

  const btn = el('group-list').querySelector(`[data-group="${CSS.escape(groupId)}"].verify-btn`)
  if (btn) { btn.disabled = true; btn.textContent = 'Verifying…' }

  // Use first two files in group for pHash comparison
  const [fileA, fileB] = group.files

  const result = await api.verifyPair({
    fileA: { remote: fileA.remote, path: fileA.path, name: fileA.name },
    fileB: { remote: fileB.remote, path: fileB.path, name: fileB.name },
  })

  if (!result.ok) {
    if (btn) { btn.disabled = false; btn.textContent = `Error: ${result.error.slice(0, 40)}` }
    return
  }

  // Update file records with thumb paths and verification result
  if (result.thumbA) fileA.thumbPath = result.thumbA
  if (result.thumbB) fileB.thumbPath = result.thumbB

  if (result.unsupported) {
    fileA.hashVerified = 'unsupported'
    fileB.hashVerified = 'unsupported'
  } else {
    fileA.hashVerified = result.match
    fileB.hashVerified = result.match
  }

  // Re-render the card
  const card = el('group-list').querySelector(`[data-group-id="${CSS.escape(groupId)}"]`)
  if (card) {
    const newCard = makeGroupCard(group)
    card.replaceWith(newCard)
    bindCardEvents(newCard)
  }
}

// ---------------------------------------------------------------------------
// Checkboxes + delete footer
// ---------------------------------------------------------------------------

function onDeleteCheckChange(key, checked) {
  const [remote, ...pathParts] = key.split(':')
  const path = pathParts.join(':')

  if (checked) {
    state.results.selected.add(key)
  } else {
    state.results.selected.delete(key)
  }
  updateDeleteFooter()
}

function updateDeleteFooter() {
  const footer = el('delete-footer')
  const sel = state.results.selected

  if (sel.size === 0) {
    footer.classList.add('hidden')
    return
  }

  footer.classList.remove('hidden')

  // Calculate bytes of selected
  let bytes = 0
  state.results.groups.forEach(g => {
    g.files.forEach(f => {
      if (sel.has(`${f.remote}:${f.path}`)) bytes += f.size
    })
  })
  state.results.selectedBytes = bytes

  el('delete-count').textContent =
    `${sel.size} file${sel.size !== 1 ? 's' : ''} selected · ${formatSize(bytes)}`
}

// ---------------------------------------------------------------------------
// Delete flow
// ---------------------------------------------------------------------------

function openDeleteModal() {
  const list = el('delete-modal-list')
  list.innerHTML = ''

  state.results.selected.forEach(key => {
    const li = document.createElement('li')
    li.textContent = key
    list.appendChild(li)
  })

  el('delete-modal').classList.remove('hidden')
}

async function confirmDelete() {
  el('delete-modal').classList.add('hidden')
  el('delete-btn').disabled = true

  const files = []
  state.results.selected.forEach(key => {
    const colon = key.indexOf(':')
    files.push({ remote: key.slice(0, colon), path: key.slice(colon + 1) })
  })

  const result = await api.deleteFiles(files)

  const deletedPaths = new Set(
    result.results.filter(r => r.ok).map(r => r.path)
  )

  // Remove successfully deleted files from groups
  state.results.groups.forEach(group => {
    group.files = group.files.filter(f => !deletedPaths.has(f.path))
  })
  state.results.groups = state.results.groups.filter(g => g.files.length >= 2)
  state.results.selected = new Set()

  // Recalculate recoverable
  const recoverable = state.results.groups
    .flatMap(g => g.files.filter(f => f.canDelete))
    .reduce((s, f) => s + f.size, 0)

  el('results-summary').textContent =
    `${state.results.groups.length} group${state.results.groups.length !== 1 ? 's' : ''} · ${formatSize(recoverable)} recoverable`

  el('delete-btn').disabled = false
  renderResultsScreen()
}

// ---------------------------------------------------------------------------
// Event binding
// ---------------------------------------------------------------------------

function bindEvents() {
  el('setup-retry-btn').addEventListener('click', startup)
  el('setup-continue-btn').addEventListener('click', () => {
    state.setup.hasGphotos = false
    renderConfigScreen()
    showScreen('config')
  })
  el('setup-docs-btn').addEventListener('click',  () => api.openExternal('https://rclone.org/install/'))
  el('setup-docs-btn2').addEventListener('click', () => api.openExternal('https://rclone.org/googlephotos/'))

  el('config-include-photos').addEventListener('change', (e) => {
    el('config-photos-remote-label').classList.toggle('hidden', !e.target.checked)
  })

  el('start-scan-btn').addEventListener('click', startScan)
  el('cancel-scan-btn').addEventListener('click', async () => {
    await api.cancelScan()
    showScreen('config')
  })

  el('results-back-btn').addEventListener('click', () => showScreen('config'))
  el('delete-btn').addEventListener('click', openDeleteModal)
  el('delete-cancel-btn').addEventListener('click', () => el('delete-modal').classList.add('hidden'))
  el('delete-confirm-btn').addEventListener('click', confirmDelete)

  // Event delegation for group-list (verify buttons + checkboxes)
  el('group-list').addEventListener('click', (e) => {
    const verifyBtn = e.target.closest('.verify-btn')
    if (verifyBtn) { onVerifyClick(verifyBtn.dataset.group); return }
  })

  el('group-list').addEventListener('change', (e) => {
    if (e.target.classList.contains('delete-check')) {
      onDeleteCheckChange(e.target.dataset.key, e.target.checked)
    }
  })

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') el('delete-modal').classList.add('hidden')
  })
}

function bindCardEvents(card) {
  // Cards created after initial render need verify-btn wired — handled via delegation above
  // Checkboxes also handled via delegation; nothing extra needed here
}

// ---------------------------------------------------------------------------
// Screen management
// ---------------------------------------------------------------------------

function showScreen(name) {
  const screens = { setup: 'setup-screen', config: 'config-screen', scanning: 'scanning-screen', results: 'results-screen' }
  Object.values(screens).forEach(id => el(id).classList.add('hidden'))
  el(screens[name]).classList.remove('hidden')
  state.screen = name
}

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

function formatSize(bytes) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const exp = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  const val = bytes / Math.pow(1024, exp)
  return `${val.toFixed(exp > 0 ? 1 : 0)} ${units[exp]}`
}

function esc(str) {
  return String(str)
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}

function el(id) { return document.getElementById(id) }
