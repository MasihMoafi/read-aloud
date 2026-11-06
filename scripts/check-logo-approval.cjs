const fs = require('node:fs')
const path = require('node:path')
const crypto = require('node:crypto')

function checkLogoApproval(root) {
  const logo = path.join(root, 'assets/logo.svg')
  const record = path.join(root, 'design/logo-approval.json')
  const hasLogo = fs.existsSync(logo)
  const hasRecord = fs.existsSync(record)
  if (!hasLogo && !hasRecord) return
  if (!hasLogo || !hasRecord) throw new Error('A logo requires a recorded user choice and matching SVG')
  const approval = JSON.parse(fs.readFileSync(record, 'utf8'))
  const hash = crypto.createHash('sha256').update(fs.readFileSync(logo)).digest('hex')
  if (typeof approval.choice !== 'string' || !approval.choice.trim() || approval.sha256 !== hash) {
    throw new Error('The installed logo does not match the recorded choice')
  }
}

if (require.main === module) checkLogoApproval(path.resolve(__dirname, '..'))
module.exports = checkLogoApproval
