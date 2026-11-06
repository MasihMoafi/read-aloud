const { app, BrowserWindow, ipcMain, Notification, screen } = require('electron')
const { spawn } = require('node:child_process')
const net = require('node:net')
const path = require('node:path')

const root = process.env.READ_ALOUD_ROOT
const build = process.env.READ_ALOUD_BUILD
const runtime = process.env.READ_ALOUD_RUNTIME || path.join(process.env.XDG_RUNTIME_DIR, 'read-aloud')
const socketPath = path.join(runtime, 'daemon.sock')
let window = null
let daemon = null
let subscription = null
let lastState = { active: false, paused: false, speed: 0, speedValue: '1.0', ready: false, error: '' }
let lastError = ''
let shuttingDown = false
let showIdle = false

app.disableHardwareAcceleration()
app.setDesktopName('read-aloud.desktop')
if (process.env.READ_ALOUD_DEBUG_PORT) {
  app.commandLine.appendSwitch('remote-debugging-port', process.env.READ_ALOUD_DEBUG_PORT)
}

function notify(message) {
  console.error(message)
  if (Notification.isSupported()) new Notification({ title: 'Read Aloud', body: message }).show()
}

function request(command) {
  const client = net.createConnection(socketPath)
  client.on('connect', () => client.end(`${command}\n`))
  client.on('error', (error) => console.error('Control:', error.message))
}

function applyState(line) {
  const [type, active, paused, speed, ready, error = '', speedValue = '1.0'] = line.split('\t')
  if (type !== 'STATE') return
  lastState = { active: active === '1', paused: paused === '1', speed: Number(speed), speedValue, ready: ready === '1', error }
  if (!window || window.isDestroyed()) return
  window.webContents.send('state', lastState)
  if (lastState.active) {
    showIdle = false
    if (!window.isVisible()) window.showInactive()
  } else if (!showIdle && window.isVisible()) {
    window.hide()
  }
  if (error && error !== lastError) notify(error)
  lastError = error
}

function connect() {
  if (shuttingDown) return
  const client = net.createConnection(socketPath)
  subscription = client
  let pending = ''
  client.on('connect', () => client.write('SUBSCRIBE\n'))
  client.on('data', (buffer) => {
    pending += buffer.toString('utf8')
    const lines = pending.split('\n')
    pending = lines.pop()
    lines.forEach(applyState)
  })
  client.on('error', () => {})
  client.on('close', () => { if (!shuttingDown) setTimeout(connect, 250) })
}

function createWindow() {
  const area = screen.getPrimaryDisplay().workArea
  window = new BrowserWindow({
    width: 344, height: 64, minWidth: 320, minHeight: 64,
    x: area.x + area.width - 368, y: area.y + area.height - 88,
    frame: false, resizable: false, show: false, skipTaskbar: true,
    alwaysOnTop: true,
    icon: path.join(build, 'logo.png'),
    webPreferences: { preload: path.join(root, 'electron/preload.cjs'), contextIsolation: true, nodeIntegration: false, sandbox: true },
  })
  window.setVisibleOnAllWorkspaces(true)
  window.loadFile(path.join(build, 'index.html'))
  window.webContents.on('did-finish-load', () => window.webContents.send('state', lastState))
}

function showWindow() {
  if (!lastState.active) showIdle = true
  if (!window || window.isDestroyed()) return
  const reveal = () => {
    if (!window || window.isDestroyed() || (!showIdle && !lastState.active)) return
    window.show()
    window.focus()
  }
  if (window.webContents.isLoadingMainFrame()) window.webContents.once('did-finish-load', reveal)
  else reveal()
}

ipcMain.on('action', (_event, name) => {
  if (name === 'pause') request('PAUSE')
  else if (name === 'stop') request('STOP')
  else if (name === 'faster') request('FASTER')
  else if (name === 'hide' && window && !window.isDestroyed()) { showIdle = false; window.hide() }
})

if (!app.requestSingleInstanceLock()) app.quit()
else {
  app.on('second-instance', (_event, argv) => { if (argv.includes('--show')) showWindow() })
  app.whenReady().then(() => {
    createWindow()
    if (showIdle || process.argv.includes('--show')) showWindow()
    daemon = spawn(path.join(build, 'read-aloud'), ['daemon'], { env: process.env, stdio: ['ignore', 'ignore', 'inherit'] })
    daemon.on('error', (error) => { notify(`Could not start speech: ${error.message}`); app.quit() })
    daemon.on('exit', (code) => {
      if (!shuttingDown) {
        if (code !== 0 && !lastError) notify(`Speech service stopped (${code ?? 'signal'})`)
        shuttingDown = true
        app.quit()
      }
    })
    connect()
  })
}

app.on('window-all-closed', () => {})
app.on('before-quit', (event) => {
  if (shuttingDown) return
  event.preventDefault()
  shuttingDown = true
  if (subscription) subscription.destroy()
  if (!daemon || daemon.exitCode !== null) return app.quit()
  daemon.once('exit', () => app.quit())
  request('SHUTDOWN')
  setTimeout(() => { if (daemon.exitCode === null) daemon.kill('SIGTERM') }, 2000).unref()
})
