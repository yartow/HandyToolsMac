const { app, BrowserWindow, ipcMain, shell } = require('electron')
const { execFile } = require('child_process')
const path = require('path')
const Store = require('electron-store')

const store = new Store({
  defaults: {
    rootPath: '',
    rcloneRemote: 'gdrive',
    windowBounds: { width: 900, height: 600 },
  },
})

let mainWindow
let rcloneBin = 'rclone'

// ---------------------------------------------------------------------------
// Window
// ---------------------------------------------------------------------------

function createWindow() {
  const { width, height } = store.get('windowBounds')

  mainWindow = new BrowserWindow({
    width,
    height,
    minWidth: 620,
    minHeight: 420,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
    titleBarStyle: 'hiddenInset',
  })

  mainWindow.loadFile('index.html')
  mainWindow.on('resize', () => {
    const [width, height] = mainWindow.getSize()
    store.set('windowBounds', { width, height })
  })
}

app.whenReady().then(createWindow)
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit() })
app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow() })

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
  const candidates = [
    'rclone',
    '/opt/homebrew/bin/rclone',
    '/usr/local/bin/rclone',
    '/usr/bin/rclone',
  ]
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
// IPC handlers
// ---------------------------------------------------------------------------

ipcMain.handle('check-rclone', async () => {
  const found = await findRclone()
  if (!found) return { ok: false, error: 'rclone not found in PATH' }
  try {
    const out = await execRclone(['version'], { timeout: 5000 })
    return { ok: true, version: out.split('\n')[0] }
  } catch (e) {
    return { ok: false, error: e.message }
  }
})

ipcMain.handle('list-folder', async (_e, { remote, remotePath }) => {
  try {
    const target = remotePath ? `${remote}:${remotePath}` : `${remote}:`
    const out = await execRclone(['lsjson', target, '--no-mimetype', '--no-modtime'])
    return { ok: true, data: JSON.parse(out) }
  } catch (e) {
    return { ok: false, error: e.message }
  }
})

ipcMain.handle('get-folder-size', async (_e, { remote, remotePath }) => {
  try {
    const target = remotePath ? `${remote}:${remotePath}` : `${remote}:`
    const out = await execRclone(['size', '--json', target], { timeout: 300_000 })
    return { ok: true, data: JSON.parse(out) }
  } catch (e) {
    return { ok: false, error: e.message }
  }
})

ipcMain.handle('get-prefs', () => store.store)

ipcMain.handle('set-prefs', (_e, prefs) => {
  Object.entries(prefs).forEach(([k, v]) => store.set(k, v))
  return store.store
})

ipcMain.handle('open-external', (_e, url) => shell.openExternal(url))
