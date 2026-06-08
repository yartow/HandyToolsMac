const { app, BrowserWindow, ipcMain, shell } = require('electron')
const { execFile } = require('child_process')
const path = require('path')
const os = require('os')
const fs = require('fs')
const crypto = require('crypto')
const Store = require('electron-store')
const { filterPhotos, buildDuplicateGroups } = require('./scanner')
const { computeHash, hammingDistance, isHeic } = require('./hasher')
const { computeScore } = require('./scorer')

const store = new Store({
  defaults: {
    drivePath: '',
    driveRemote: 'gdrive',
    photosRemote: 'gphotos',
    includePhotos: true,
    windowBounds: { width: 1000, height: 700 },
  },
})

const TEMP_DIR = path.join(os.tmpdir(), 'photo-dup-finder')
const CATALOG_MAX_AGE_MS = 24 * 60 * 60 * 1000   // 24 hours
let CATALOG_CACHE_DIR = null
let THUMB_CACHE_DIR   = null
let mainWindow
let rcloneBin = 'rclone'
let currentScanAbort = false

// ---------------------------------------------------------------------------
// Window
// ---------------------------------------------------------------------------

function createWindow() {
  const { width, height } = store.get('windowBounds')

  mainWindow = new BrowserWindow({
    width,
    height,
    minWidth: 800,
    minHeight: 550,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      webSecurity: false,  // allow file:// thumbnail src from temp dir
    },
    titleBarStyle: 'hiddenInset',
  })

  mainWindow.loadFile('index.html')
  mainWindow.on('resize', () => {
    const [w, h] = mainWindow.getSize()
    store.set('windowBounds', { width: w, height: h })
  })
}

app.whenReady().then(() => {
  CATALOG_CACHE_DIR = path.join(app.getPath('userData'), 'catalog-cache')
  THUMB_CACHE_DIR   = path.join(app.getPath('userData'), 'thumb-cache')
  try { fs.mkdirSync(CATALOG_CACHE_DIR, { recursive: true }) } catch {}
  try { fs.mkdirSync(THUMB_CACHE_DIR,   { recursive: true }) } catch {}
  createWindow()
})
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit() })
app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow() })
app.on('before-quit', () => {
  try { fs.rmSync(TEMP_DIR, { recursive: true, force: true }) } catch {}
})

// ---------------------------------------------------------------------------
// rclone helpers
// ---------------------------------------------------------------------------

function execRclone(args, opts = {}) {
  return new Promise((resolve, reject) => {
    execFile(rcloneBin, args, {
      maxBuffer: 100 * 1024 * 1024,
      timeout: opts.timeout ?? 120_000,
    }, (err, stdout, stderr) => {
      if (err) reject(new Error(stderr?.trim() || err.message))
      else resolve(stdout)
    })
  })
}

async function findRclone() {
  const candidates = ['rclone', '/opt/homebrew/bin/rclone', '/usr/local/bin/rclone', '/usr/bin/rclone']
  for (const bin of candidates) {
    try {
      await new Promise((res, rej) =>
        execFile(bin, ['version'], { timeout: 5000 }, (e) => (e ? rej(e) : res()))
      )
      rcloneBin = bin
      return true
    } catch {}
  }
  return false
}

// ---------------------------------------------------------------------------
// Google Photos catalog cache
// ---------------------------------------------------------------------------

function catalogCacheFile(photosRemote) {
  return path.join(CATALOG_CACHE_DIR, `${photosRemote}.json`)
}

function msToHuman(ms) {
  const h = Math.floor(ms / 3_600_000)
  const m = Math.floor((ms % 3_600_000) / 60_000)
  if (h >= 24) return `${Math.floor(h / 24)}d ${h % 24}h`
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}

async function loadPhotoCatalog(photosRemote, emit) {
  const cacheFile = catalogCacheFile(photosRemote)

  // Try cache first
  try {
    const cached = JSON.parse(fs.readFileSync(cacheFile, 'utf8'))
    const age = Date.now() - cached.timestamp
    if (age < CATALOG_MAX_AGE_MS) {
      const files = filterPhotos(JSON.parse(cached.rawLsjson), photosRemote)
      files.forEach(f => { f.path = `media/all-photos/${f.path}` })
      emit({
        phase: 'listing', source: 'photos',
        scanned: files.length, total: files.length,
        currentFile: `Loaded ${files.length} photos from cache (${msToHuman(age)} ago)`,
      })
      return files
    }
  } catch {}

  // Fetch fresh catalog
  emit({
    phase: 'listing', source: 'photos', scanned: 0, total: null,
    currentFile: 'Fetching Google Photos catalog — may take several minutes for large libraries…',
  })

  const rawLsjson = await execRclone(
    ['lsjson', `${photosRemote}:media/all-photos`, '--recursive', '--no-modtime', '--no-mimetype'],
    { timeout: 600_000 }
  )

  // Persist to cache
  try {
    fs.writeFileSync(cacheFile, JSON.stringify({ timestamp: Date.now(), rawLsjson }), 'utf8')
  } catch {}

  const files = filterPhotos(JSON.parse(rawLsjson), photosRemote)
  files.forEach(f => { f.path = `media/all-photos/${f.path}` })
  emit({
    phase: 'listing', source: 'photos',
    scanned: files.length, total: files.length,
    currentFile: `Found ${files.length} photos in Google Photos`,
  })
  return files
}

// ---------------------------------------------------------------------------
// IPC: check-setup
// ---------------------------------------------------------------------------

ipcMain.handle('check-setup', async () => {
  const found = await findRclone()
  if (!found) return { ok: false, error: 'rclone not found' }

  try {
    const [versionOut, remotesOut] = await Promise.all([
      execRclone(['version'], { timeout: 5000 }),
      execRclone(['listremotes'], { timeout: 5000 }),
    ])

    const remotes = remotesOut.split('\n').map(r => r.trim().replace(/:$/, ''))
    const driveRemote  = store.get('driveRemote')
    const photosRemote = store.get('photosRemote')

    return {
      ok: true,
      rcloneVersion: versionOut.split('\n')[0].trim(),
      hasGdrive:  remotes.includes(driveRemote),
      hasGphotos: remotes.includes(photosRemote),
    }
  } catch (e) {
    return { ok: false, error: e.message }
  }
})

// ---------------------------------------------------------------------------
// IPC: start-scan
// ---------------------------------------------------------------------------

ipcMain.handle('start-scan', async (_e, { drivePath, includePhotos, driveRemote, photosRemote }) => {
  currentScanAbort = false
  try { fs.rmSync(TEMP_DIR, { recursive: true, force: true }) } catch {}

  const emit = (data) => mainWindow.webContents.send('scan-progress', data)

  try {
    const groups = await runScan({ drivePath, includePhotos, driveRemote, photosRemote, emit })
    mainWindow.webContents.send('scan-done', { ok: true, groups })
  } catch (e) {
    mainWindow.webContents.send('scan-done', { ok: false, error: e.message })
  }

  return { started: true }
})

async function runScan({ drivePath, includePhotos, driveRemote, photosRemote, emit }) {
  // --- Phase 1: list Google Drive ---
  emit({ phase: 'listing', source: 'drive', scanned: 0, total: null, currentFile: 'Fetching Google Drive list…' })

  const driveTarget = drivePath ? `${driveRemote}:${drivePath}` : `${driveRemote}:`
  const driveRaw = await execRclone(
    ['lsjson', driveTarget, '--recursive', '--no-modtime', '--no-mimetype'],
    { timeout: 600_000 }
  )

  if (currentScanAbort) throw new Error('Scan cancelled')

  const driveAll = JSON.parse(driveRaw)
  const driveFiles = filterPhotos(driveAll, driveRemote)
  // Prepend drivePath so stored paths are relative to the remote root
  if (drivePath) {
    driveFiles.forEach(f => { f.path = `${drivePath}/${f.path}` })
  }

  emit({ phase: 'listing', source: 'drive', scanned: driveFiles.length, total: driveFiles.length, currentFile: `Found ${driveFiles.length} photos in Drive` })

  // --- Phase 2: Google Photos catalog (cached) ---
  let photosFiles = []
  if (includePhotos) {
    try {
      photosFiles = await loadPhotoCatalog(photosRemote, emit)
    } catch (e) {
      emit({ phase: 'listing', source: 'photos', scanned: 0, total: 0, currentFile: `Could not load Google Photos catalog: ${e.message}` })
    }
  }

  if (currentScanAbort) throw new Error('Scan cancelled')

  // --- Phase 3: group ---
  const total = driveFiles.length + photosFiles.length
  emit({ phase: 'grouping', scanned: total, total, currentFile: 'Finding duplicates…' })

  const groups = buildDuplicateGroups(driveFiles, photosFiles, driveRemote)
  return groups
}

ipcMain.handle('cancel-scan', () => {
  currentScanAbort = true
  return { ok: true }
})

// ---------------------------------------------------------------------------
// Thumb cache helpers
// ---------------------------------------------------------------------------

function thumbIndexFile() {
  return path.join(THUMB_CACHE_DIR, '_index.json')
}

function loadThumbIndex() {
  try { return JSON.parse(fs.readFileSync(thumbIndexFile(), 'utf8')) }
  catch { return {} }
}

function saveThumbIndex(idx) {
  try { fs.writeFileSync(thumbIndexFile(), JSON.stringify(idx), 'utf8') } catch {}
}

function thumbCachePath(remote, filePath, name) {
  const keyHash = crypto.createHash('md5').update(`${remote}:${filePath}`).digest('hex')
  const ext = path.extname(name) || '.jpg'
  return path.join(THUMB_CACHE_DIR, keyHash + ext)
}

function cacheThumb(remote, filePath, name, srcPath) {
  const dest = thumbCachePath(remote, filePath, name)
  try {
    if (!fs.existsSync(dest)) {
      fs.copyFileSync(srcPath, dest)
      const idx = loadThumbIndex()
      idx[`${remote}:${filePath}`] = path.basename(dest)
      saveThumbIndex(idx)
    }
  } catch {}
  return dest
}

// ---------------------------------------------------------------------------
// IPC: verify-pair  (multi-signal similarity score)
// ---------------------------------------------------------------------------

ipcMain.handle('verify-pair', async (_e, { fileA, fileB }) => {
  try {
    const sessionDir = path.join(TEMP_DIR, `${Date.now()}`)
    fs.mkdirSync(sessionDir, { recursive: true })

    const pathA = path.join(sessionDir, 'a_' + fileA.name)
    const pathB = path.join(sessionDir, 'b_' + fileB.name)

    await Promise.all([
      execRclone(['copyto', `${fileA.remote}:${fileA.path}`, pathA], { timeout: 120_000 }),
      execRclone(['copyto', `${fileB.remote}:${fileB.path}`, pathB], { timeout: 120_000 }),
    ])

    // Persist to thumb cache for future sessions
    const thumbA = cacheThumb(fileA.remote, fileA.path, fileA.name, pathA)
    const thumbB = cacheThumb(fileB.remote, fileB.path, fileB.name, pathB)

    const heic = isHeic(pathA) || isHeic(pathB)

    // EXIF
    let exifA = null, exifB = null
    try {
      const exifr = require('exifr')
      ;[exifA, exifB] = await Promise.all([
        exifr.parse(pathA, { tiff: true, exif: true, gps: false, iptc: false }).catch(() => null),
        exifr.parse(pathB, { tiff: true, exif: true, gps: false, iptc: false }).catch(() => null),
      ])
    } catch {}

    // pHash (skip for HEIC)
    let pHashDistance = null
    if (!heic) {
      try {
        const [hashA, hashB] = await Promise.all([computeHash(pathA), computeHash(pathB)])
        pHashDistance = hammingDistance(hashA, hashB)
      } catch {}
    }

    const { score, breakdown } = computeScore({
      normNameA: fileA.normName,
      normNameB: fileB.normName,
      sizeA: fileA.size,
      sizeB: fileB.size,
      exifA,
      exifB,
      pHashDistance,
      heic,
    })

    return { ok: true, score, breakdown, thumbA, thumbB, unsupported: heic }
  } catch (e) {
    return { ok: false, error: e.message }
  }
})

// ---------------------------------------------------------------------------
// IPC: delete-files
// ---------------------------------------------------------------------------

ipcMain.handle('delete-files', async (_e, files) => {
  const allowedRemote = store.get('driveRemote') || 'gdrive'
  const results = []

  for (const f of files) {
    if (f.remote !== allowedRemote) {
      results.push({ path: f.path, ok: false, error: 'Deletion refused: not a Drive file' })
      continue
    }
    try {
      await execRclone(['deletefile', `${f.remote}:${f.path}`])
      results.push({ path: f.path, ok: true })
    } catch (e) {
      results.push({ path: f.path, ok: false, error: e.message })
    }
  }

  return { results }
})

// ---------------------------------------------------------------------------
// IPC: list-drive-folders  (folder browser)
// ---------------------------------------------------------------------------

ipcMain.handle('list-drive-folders', async (_e, { remote, folderPath }) => {
  try {
    const target = folderPath ? `${remote}:${folderPath}` : `${remote}:`
    const out = await execRclone(['lsd', target, '--max-depth', '1'], { timeout: 30_000 })
    const folders = out.split('\n')
      .filter(l => l.trim())
      .map(l => {
        // rclone lsd line: "       -1 2023-01-01 00:00:00        -1 FolderName"
        const parts = l.trim().split(/\s+/)
        return parts[parts.length - 1]
      })
      .filter(Boolean)
    return { ok: true, folders }
  } catch (e) {
    return { ok: false, error: e.message }
  }
})

// ---------------------------------------------------------------------------
// IPC: fetch-thumb  (single-file thumbnail download)
// ---------------------------------------------------------------------------

ipcMain.handle('fetch-thumb', async (_e, { remote, filePath, name }) => {
  try {
    const localPath = thumbCachePath(remote, filePath, name)
    if (!fs.existsSync(localPath)) {
      await execRclone(['copyto', `${remote}:${filePath}`, localPath], { timeout: 60_000 })
      const idx = loadThumbIndex()
      idx[`${remote}:${filePath}`] = path.basename(localPath)
      saveThumbIndex(idx)
    }
    return { ok: true, thumbPath: localPath }
  } catch (e) {
    return { ok: false, error: e.message }
  }
})

// ---------------------------------------------------------------------------
// IPC: catalog cache management
// ---------------------------------------------------------------------------

ipcMain.handle('get-catalog-info', (_e, { photosRemote }) => {
  if (!CATALOG_CACHE_DIR) return { exists: false }
  try {
    const cached = JSON.parse(fs.readFileSync(catalogCacheFile(photosRemote), 'utf8'))
    const items  = JSON.parse(cached.rawLsjson)
    const fileCount = items.filter(f => !f.IsDir).length
    return { exists: true, cachedAt: cached.timestamp, fileCount, ageMs: Date.now() - cached.timestamp }
  } catch {
    return { exists: false }
  }
})

ipcMain.handle('clear-catalog-cache', (_e, { photosRemote }) => {
  if (!CATALOG_CACHE_DIR) return { ok: false }
  try { fs.unlinkSync(catalogCacheFile(photosRemote)) } catch {}
  return { ok: true }
})

ipcMain.handle('get-thumb-cache-info', (_e, { folderPath, driveRemote } = {}) => {
  const idx = loadThumbIndex()
  const prefix = folderPath ? `${driveRemote}:${folderPath}/` : null
  let count = 0, sizeBytes = 0
  for (const [key, fname] of Object.entries(idx)) {
    if (prefix && !key.startsWith(prefix)) continue
    count++
    try { sizeBytes += fs.statSync(path.join(THUMB_CACHE_DIR, fname)).size } catch {}
  }
  return { count, sizeBytes }
})

ipcMain.handle('clear-thumb-cache', (_e, { folderPath, driveRemote }) => {
  const idx = loadThumbIndex()
  const prefix = folderPath ? `${driveRemote}:${folderPath}/` : null
  let deleted = 0
  const newIdx = {}
  for (const [key, fname] of Object.entries(idx)) {
    if (!prefix || key.startsWith(prefix)) {
      try { fs.unlinkSync(path.join(THUMB_CACHE_DIR, fname)) } catch {}
      deleted++
    } else {
      newIdx[key] = fname
    }
  }
  saveThumbIndex(prefix ? newIdx : {})
  return { ok: true, deleted }
})

// ---------------------------------------------------------------------------
// IPC: prefs + external
// ---------------------------------------------------------------------------

ipcMain.handle('get-prefs', () => store.store)
ipcMain.handle('set-prefs', (_e, prefs) => {
  Object.entries(prefs).forEach(([k, v]) => store.set(k, v))
  return store.store
})
ipcMain.handle('open-external', (_e, url) => shell.openExternal(url))
