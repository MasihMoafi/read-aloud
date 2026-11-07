// The TypeScript main process is compiled alongside the player.
require(require('node:path').join(process.env.READ_ALOUD_BUILD, 'main.cjs'))
