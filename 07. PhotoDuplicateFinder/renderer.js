/* global api */

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

const state = {
  screen: 'setup',
  setup: { rcloneVersion: null, hasGdrive: false, hasGphotos: false, error: null },
  config: { drivePath: '', driveRemote: 'gdrive', photosRemote: 'gphotos', includePhotos: true },
  scan:   { phase: null, scanned: 0, total: null, currentFile: '' },
  results: { groups: [], toDelete: new Set(), toKeep: new Set(), totalRecoverable: 0 },
  scanGen: 0,
}

let thumbLoadGen = 0

const folderBrowser = { currentPath: '' }

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------

document.addEventListener('DOMContentLoaded', () => {
  bindEvents()
  startup()
})

async function startup() {
  const prefs = await api.getPrefs()
  state.config.driveRemote   = prefs.driveRemote  || 'gdrive'
  state.config.photosRemote  = prefs.photosRemote || 'gphotos'
  state.config.drivePath     = prefs.drivePath    || ''
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
  el('config-drive-remote').value   = state.config.driveRemote
  el('config-drive-path').value     = state.config.drivePath
  el('config-photos-remote').value  = state.config.photosRemote
  el('config-include-photos').checked = state.config.includePhotos
  el('config-rclone-ver').textContent = state.setup.rcloneVersion || ''

  const hasPh = state.setup.hasGphotos
  el('config-photos-badge').classList.toggle('hidden', !hasPh)
  el('config-photos-remote-label').classList.toggle('hidden', !el('config-include-photos').checked)

  if (state.config.includePhotos) refreshCatalogInfo()
}

let catalogInfoTimer = null
function refreshCatalogInfo() {
  clearTimeout(catalogInfoTimer)
  catalogInfoTimer = setTimeout(async () => {
    const remote = el('config-photos-remote').value.trim() || 'gphotos'
    const info = await api.getCatalogInfo({ photosRemote: remote })
    renderCatalogInfo(info)
  }, 200)
}

function renderCatalogInfo(info) {
  const row = el('catalog-info-row')
  const txt = el('catalog-info-text')

  if (!el('config-include-photos').checked) {
    row.classList.add('hidden')
    return
  }

  row.classList.remove('hidden')

  if (!info.exists) {
    txt.textContent = 'No catalog cached — first scan will fetch it from Google Photos'
    txt.className = 'catalog-info-text catalog-info-warn'
    return
  }

  const ageH  = Math.floor(info.ageMs / 3_600_000)
  const ageM  = Math.floor((info.ageMs % 3_600_000) / 60_000)
  const ageStr = ageH >= 24 ? `${Math.floor(ageH / 24)}d ${ageH % 24}h` : ageH > 0 ? `${ageH}h ${ageM}m` : `${ageM}m`
  const count = info.fileCount.toLocaleString()

  if (info.ageMs < 24 * 3_600_000) {
    txt.textContent = `Catalog cached ${ageStr} ago · ${count} photos`
    txt.className = 'catalog-info-text catalog-info-ok'
  } else {
    txt.textContent = `Catalog cached ${ageStr} ago · ${count} photos (may be stale)`
    txt.className = 'catalog-info-text catalog-info-warn'
  }
}

// ---------------------------------------------------------------------------
// Folder browser
// ---------------------------------------------------------------------------

async function openFolderBrowser() {
  el('folder-modal').dataset.target = ''
  folderBrowser.currentPath = el('config-drive-path').value.trim()
  updateFolderBreadcrumb(folderBrowser.currentPath)
  el('folder-modal').classList.remove('hidden')
  await loadFolderItems(folderBrowser.currentPath)
}

function closeFolderBrowser(select) {
  if (select) {
    const target = el('folder-modal').dataset.target
    const targetInput = target === 'thumb-cache' ? 'thumb-cache-folder' : 'config-drive-path'
    el(targetInput).value = folderBrowser.currentPath
    if (target === 'thumb-cache') refreshThumbCacheInfo()
  }
  el('folder-modal').dataset.target = ''
  el('folder-modal').classList.add('hidden')
}

async function loadFolderItems(folderPath) {
  const remote = el('config-drive-remote').value.trim() || 'gdrive'
  const items  = el('folder-items')
  items.innerHTML = '<div class="folder-loading">Loading…</div>'

  const result = await api.listDriveFolders({ remote, folderPath })
  items.innerHTML = ''

  if (!result.ok) {
    items.innerHTML = `<div class="folder-item-error">Error: ${esc(result.error)}</div>`
    return
  }

  if (result.folders.length === 0) {
    items.innerHTML = '<div class="folder-empty-msg">No subfolders here</div>'
    return
  }

  result.folders.forEach(name => {
    const fullPath = folderPath ? `${folderPath}/${name}` : name
    const div = document.createElement('div')
    div.className = 'folder-item'
    div.innerHTML = `<span class="folder-icon">📁</span>${esc(name)}`
    div.addEventListener('click', async () => {
      folderBrowser.currentPath = fullPath
      updateFolderBreadcrumb(fullPath)
      await loadFolderItems(fullPath)
    })
    items.appendChild(div)
  })
}

function updateFolderBreadcrumb(folderPath) {
  const crumb = el('folder-breadcrumb')
  crumb.innerHTML = ''

  const root = document.createElement('span')
  root.className = 'breadcrumb-item' + (folderPath === '' ? ' breadcrumb-current' : '')
  root.textContent = 'My Drive'
  if (folderPath !== '') {
    root.addEventListener('click', async () => {
      folderBrowser.currentPath = ''
      updateFolderBreadcrumb('')
      await loadFolderItems('')
    })
  }
  crumb.appendChild(root)

  if (folderPath) {
    const parts = folderPath.split('/')
    let cumPath = ''
    parts.forEach((part, i) => {
      cumPath = cumPath ? `${cumPath}/${part}` : part
      const sep = document.createElement('span')
      sep.className = 'breadcrumb-sep'
      sep.textContent = ' › '
      crumb.appendChild(sep)

      const isCurrent = i === parts.length - 1
      const item = document.createElement('span')
      item.className = 'breadcrumb-item' + (isCurrent ? ' breadcrumb-current' : '')
      item.textContent = part
      if (!isCurrent) {
        const p = cumPath
        item.addEventListener('click', async () => {
          folderBrowser.currentPath = p
          updateFolderBreadcrumb(p)
          await loadFolderItems(p)
        })
      }
      crumb.appendChild(item)
    })
  }

  const selectBtn = el('folder-select-btn')
  if (selectBtn) {
    selectBtn.textContent = folderPath
      ? `Select "${folderPath.split('/').pop()}"`
      : 'Select (entire Drive)'
  }
}

// ---------------------------------------------------------------------------
// Scan
// ---------------------------------------------------------------------------

async function startScan() {
  const driveRemote   = el('config-drive-remote').value.trim()  || 'gdrive'
  const drivePath     = el('config-drive-path').value.trim()
  const photosRemote  = el('config-photos-remote').value.trim() || 'gphotos'
  const includePhotos = el('config-include-photos').checked

  await api.setPrefs({ driveRemote, drivePath, photosRemote, includePhotos })
  state.config = { driveRemote, drivePath, photosRemote, includePhotos }

  state.scanGen++
  const gen = state.scanGen

  api.offScanListeners()
  api.onScanProgress(data => { if (gen === state.scanGen) handleProgress(data) })
  api.onScanDone(data     => { if (gen === state.scanGen) handleDone(data) })

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

  state.results.groups   = data.groups || []
  state.results.toDelete = new Set()
  state.results.toKeep   = new Set()

  // Keep is checked by default for every file EXCEPT duplicate candidates (canDelete && !isKeep)
  state.results.groups.forEach(g =>
    g.files.forEach(f => {
      if (!(f.canDelete && !f.isKeep)) state.results.toKeep.add(`${f.remote}:${f.path}`)
    })
  )

  const recoverable = state.results.groups
    .flatMap(g => g.files.filter(f => f.canDelete))
    .reduce((s, f) => s + f.size, 0)
  state.results.totalRecoverable = recoverable

  el('results-summary').textContent =
    `${state.results.groups.length} duplicate group${state.results.groups.length !== 1 ? 's' : ''} · ${formatSize(recoverable)} recoverable`

  el('filter-score').value = ''
  el('filter-same-name').checked = false
  el('filter-count').textContent = ''

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

  state.results.groups.forEach(group => list.appendChild(makeGroupCard(group)))
  updateDeleteFooter()
  startEagerThumbLoad()

  const minScore     = parseInt(el('filter-score').value) || 0
  const sameNameOnly = el('filter-same-name').checked
  if (minScore > 0 || sameNameOnly) applyFilter()
}

// ---------------------------------------------------------------------------
// Group card
// ---------------------------------------------------------------------------

function makeGroupCard(group) {
  const recoverable = group.files
    .filter(f => f.canDelete)
    .reduce((s, f) => s + f.size, 0)

  const card = document.createElement('div')
  card.className = 'group-card'
  card.dataset.groupId = group.id

  const header = document.createElement('div')
  header.className = 'group-header'
  header.innerHTML = `
    <span class="group-norm-name">${esc(group.normName)}</span>
    ${recoverable > 0 ? `<span class="group-recoverable">-${formatSize(recoverable)}</span>` : ''}
    ${group.score !== undefined ? makeScoreBadgeHtml(group.score) : ''}
    <button class="verify-btn" data-group="${esc(group.id)}">${group.verified ? 'Re-verify ▶' : 'Verify ▶'}</button>
  `
  card.appendChild(header)

  // Column headers aligned with Keep/Delete checkboxes in file rows
  const colHdr = document.createElement('div')
  colHdr.className = 'files-col-headers'
  colHdr.innerHTML = `
    <div class="files-col-headers-spacer"></div>
    <div class="files-col-headers-info"></div>
    <div class="files-check-col-headers">
      <span class="files-col-header">Keep</span>
      <span class="files-col-header">Delete</span>
    </div>
  `
  card.appendChild(colHdr)

  group.files.forEach(file => card.appendChild(makeFileRow(file, group)))

  if (group.breakdown) card.appendChild(makeBreakdownEl(group.breakdown, group.score))

  return card
}

function makeScoreBadgeHtml(score) {
  const cls = score >= 75 ? 'score-badge-green' : score >= 50 ? 'score-badge-orange' : 'score-badge-red'
  return `<span class="score-badge ${cls}">${score}</span>`
}

// ---------------------------------------------------------------------------
// File row
// ---------------------------------------------------------------------------

function makeFileRow(file, group) {
  const row = document.createElement('div')
  row.className = 'file-row'
  const key = `${file.remote}:${file.path}`
  row.dataset.key = key

  const sourceLabel = file.remote === state.config.driveRemote ? 'Drive' : 'Photos'
  const sourceCls   = file.remote === state.config.driveRemote ? 'badge-drive' : 'badge-photos'
  const scoreBadge  = verifiedBadge(group)
  const selected    = state.results.toKeep.has(key) ? 'keep'
                    : state.results.toDelete.has(key) ? 'delete'
                    : 'none'

  row.innerHTML = `
    <div class="thumb-placeholder" data-key="${esc(key)}">🖼</div>
    <div class="file-info">
      <span class="file-name">${esc(file.name)}</span>
      <div class="file-meta">
        <span class="badge ${sourceCls}">${sourceLabel}</span>
        <span class="file-size">${formatSize(file.size)}</span>
        ${scoreBadge}
      </div>
      <span class="file-path-dim">${esc(file.path)}</span>
    </div>
    <div class="radio-cols" data-selected="${selected}">
      <input type="radio" name="choice-${esc(key)}" class="keep-radio" value="keep"
             ${selected === 'keep' ? 'checked' : ''} data-key="${esc(key)}">
      <input type="radio" name="choice-${esc(key)}" class="delete-radio" value="delete"
             ${selected === 'delete' ? 'checked' : ''} data-key="${esc(key)}" data-group="${esc(group.id)}">
      <input type="radio" name="choice-${esc(key)}" class="none-radio" value="none"
             ${selected === 'none' ? 'checked' : ''} data-key="${esc(key)}" style="display:none">
    </div>
  `

  if (file.thumbPath) swapThumb(row, file.thumbPath, key, file.name)
  return row
}

function verifiedBadge(group) {
  if (group.score === undefined) return ''
  const score = group.score
  const cls   = score >= 75 ? 'score-badge-green' : score >= 50 ? 'score-badge-orange' : 'score-badge-red'
  return `<span class="score-badge score-badge-sm ${cls}">${score}% match</span>`
}

// ---------------------------------------------------------------------------
// Breakdown table
// ---------------------------------------------------------------------------

function makeBreakdownEl(breakdown, score) {
  const div = document.createElement('div')
  div.className = 'breakdown-section'

  const rows = breakdown.map(row => {
    if (row.na) {
      return `
        <div class="breakdown-row">
          <span class="breakdown-signal">${esc(row.signal)}</span>
          <div class="breakdown-bar-wrap"><div class="breakdown-bar" style="width:0%"></div></div>
          <span class="breakdown-pts breakdown-na">N/A</span>
        </div>`
    }
    const pct = Math.round((row.score / row.max) * 100)
    const ptsCls = row.score === row.max ? 'breakdown-full'
                 : row.score > 0 ? 'breakdown-partial' : 'breakdown-zero'
    return `
      <div class="breakdown-row">
        <span class="breakdown-signal">${esc(row.signal)}</span>
        <div class="breakdown-bar-wrap"><div class="breakdown-bar" style="width:${pct}%"></div></div>
        <span class="breakdown-pts ${ptsCls}">${row.score}/${row.max}</span>
      </div>`
  }).join('')

  div.innerHTML = `
    <div class="breakdown-header">Score breakdown · total ${score}/100</div>
    <div class="breakdown-rows">${rows}</div>
  `
  return div
}

// ---------------------------------------------------------------------------
// Thumbnails — eager loading + lightbox
// ---------------------------------------------------------------------------

const THUMB_BATCH = 3

function makeThumbImg(thumbPath, name) {
  const img = document.createElement('img')
  img.className = 'thumb'
  img.src = `file://${thumbPath}`
  img.title = name
  img.style.cursor = 'zoom-in'
  img.addEventListener('click', () => openLightbox(thumbPath, name))
  img.onerror = () => {}
  return img
}

function swapThumb(row, thumbPath, key, name) {
  const placeholder = row.querySelector(`[data-key="${CSS.escape(key)}"]`)
  if (!placeholder) return
  placeholder.replaceWith(makeThumbImg(thumbPath, name || key))
}

function startEagerThumbLoad() {
  const gen = ++thumbLoadGen
  const files = []
  state.results.groups.forEach(g => {
    g.files.forEach(f => { if (!f.thumbPath) files.push(f) })
  })

  ;(async () => {
    for (let i = 0; i < files.length; i += THUMB_BATCH) {
      if (gen !== thumbLoadGen) return
      await Promise.all(files.slice(i, i + THUMB_BATCH).map(async f => {
        if (gen !== thumbLoadGen) return
        const key = `${f.remote}:${f.path}`
        const result = await api.fetchThumb({ remote: f.remote, filePath: f.path, name: f.name })
        if (gen !== thumbLoadGen) return
        if (result.ok) {
          f.thumbPath = result.thumbPath
          const row = el('group-list').querySelector(`.file-row[data-key="${CSS.escape(key)}"]`)
          if (row) {
            const ph = row.querySelector('.thumb-placeholder')
            if (ph) ph.replaceWith(makeThumbImg(result.thumbPath, f.name))
          }
        }
      }))
    }
  })()
}

// ---------------------------------------------------------------------------
// Lightbox
// ---------------------------------------------------------------------------

function openLightbox(thumbPath, caption) {
  el('lightbox-img').src = `file://${thumbPath}`
  el('lightbox-caption').textContent = caption || ''
  el('lightbox').classList.remove('hidden')
}

function closeLightbox() {
  el('lightbox').classList.add('hidden')
  el('lightbox-img').src = ''
}

// ---------------------------------------------------------------------------
// Verify
// ---------------------------------------------------------------------------

const VERIFY_WARN_THRESHOLD = 15
const VERIFY_PARTIAL_COUNT  = 20

async function onVerifyAllClick() {
  const groups = state.results.groups.filter(g => g.files.length >= 2 && !g.verified)
  if (groups.length === 0) {
    const btn = el('verify-all-btn')
    if (btn) {
      btn.textContent = 'All verified!'
      setTimeout(() => { btn.textContent = 'Verify All' }, 2000)
    }
    return
  }
  if (groups.length > VERIFY_WARN_THRESHOLD) {
    el('verify-all-modal-msg').textContent =
      `You have ${groups.length} unverified groups. Verifying all may take several minutes — each group downloads photo metadata.`
    el('verify-all-partial-btn').textContent = `Verify first ${VERIFY_PARTIAL_COUNT}`
    el('verify-all-modal').classList.remove('hidden')
    return
  }
  await verifyAllGroups(groups)
}

async function verifyAllGroups(groups) {
  const btn = el('verify-all-btn')
  if (btn) btn.disabled = true

  for (let i = 0; i < groups.length; i++) {
    if (btn) btn.textContent = `Verifying ${i + 1}/${groups.length}…`
    await onVerifyClick(groups[i].id)
  }

  if (btn) { btn.disabled = false; btn.textContent = 'Verify All' }

  const minScore    = parseInt(el('filter-score').value) || 0
  const sameNameOnly = el('filter-same-name').checked
  if (minScore > 0 || sameNameOnly) applyFilter()
}

async function onVerifyClick(groupId) {
  const group = state.results.groups.find(g => g.id === groupId)
  if (!group || group.files.length < 2) return

  const btn = el('group-list').querySelector(`[data-group="${CSS.escape(groupId)}"].verify-btn`)
  if (btn) { btn.disabled = true; btn.textContent = 'Verifying…' }

  const [fileA, fileB] = group.files

  const result = await api.verifyPair({
    fileA: { remote: fileA.remote, path: fileA.path, name: fileA.name, normName: fileA.normName, size: fileA.size },
    fileB: { remote: fileB.remote, path: fileB.path, name: fileB.name, normName: fileB.normName, size: fileB.size },
  })

  if (!result.ok) {
    if (btn) { btn.disabled = false; btn.textContent = `Error: ${result.error.slice(0, 40)}` }
    return
  }

  if (result.thumbA) fileA.thumbPath = result.thumbA
  if (result.thumbB) fileB.thumbPath = result.thumbB

  group.score     = result.score
  group.breakdown = result.breakdown
  group.verified  = true

  const card = el('group-list').querySelector(`[data-group-id="${CSS.escape(groupId)}"]`)
  if (card) {
    const newCard = makeGroupCard(group)
    card.replaceWith(newCard)
    bindCardEvents(newCard)
  }
}

// ---------------------------------------------------------------------------
// Radio actions + delete footer
// ---------------------------------------------------------------------------

function onFileRadioChange(key, value) {
  state.results.toKeep.delete(key)
  state.results.toDelete.delete(key)
  if (value === 'keep')   state.results.toKeep.add(key)
  if (value === 'delete') state.results.toDelete.add(key)
  updateDeleteFooter()
}

// ---------------------------------------------------------------------------
// Filter
// ---------------------------------------------------------------------------

function applyFilter() {
  const minScore     = parseInt(el('filter-score').value) || 0
  const sameNameOnly = el('filter-same-name').checked

  const cards = el('group-list').querySelectorAll('.group-card')
  let shown = 0

  state.results.groups.forEach((group, i) => {
    const card = cards[i]
    if (!card) return

    let visible = true

    if (minScore > 0) {
      if (group.score === undefined) visible = false
      else if (group.score < minScore) visible = false
    }

    if (sameNameOnly && visible) {
      const names = new Set(group.files.map(f => f.normName))
      if (names.size > 1) visible = false
    }

    card.classList.toggle('hidden', !visible)
    if (visible) shown++
  })

  const total = state.results.groups.length
  el('filter-count').textContent = shown < total
    ? `Showing ${shown} of ${total} groups`
    : `Showing all ${total} groups`
}

function clearFilter() {
  el('filter-score').value = ''
  el('filter-same-name').checked = false
  el('filter-count').textContent = ''
  el('group-list').querySelectorAll('.group-card').forEach(c => c.classList.remove('hidden'))
}

function updateDeleteFooter() {
  const footer = el('delete-footer')
  const sel    = state.results.toDelete

  if (sel.size === 0) { footer.classList.add('hidden'); return }

  footer.classList.remove('hidden')
  let bytes = 0
  state.results.groups.forEach(g =>
    g.files.forEach(f => { if (sel.has(`${f.remote}:${f.path}`)) bytes += f.size })
  )
  el('delete-count').textContent = `${sel.size} file${sel.size !== 1 ? 's' : ''} marked for deletion · ${formatSize(bytes)}`
}

// ---------------------------------------------------------------------------
// Delete flow
// ---------------------------------------------------------------------------

function openDeleteModal() {
  const list = el('delete-modal-list')
  list.innerHTML = ''
  state.results.toDelete.forEach(key => {
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
  state.results.toDelete.forEach(key => {
    const colon = key.indexOf(':')
    files.push({ remote: key.slice(0, colon), path: key.slice(colon + 1) })
  })

  const result = await api.deleteFiles(files)
  const deletedPaths = new Set(result.results.filter(r => r.ok).map(r => r.path))

  // Remove successfully deleted files from both state sets
  const pathToKey = new Map()
  state.results.groups.forEach(g =>
    g.files.forEach(f => pathToKey.set(f.path, `${f.remote}:${f.path}`))
  )
  deletedPaths.forEach(p => {
    const k = pathToKey.get(p)
    if (k) { state.results.toKeep.delete(k); state.results.toDelete.delete(k) }
  })

  state.results.groups.forEach(group => {
    group.files = group.files.filter(f => !deletedPaths.has(f.path))
  })
  state.results.groups = state.results.groups.filter(g => g.files.length >= 2)

  const recoverable = state.results.groups
    .flatMap(g => g.files.filter(f => f.canDelete))
    .reduce((s, f) => s + f.size, 0)

  el('results-summary').textContent =
    `${state.results.groups.length} group${state.results.groups.length !== 1 ? 's' : ''} · ${formatSize(recoverable)} recoverable`

  el('delete-btn').disabled = false
  renderResultsScreen()
}

// ---------------------------------------------------------------------------
// Thumbnail cache management
// ---------------------------------------------------------------------------

async function openThumbCacheModal() {
  el('thumb-cache-folder').value = el('config-drive-path').value.trim()
  el('thumb-cache-modal').classList.remove('hidden')
  await refreshThumbCacheInfo()
}

let thumbCacheInfoTimer = null
function refreshThumbCacheInfo() {
  clearTimeout(thumbCacheInfoTimer)
  thumbCacheInfoTimer = setTimeout(async () => {
    const folderPath  = el('thumb-cache-folder').value.trim()
    const driveRemote = el('config-drive-remote').value.trim() || 'gdrive'
    const info = await api.getThumbCacheInfo({ folderPath, driveRemote })
    const infoEl = el('thumb-cache-info')
    if (info.count === 0) {
      infoEl.textContent = folderPath
        ? `No cached thumbnails for "${folderPath}"`
        : 'No cached thumbnails'
    } else {
      infoEl.textContent = folderPath
        ? `${info.count} thumbnail${info.count !== 1 ? 's' : ''} cached for "${folderPath}" · ${formatSize(info.sizeBytes)}`
        : `${info.count} thumbnail${info.count !== 1 ? 's' : ''} cached · ${formatSize(info.sizeBytes)}`
    }
    el('thumb-cache-confirm-btn').disabled = info.count === 0
  }, 200)
}

async function confirmThumbCacheClear() {
  el('thumb-cache-modal').classList.add('hidden')
  const folderPath  = el('thumb-cache-folder').value.trim()
  const driveRemote = el('config-drive-remote').value.trim() || 'gdrive'
  await api.clearThumbCache({ folderPath, driveRemote })
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
    if (e.target.checked) refreshCatalogInfo()
    else el('catalog-info-row').classList.add('hidden')
  })

  el('config-photos-remote').addEventListener('input', () => {
    if (el('config-include-photos').checked) refreshCatalogInfo()
  })

  el('clear-catalog-btn').addEventListener('click', async () => {
    const remote = el('config-photos-remote').value.trim() || 'gphotos'
    await api.clearCatalogCache({ photosRemote: remote })
    refreshCatalogInfo()
  })

  // Folder browser
  el('browse-folder-btn').addEventListener('click', openFolderBrowser)
  el('folder-cancel-btn').addEventListener('click', () => closeFolderBrowser(false))
  el('folder-select-btn').addEventListener('click', () => closeFolderBrowser(true))
  el('folder-root-btn').addEventListener('click', () => {
    el('config-drive-path').value = ''
    el('folder-modal').classList.add('hidden')
  })
  el('folder-modal').addEventListener('click', (e) => {
    if (e.target === el('folder-modal')) closeFolderBrowser(false)
  })

  // Lightbox
  el('lightbox-close').addEventListener('click', closeLightbox)
  el('lightbox').addEventListener('click', (e) => {
    if (e.target === el('lightbox')) closeLightbox()
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

  el('clear-thumb-cache-btn').addEventListener('click', openThumbCacheModal)
  el('thumb-cache-browse-btn').addEventListener('click', async () => {
    folderBrowser.currentPath = el('thumb-cache-folder').value.trim()
    updateFolderBreadcrumb(folderBrowser.currentPath)
    el('folder-modal').classList.remove('hidden')
    el('folder-modal').dataset.target = 'thumb-cache'
    await loadFolderItems(folderBrowser.currentPath)
  })
  el('thumb-cache-folder').addEventListener('input', refreshThumbCacheInfo)
  el('thumb-cache-cancel-btn').addEventListener('click', () => el('thumb-cache-modal').classList.add('hidden'))
  el('thumb-cache-confirm-btn').addEventListener('click', confirmThumbCacheClear)

  el('verify-all-btn').addEventListener('click', onVerifyAllClick)
  el('verify-all-cancel-btn').addEventListener('click', () => el('verify-all-modal').classList.add('hidden'))
  el('verify-all-confirm-btn').addEventListener('click', async () => {
    el('verify-all-modal').classList.add('hidden')
    const groups = state.results.groups.filter(g => g.files.length >= 2 && !g.verified)
    await verifyAllGroups(groups)
  })
  el('verify-all-partial-btn').addEventListener('click', async () => {
    el('verify-all-modal').classList.add('hidden')
    const groups = state.results.groups.filter(g => g.files.length >= 2 && !g.verified)
    await verifyAllGroups(groups.slice(0, VERIFY_PARTIAL_COUNT))
  })

  el('filter-apply-btn').addEventListener('click', applyFilter)
  el('filter-clear-btn').addEventListener('click', clearFilter)
  el('filter-score').addEventListener('keydown', (e) => { if (e.key === 'Enter') applyFilter() })

  let preClickSelected = null

  el('group-list').addEventListener('mousedown', (e) => {
    const r = e.target
    if (r.matches && r.matches('.keep-radio, .delete-radio') && r.checked) {
      preClickSelected = { key: r.dataset.key, value: r.value }
    } else {
      preClickSelected = null
    }
  })

  el('group-list').addEventListener('click', (e) => {
    const verifyBtn = e.target.closest('.verify-btn')
    if (verifyBtn) { onVerifyClick(verifyBtn.dataset.group); return }

    const r = e.target
    if (r.matches && r.matches('.keep-radio, .delete-radio')) {
      if (preClickSelected && preClickSelected.key === r.dataset.key && preClickSelected.value === r.value) {
        const container = r.closest('.radio-cols')
        const noneRadio = container?.querySelector('.none-radio')
        if (noneRadio) {
          r.checked = false
          noneRadio.checked = true
          container.dataset.selected = 'none'
          onFileRadioChange(r.dataset.key, 'none')
        }
      }
      preClickSelected = null
    }
  })

  el('group-list').addEventListener('change', (e) => {
    const r = e.target
    if (r.matches && r.matches('.keep-radio, .delete-radio')) {
      const container = r.closest('.radio-cols')
      if (container) container.dataset.selected = r.value
      onFileRadioChange(r.dataset.key, r.value)
    }
  })

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      el('delete-modal').classList.add('hidden')
      el('folder-modal').classList.add('hidden')
      el('verify-all-modal').classList.add('hidden')
      el('thumb-cache-modal').classList.add('hidden')
      closeLightbox()
    }
  })
}

function bindCardEvents(_card) {
  // Thumbs are loaded by the eager loader which queries the live DOM — no per-card wiring needed
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
