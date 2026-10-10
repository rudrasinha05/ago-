// Developer-only syntax check; packages are installed into an isolated CI directory.
import {readFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';

const modules = process.argv[2];
if (!modules) throw new Error('Pass isolated node_modules directory');
const {JSDOM} = await import(pathToFileURL(resolve(modules, 'jsdom/lib/api.js')));
const dom = new JSDOM('<!doctype html><html><body></body></html>');
globalThis.window = dom.window;
globalThis.document = dom.window.document;
const {default: mermaid} = await import(
  pathToFileURL(resolve(modules, 'mermaid/dist/mermaid.esm.mjs')),
);
mermaid.initialize({startOnLoad: false, securityLevel: 'strict'});
const source = await readFile(
  new URL('../docs/architecture/SECTION_02_COMPONENT_VIEWS.md', import.meta.url), 'utf8',
);
const blocks = [...source.matchAll(/```mermaid\n([\s\S]*?)```/g)].map(m => m[1]);
if (blocks.length !== 6) throw new Error(`Expected six views, found ${blocks.length}`);
for (const [i, block] of blocks.entries()) {
  await mermaid.parse(block);
  console.log(`Section 2 Mermaid view ${i + 1}: parsed`);
}
