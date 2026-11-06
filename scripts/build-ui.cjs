const fs = require('node:fs')
const path = require('node:path')
const { execFileSync } = require('node:child_process')
const { createRequire } = require('node:module')
const checkLogoApproval = require('./check-logo-approval.cjs')

const root = path.resolve(__dirname, '..')
const out = process.env.READ_ALOUD_BUILD
const modules = process.env.READ_ALOUD_NODE_MODULES || path.join(process.env.HOME, 'Desktop/p/svg/node_modules')
const fromModules = createRequire(path.join(modules, 'placeholder.js'))
const esbuild = require('/usr/local/node/lib/node_modules/vercel/node_modules/esbuild')
const postcss = fromModules('postcss')
const tailwind = fromModules('@tailwindcss/postcss')
const design = JSON.parse(fs.readFileSync(path.join(root, 'design/design.json'), 'utf8'))
const variables = (values) => Object.entries(values).map(([key, value]) => `--${key}:${value};`).join('')

function luminance(hex) {
  if (!/^#[0-9a-f]{6}$/i.test(hex)) throw new Error(`Invalid theme colour: ${hex}`)
  const channels = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255)
    .map((v) => v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4)
  return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722
}

function checkContrast(name, values) {
  const background = luminance(values.background)
  for (const [token, minimum] of [['foreground', 4.5], ['border', 3], ['primary', 3]]) {
    const colour = luminance(values[token])
    const ratio = (Math.max(background, colour) + 0.05) / (Math.min(background, colour) + 0.05)
    if (ratio < minimum) throw new Error(`${name} ${token} contrast is ${ratio.toFixed(2)}; need ${minimum}`)
  }
}

async function build() {
  checkLogoApproval(root)
  for (const [name, values] of Object.entries(design)) checkContrast(name, values)
  if (process.argv[2] === '--check') return
  fs.mkdirSync(out, { recursive: true })
  await esbuild.build({
    entryPoints: [path.join(root, 'renderer/player.tsx')],
    bundle: true, platform: 'browser', format: 'iife', target: 'chrome120',
    nodePaths: [modules], outfile: path.join(out, 'player.js'),
  })
  const source = fs.readFileSync(path.join(root, 'renderer/styles.css'), 'utf8')
    .replace('"tailwindcss"', `"${path.join(modules, 'tailwindcss/index.css')}"`)
  const themed = `${source}\n:root{${variables(design.light)}}\n@media (prefers-color-scheme:dark){:root{${variables(design.dark)}}}\n`
  const css = await postcss([tailwind()]).process(themed, { from: path.join(root, 'renderer/styles.css') })
  fs.writeFileSync(path.join(out, 'player.css'), css.css)
  fs.copyFileSync(path.join(root, 'renderer/index.html'), path.join(out, 'index.html'))
  fs.copyFileSync(path.join(root, 'assets/logo.svg'), path.join(out, 'logo.svg'))
  execFileSync('rsvg-convert', ['-w', '256', '-h', '256', '-o', path.join(out, 'logo.png'), path.join(out, 'logo.svg')])
}

build().catch((error) => { console.error(error); process.exitCode = 1 })
