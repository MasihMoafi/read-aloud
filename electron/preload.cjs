const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('readAloud', {
  onState: (listener) => ipcRenderer.on('state', (_event, state) => listener(state)),
  action: (name) => ipcRenderer.send('action', name),
  setSpeed: (index) => ipcRenderer.send('speed', index),
  voiceStatus: () => ipcRenderer.invoke('voice-status'),
  selectVoice: (name) => ipcRenderer.invoke('voice-select', name),
  menu: (name) => ipcRenderer.send('menu', name),
})
