const { app, BrowserWindow, ipcMain, Notification, screen } = require('electron')
const { execFile, spawn } = require('node:child_process')
const net = require('node:net')
const path = require('node:path')
const { promisify } = require('node:util')
import { downloadModelFiles, MODEL_FILES } from './model-download'

const root = process.env.READ_ALOUD_ROOT || path.join((process as NodeJS.Process & { resourcesPath: string }).resourcesPath, 'read-aloud')
const build = process.env.READ_ALOUD_BUILD || path.join(root, 'build')
const python = process.env.READ_ALOUD_PYTHON || (app.isPackaged ? path.join(root, 'runtime/bin/python3') : 'python3')
const launcher = process.env.SNAP ? '/snap/bin/read-aloud' : (process.env.APPIMAGE || process.execPath)
process.env.READ_ALOUD_ROOT = root
if (app.isPackaged) process.env.READ_ALOUD_START = launcher
const runtime = process.env.READ_ALOUD_RUNTIME || path.join(process.env.XDG_RUNTIME_DIR, 'read-aloud')
const socketPath = path.join(runtime, 'daemon.sock')
let window = null
let daemon = null
let subscription = null
type DownloadState = { phase: 'checking' | 'downloading' | 'failed' | 'ready'; percent: number; error: string }
let downloadState: DownloadState = { phase: 'checking', percent: 0, error: '' }
let lastState = { active: false, paused: false, speed: 0, speedValue: '1.0', ready: false, error: '' }
let downloading = false
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

function sendState() {
  if (window && !window.isDestroyed()) window.webContents.send('state', { ...lastState, download: downloadState })
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
  sendState()
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
    webPreferences: { preload: path.join(build, 'preload.cjs'), contextIsolation: true, nodeIntegration: false, sandbox: true },
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
  window.webContents.on('did-finish-load', sendState)
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
  else if (name === 'retry') void prepareModel()
})

ipcMain.on('state-request', sendState)

ipcMain.on('speed', (_event, index) => { if (Number.isInteger(index)) request(`SPEED ${index}`) })

async function voiceCommand(...args) {
  try {
    const { stdout } = await runFile(python, [path.join(root, 'worker/voices.py'), ...args], { timeout: 5000 })
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

async function prepareModel() {
  if (downloading || daemon || shuttingDown) return
  downloading = true
  downloadState = { phase: 'checking', percent: 0, error: '' }
  sendState()
  try {
    const directory = path.join(process.env.SNAP_USER_COMMON || app.getPath('userData'), 'models')
    const total = MODEL_FILES.reduce((sum, file) => sum + file.size, 0)
    await downloadModelFiles(directory, MODEL_FILES, (progress) => {
      const index = MODEL_FILES.findIndex((file) => file.name === progress.name)
      const completed = MODEL_FILES.slice(0, index).reduce((sum, file) => sum + file.size, 0)
      const percent = Math.min(99, Math.floor((completed + Math.min(progress.received, MODEL_FILES[index].size)) * 100 / total))
      const firstProgress = downloadState.phase !== 'downloading'
      if (!firstProgress && downloadState.percent === percent) return
      downloadState = { phase: 'downloading', percent, error: '' }
      sendState()
      if (firstProgress) showWindow()
    })
    if (shuttingDown) return
    process.env.READ_ALOUD_MODEL = path.join(directory, MODEL_FILES[0].name)
    process.env.READ_ALOUD_VOICES = path.join(directory, MODEL_FILES[1].name)
    downloadState = { phase: 'ready', percent: 100, error: '' }
    sendState()
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
  } catch (error) {
    if (shuttingDown) return
    const message = error instanceof Error ? error.message : String(error)
    downloadState = { phase: 'failed', percent: 0, error: message }
    console.error('Voice download failed:', message)
    sendState()
    showWindow()
  } finally {
    downloading = false
  }
}

function runShortcut(argv) {
  const index = argv.indexOf('--shortcut')
  const action = index < 0 ? '' : argv[index + 1]
  if (!['read', 'faster', 'slower'].includes(action)) return
  const child = spawn(path.join(build, 'read-aloud'), [action], { env: process.env, stdio: ['ignore', 'ignore', 'pipe'] })
  let error = ''
  child.stderr.on('data', (chunk) => { error += chunk.toString() })
  child.on('error', (failure) => notify(`Shortcut failed: ${failure.message}`))
  child.on('exit', (code) => { if (code) notify(`Shortcut failed: ${error.trim() || code}`) })
}

if (process.argv.includes('--uninstall-setup')) {
  void runFile(python, [path.join(root, 'scripts/desktop-setup.py'), 'uninstall', launcher])
    .then(() => app.exit(0), (error) => { console.error(error.message); app.exit(1) })
} else if (!app.requestSingleInstanceLock()) app.quit()
else {
  app.on('second-instance', (_event, argv) => {
    if (argv.includes('--show') || (!argv.includes('--background') && !argv.includes('--shortcut'))) showWindow()
    runShortcut(argv)
  })
  app.whenReady().then(() => {
    createWindow()
    if (app.isPackaged && !process.env.SNAP) {
      void runFile(python, [path.join(root, 'scripts/desktop-setup.py'), 'install', launcher]).catch((error) => notify(`Shortcut setup failed: ${error.message}`))
    }
    runShortcut(process.argv)
    if (showIdle || process.argv.includes('--show') || (app.isPackaged && !process.argv.includes('--background') && !process.argv.includes('--shortcut'))) showWindow()
    void prepareModel()
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
