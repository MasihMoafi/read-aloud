import { strict as assert } from 'node:assert'
import { createHash } from 'node:crypto'
import { mkdtemp, readFile, readdir, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { test } from 'node:test'
import { downloadModelFiles } from '../electron/model-download.ts'

const contents = Buffer.from('verified model bytes')
const sha256 = createHash('sha256').update(contents).digest('hex')

test('model downloads verify bytes and keep failures out of the final path', async (t) => {
  const directory = await mkdtemp(join(tmpdir(), 'read-aloud-download-'))
  t.after(async () => { await rm(directory, { recursive: true, force: true }) })
  t.mock.method(globalThis, 'fetch', async (input) => {
    const url = String(input)
    if (url.endsWith('/offline')) throw new TypeError('network unavailable')
    if (url.endsWith('/partial')) {
      let sent = false
      const body = new ReadableStream({ pull(controller) {
        if (!sent) { sent = true; controller.enqueue(contents); return }
        controller.error(new Error('connection interrupted'))
      } })
      return new Response(body, { headers: { 'content-length': String(contents.length * 2) } })
    }
    return new Response(contents, { headers: { 'content-length': String(contents.length) } })
  })
  const target = join(directory, 'model.bin')
  const file = (endpoint: string, hash = sha256) => [{ name: 'model.bin', url: `https://example.test/${endpoint}`, sha256: hash }]

  await assert.rejects(downloadModelFiles(directory, file('good', '0'.repeat(64))), /checksum/i)
  assert.deepEqual(await readdir(directory), [])
  await assert.rejects(downloadModelFiles(directory, file('partial')), /interrupted/i)
  assert.deepEqual(await readdir(directory), [])
  const offlineProgress: number[] = []
  await assert.rejects(downloadModelFiles(directory, file('offline'), (state) => offlineProgress.push(state.received)), /network unavailable/i)
  assert.deepEqual(offlineProgress, [0], 'progress appears before the network request fails')
  assert.deepEqual(await readdir(directory), [])
  const progress: number[] = []
  await downloadModelFiles(directory, file('good'), (state) => progress.push(state.received))
  assert.deepEqual(await readFile(target), contents)
  assert(progress.includes(contents.length))
  await downloadModelFiles(directory, file('offline'))
  await writeFile(target, 'corrupt existing file')
  await assert.rejects(downloadModelFiles(directory, file('offline')), /network unavailable/i)
  assert.equal((await readFile(target)).toString(), 'corrupt existing file')
  await downloadModelFiles(directory, file('good'))
  assert.deepEqual(await readFile(target), contents)
})
