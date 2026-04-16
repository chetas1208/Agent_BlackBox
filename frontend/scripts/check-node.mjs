#!/usr/bin/env node
/** Nuxt 3.21+ CLI uses util.styleText (Node 20.12+). */
const [major, minor] = process.version.slice(1).split('.').map(Number)
const ok = major > 20 || (major === 20 && minor >= 12)
if (!ok) {
  console.error(`\n  Node.js 20.12+ required (you have ${process.version}).`)
  console.error('  From frontend/: nvm use   (see .nvmrc)')
  console.error('  Or: export PATH="/opt/homebrew/opt/node@20/bin:$PATH"\n')
  process.exit(1)
}
