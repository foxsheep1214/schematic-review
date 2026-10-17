// Usage: node downgrade.mjs <converter.js> <file.kicad_sch>...  (rewrites in place to KiCad 7)
import { readFileSync, writeFileSync } from 'node:fs';
const [conv, ...files] = process.argv.slice(2);
const { convertKicad } = await import(conv);
for (const f of files) {
  const r = await convertKicad(readFileSync(f, 'utf8'), 'KICAD7', f);
  writeFileSync(f, r.output);
  console.log(f, 'warnings:', r.warnings.length ? r.warnings.join(' | ') : 'none');
}
