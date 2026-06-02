const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('api', {
  checkRclone:   ()       => ipcRenderer.invoke('check-rclone'),
  listFolder:    (args)   => ipcRenderer.invoke('list-folder', args),
  getFolderSize: (args)   => ipcRenderer.invoke('get-folder-size', args),
  getPrefs:      ()       => ipcRenderer.invoke('get-prefs'),
  setPrefs:      (prefs)  => ipcRenderer.invoke('set-prefs', prefs),
  openExternal:  (url)    => ipcRenderer.invoke('open-external', url),
})
