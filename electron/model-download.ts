import { createHash, randomUUID } from 'node:crypto'
import { createReadStream, createWriteStream } from 'node:fs'
import { mkdir, rename, rm } from 'node:fs/promises'
import { basename, join } from 'node:path'
import { Readable, Transform } from 'node:stream'
import { pipeline } from 'node:stream/promises'

export type ModelFile = { name: string; url: string; sha256: string }
export type DownloadProgress = { name: string; received: number; total: number | null }

const release = 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0'
export const MODEL_FILES = [
  { name: 'kokoro-v1.0.onnx', url: `${release}/kokoro-v1.0.onnx`, sha256: '7d5df8ecf7d4b1878015a32686053fd0eebe2bc377234608764cc0ef3636a6c5', size: 325532387 },
  { name: 'voices-v1.0.bin', url: `${release}/voices-v1.0.bin`, sha256: 'bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d', size: 28214398 },
] satisfies (ModelFile & { size: number })[]

async function matches(path: string, expected: string): Promise<boolean> {
  const hash = createHash('sha256')
  try {
    for await (const chunk of createReadStream(path)) hash.update(chunk)
    return hash.digest('hex') === expected
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === 'ENOENT') return false
    throw error
  }
}

/** Install verified assets atomically; concurrent processes may safely download the same asset. */
export async function downloadModelFiles(directory: string, files: ModelFile[], onProgress: (progress: DownloadProgress) => void = () => {}): Promise<void> {
  await mkdir(directory, { recursive: true, mode: 0o700 })
  for (const file of files) {
    if (basename(file.name) !== file.name || !/^[a-f0-9]{64}$/.test(file.sha256)) throw new Error('Invalid model manifest')
    const destination = join(directory, file.name)
    if (await matches(destination, file.sha256)) continue
    const temporary = join(directory, `.${file.name}.${randomUUID()}.partial`)
    try {
      onProgress({ name: file.name, received: 0, total: null })
      const response = await fetch(file.url, { signal: AbortSignal.timeout(600_000) })
      if (!response.ok || !response.body) throw new Error(`Download failed for ${file.name}: HTTP ${response.status}`)
      const length = response.headers.get('content-length')
      const total = length && Number.isSafeInteger(Number(length)) ? Number(length) : null
      let received = 0
      const hash = createHash('sha256')
      const meter = new Transform({ transform(chunk, _encoding, callback) {
        received += chunk.length
        hash.update(chunk)
        onProgress({ name: file.name, received, total })
        callback(null, chunk)
      } })
      onProgress({ name: file.name, received, total })
      await pipeline(Readable.fromWeb(response.body as import('node:stream/web').ReadableStream), meter, createWriteStream(temporary, { flags: 'wx', mode: 0o600 }))
      if (total !== null && received !== total) throw new Error(`Incomplete download for ${file.name}`)
      if (hash.digest('hex') !== file.sha256) throw new Error(`Checksum mismatch for ${file.name}`)
      await rename(temporary, destination)
    } finally {
      await rm(temporary, { force: true })
    }
  }
}
