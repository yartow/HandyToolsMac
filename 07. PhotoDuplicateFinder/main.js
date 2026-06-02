const { app, BrowserWindow, ipcMain, shell } = require('electron')
const { execFile } = require('child_process')
const path = require('path')
const os = require('os')
const fs = require('fs')
const Store = require('electron-store')
const { filterPhotos, buildDuplicateGroups } = require('./scanner')
const { computeHash, hammingDistance, isHeic } = require('./hasher')

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

app.whenReady().then(createWindow)
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
// IPC: start-scan  (streams scan-progress / scan-done events)
// ---------------------------------------------------------------------------

ipcMain.handle('start-scan', async (_e, { drivePath, includePhotos, driveRemote, photosRemote }) => {
  currentScanAbort = false
  // Clean up temp dir from previous run
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

  emit({ phase: 'listing', source: 'drive', scanned: driveFiles.length, total: driveFiles.length, currentFile: `Found ${driveFiles.length} photos in Drive` })

  // --- Phase 2: list Google Photos (optional) ---
  let photosFiles = []
  if (includePhotos) {
    emit({ phase: 'listing', source: 'photos', scanned: 0, total: null, currentFile: 'Fetching Google Photos list (this can take several minutes for large libraries)…' })

    try {
      const photosRaw = await execRclone(
        ['lsjson', `${photosRemote}:media/all-photos`, '--recursive', '--no-modtime', '--no-mimetype'],
        { timeout: 600_000 }
      )
      if (!currentScanAbort) {
        const photosAll = JSON.parse(photosRaw)
        photosFiles = filterPhotos(photosAll, photosRemote)
        emit({ phase: 'listing', source: 'photos', scanned: photosFiles.length, total: photosFiles.length, currentFile: `Found ${photosFiles.length} photos in Google Photos` })
      }
    } catch (e) {
      // Non-fatal: continue without Google Photos if the remote fails
      emit({ phase: 'listing', source: 'photos', scanned: 0, total: 0, currentFile: `Could not list Google Photos: ${e.message}` })
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
// IPC: verify-pair
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

    // Handle HEIC — return thumbnails but skip pHash
    if (isHeic(pathA) || isHeic(pathB)) {
      return { ok: true, match: null, distance: null, thumbA: pathA, thumbB: pathB, unsupported: true }
    }

    const [hashA, hashB] = await Promise.all([computeHash(pathA), computeHash(pathB)])
    const distance = hammingDistance(hashA, hashB)

    return { ok: true, match: distance <= 10, distance, thumbA: pathA, thumbB: pathB, unsupported: false }
  } catch (e) {
    return { ok: false, error: e.message, unsupported: !!e.unsupported }
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
// IPC: prefs + external
// ---------------------------------------------------------------------------

ipcMain.handle('get-prefs', () => store.store)
ipcMain.handle('set-prefs', (_e, prefs) => {
  Object.entries(prefs).forEach(([k, v]) => store.set(k, v))
  return store.store
})
ipcMain.handle('open-external', (_e, url) => shell.openExternal(url))
