const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('readAloud', {
  onState: (listener) => ipcRenderer.on('state', (_event, state) => listener(state)),
  action: (name) => ipcRenderer.send('action', name),
  setSpeed: (index) => ipcRenderer.send('speed', index),
  menu: (open) => ipcRenderer.send('menu', open),
})
