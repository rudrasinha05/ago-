import assert from 'node:assert/strict';
import {mkdtempSync, mkdirSync, rmSync, writeFileSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {test} from 'node:test';
import {spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {inspectNextDependencies} from './ago_next_dependency_state.mjs';

function fixture() {
  const root = mkdtempSync(join(tmpdir(), 'ago-next-version-'));
  const packages = {
    '': {name: 'ago-monorepo'}, // Legal npm lockfile entry that trips Windows PS 5.1.
    'node_modules/next': {version: '16.4.3'}
  };
  for (const name of ['web', 'admin', 'docs']) {
    packages[`apps/${name}`] = {dependencies: {next: '16.4.3'}};
    mkdirSync(join(root, 'apps', name), {recursive: true});
    writeFileSync(join(root, 'apps', name, 'package.json'),
      JSON.stringify({dependencies: {next: '16.4.3'}}));
  }
  writeFileSync(join(root, 'package-lock.json'), JSON.stringify({packages}));
  const writeInstalled = version => {
    mkdirSync(join(root, 'node_modules', 'next'), {recursive: true});
    writeFileSync(join(root, 'node_modules', 'next', 'package.json'),
      JSON.stringify({version}));
  };
  return {root, writeInstalled};
}

test('stale Next.js install is detected and a corrected install is accepted', () => {
  const f = fixture();
  try {
    assert.deepEqual(inspectNextDependencies(f.root), {pinned:'16.4.3', installed:'missing'});
    f.writeInstalled('16.4.0');
    assert.deepEqual(inspectNextDependencies(f.root), {pinned:'16.4.3', installed:'16.4.0'});
    f.writeInstalled('16.4.3');
    assert.deepEqual(inspectNextDependencies(f.root), {pinned:'16.4.3', installed:'16.4.3'});
    writeFileSync(join(f.root, 'node_modules', 'next', 'package.json'), '{broken');
    assert.equal(inspectNextDependencies(f.root).installed, 'missing');
  } finally {
    rmSync(f.root, {recursive:true, force:true});
  }
});

test('mismatched Next.js workspace pin fails closed before npm ci', () => {
  const f = fixture();
  try {
    writeFileSync(join(f.root, 'apps', 'admin', 'package.json'),
      JSON.stringify({dependencies: {next:'16.4.0'}}));
    assert.throws(() => inspectNextDependencies(f.root),
      /Next.js version mismatch between admin and lockfile/);
  } finally {
    rmSync(f.root, {recursive:true, force:true});
  }
});

test('real repository lockfile parses through the Node CLI', () => {
  const script = fileURLToPath(new URL('./ago_next_dependency_state.mjs', import.meta.url));
  const result = spawnSync(process.execPath, [script], {encoding:'utf8'});
  assert.equal(result.status, 0, result.stderr);
  assert.match(result.stdout.trim(), /^\d+\.\d+\.\d+\|(missing|\d+\.\d+\.\d+)$/);
  assert.equal(result.stderr, '');
});
