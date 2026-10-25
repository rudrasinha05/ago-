#!/usr/bin/env node
/**
 * Windows PowerShell 5.1 cannot ConvertFrom-Json some npm lockfiles (for example
 * an empty-string package key). Parse lockfiles in Node, without modifying data.
 * Print one small pipe-delimited line: pinned_version|installed_version_or_missing.
 */
import {readFileSync} from 'node:fs';
import {dirname, join, resolve} from 'node:path';
import {fileURLToPath} from 'node:url';

const repositoryRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..');

function readJson(path) {
  return JSON.parse(readFileSync(path, 'utf8'));
}

export function inspectNextDependencies(root = repositoryRoot) {
  const lock = readJson(join(root, 'package-lock.json'));
  const pinned = lock?.packages?.['node_modules/next']?.version;
  if (typeof pinned !== 'string' || !/^\d+\.\d+\.\d+(?:-[\w.-]+)?$/.test(pinned)) {
    throw new Error('Next.js lockfile entry is missing or invalid');
  }
  for (const workspace of ['web', 'admin', 'docs']) {
    const manifest = readJson(join(root, 'apps', workspace, 'package.json'));
    if (manifest?.dependencies?.next !== pinned ||
        lock?.packages?.[`apps/${workspace}`]?.dependencies?.next !== pinned) {
      throw new Error(`Next.js version mismatch between ${workspace} and lockfile`);
    }
  }
  let installed = 'missing';
  try {
    const version = readJson(join(root, 'node_modules', 'next', 'package.json'))?.version;
    if (typeof version === 'string' && /^\d+\.\d+\.\d+(?:-[\w.-]+)?$/.test(version)) {
      installed = version;
    }
  } catch {
    // Missing/corrupt node_modules is recoverable: the launcher will run npm ci.
  }
  return {pinned, installed};
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const state = inspectNextDependencies();
    process.stdout.write(`${state.pinned}|${state.installed}\n`);
  } catch (error) {
    // Do not print the contents of lockfiles or environment variables.
    console.error(`AGO pinned dependency check failed: ${error.message}`);
    process.exitCode = 1;
  }
}
