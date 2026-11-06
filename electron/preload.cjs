const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('readAloud', {
  onState: (listener) => ipcRenderer.on('state', (_event, state) => listener(state)),
  action: (name, value) => ipcRenderer.send('action', name, value),
})
