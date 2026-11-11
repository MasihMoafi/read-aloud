// Read Aloud takes the shared parts of ~/Desktop/p/shared-system (skills/shared-system, requirements 1, 6 and 7): the UI
// lint runs here with today's findings listed in ui-check.known.json (the list may only shrink), and the generated copy
// must match its source. Where the shared folder is absent (a fresh clone, CI), the copy is used as it is.
import test from 'node:test';
import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

const root = path.resolve(import.meta.dirname, '..');
const run = (script: string, ...args: string[]) => spawnSync(process.execPath, [path.join(root, script), ...args], { cwd: root, encoding: 'utf8' });

test('the UI lint finds nothing beyond the known findings', () => {
  const lint = run('scripts/ui-lint.mts');
  assert.equal(lint.status, 0, lint.stdout + lint.stderr);
});

test('the generated copy of the UI lint matches its source', () => {
  const sync = run('scripts/ui-lint-sync.mts', '--check');
  assert.equal(sync.status, 0, sync.stdout + sync.stderr);
});

// SHARED_SYSTEM points the check below at another copy of the shared folder (to try a change in isolation).
const shared = process.env.SHARED_SYSTEM ?? path.join(os.homedir(), 'Desktop/p/shared-system');

test('the shared spacing in styles.css is the one design.json writes', async t => {
  const json = path.join(shared, 'design/design.json');
  if (!fs.existsSync(json)) return t.skip('shared folder absent; styles.css is used as it is');
  if (!JSON.parse(fs.readFileSync(json, 'utf8')).sites['read-aloud']) return t.skip('read-aloud is not registered in design.json yet');
  // Build into a throwaway copy, so the check never writes into a checkout.
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'read-aloud-design-'));
  t.after(() => fs.rmSync(home, { recursive: true, force: true }));
  const file = path.join(home, 'read-aloud/renderer/styles.css');
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.copyFileSync(path.join(root, 'renderer/styles.css'), file);
  const { build } = await import(pathToFileURL(path.join(shared, 'design/design.mjs')).href) as { build(json: string, home: string, only: string[]): Promise<string[]> };
  assert.deepEqual(await build(json, home, ['read-aloud']), [], 'styles.css differs from design.json; run `shared-design build`, never edit the region by hand');
});
