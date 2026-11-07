const { app, BrowserWindow, ipcMain, Notification, screen } = require('electron')
const { execFile, spawn } = require('node:child_process')
const net = require('node:net')
const path = require('node:path')
const { promisify } = require('node:util')

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
// The bar stays put; menus open the window upward above it.
const BAR = { width: 204, height: 40 }
const MENU_HEIGHT = { speed: 212, voice: 280 }
const MENU_WIDTH = 168
const runFile = promisify(execFile)

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
    width: BAR.width, height: BAR.height,
    x: area.x + area.width - BAR.width - 24, y: area.y + area.height - BAR.height - 24,
    frame: false, resizable: false, show: false, skipTaskbar: true,
    alwaysOnTop: true, transparent: true, backgroundColor: '#00000000',
    icon: path.join(build, 'logo.png'),
    webPreferences: { preload: path.join(root, 'electron/preload.cjs'), contextIsolation: true, nodeIntegration: false, sandbox: true },
  })
  // Closing from the window manager (Alt+F4, title menu) must only hide: the launcher reopens this window.
  window.on('close', (event) => {
    if (shuttingDown) return
    event.preventDefault()
    showIdle = false
    window.hide()
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
  else if (name === 'hide' && window && !window.isDestroyed()) { showIdle = false; window.hide() }
})

ipcMain.on('speed', (_event, index) => { if (Number.isInteger(index)) request(`SPEED ${index}`) })

async function voiceCommand(...args) {
  try {
    const { stdout } = await runFile('python3', [path.join(root, 'worker/voices.py'), ...args], { timeout: 5000 })
    return JSON.parse(stdout)
  } catch (error) {
    notify('Local voices are unavailable. Check the installed voice bundle.')
    throw error
  }
}

ipcMain.handle('voice-status', () => voiceCommand('status'))
ipcMain.handle('voice-select', (_event, name) => {
  if (typeof name !== 'string') throw new Error('Invalid voice')
  return voiceCommand('select', name)
})

// The bar is as wide as its controls (the renderer measures them); menus need room for voice names.
// Resizing keeps the right edge and the bottom where they are.
let barWidth = BAR.width
let openMenu = null
function fitWindow() {
  if (!window || window.isDestroyed()) return
  const bounds = window.getBounds()
  const width = openMenu ? Math.max(barWidth, MENU_WIDTH) : barWidth
  const height = BAR.height + (openMenu ? MENU_HEIGHT[openMenu] : 0)
  window.setBounds({ x: bounds.x + bounds.width - width, y: bounds.y + bounds.height - height, width, height })
}

ipcMain.on('menu', (_event, menu) => {
  if (menu !== null && menu !== 'speed' && menu !== 'voice') return
  openMenu = menu
  fitWindow()
})

ipcMain.on('bar-width', (_event, width) => {
  if (!Number.isFinite(width)) return
  barWidth = Math.min(400, Math.max(96, Math.ceil(width)))
  fitWindow()
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
