const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('api', {
  checkSetup:       ()      => ipcRenderer.invoke('check-setup'),
  startScan:        (args)  => ipcRenderer.invoke('start-scan', args),
  cancelScan:       ()      => ipcRenderer.invoke('cancel-scan'),
  verifyPair:       (args)  => ipcRenderer.invoke('verify-pair', args),
  deleteFiles:      (files) => ipcRenderer.invoke('delete-files', files),
  getPrefs:         ()      => ipcRenderer.invoke('get-prefs'),
  setPrefs:         (p)     => ipcRenderer.invoke('set-prefs', p),
  openExternal:     (url)   => ipcRenderer.invoke('open-external', url),
  listDriveFolders:  (args) => ipcRenderer.invoke('list-drive-folders', args),
  fetchThumb:        (args) => ipcRenderer.invoke('fetch-thumb', args),
  getCatalogInfo:    (args) => ipcRenderer.invoke('get-catalog-info', args),
  clearCatalogCache: (args) => ipcRenderer.invoke('clear-catalog-cache', args),
  getThumbCacheInfo: (args) => ipcRenderer.invoke('get-thumb-cache-info', args),
  clearThumbCache:   (args) => ipcRenderer.invoke('clear-thumb-cache', args),

  onScanProgress: (cb) => ipcRenderer.on('scan-progress', (_e, d) => cb(d)),
  onScanDone:     (cb) => ipcRenderer.on('scan-done',     (_e, d) => cb(d)),
  offScanListeners: () => {
    ipcRenderer.removeAllListeners('scan-progress')
    ipcRenderer.removeAllListeners('scan-done')
  },
})
