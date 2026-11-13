// Turns probe.html's dumped DOM into <prefix>.probe.json and a short <prefix>.probe.md.
import { readFileSync, writeFileSync } from 'node:fs';
const [dom, prefix] = process.argv.slice(2);
const m = /<pre id="out">([\s\S]*?)<\/pre>/.exec(readFileSync(dom, 'utf8'));
const raw = m && m[1].replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, '&');
if (!raw) process.exit(1);
const r = JSON.parse(raw);
writeFileSync(prefix + '.probe.json', JSON.stringify(r, null, 1));
const sevOrder = { high: 0, med: 1, low: 2 };
const L = [`# Probe: ${r.board} ${r.W}x${r.H} · ${r.frames.length} frames`, '',
  '| # | frame | x,y,w,h | art | biggest art | empty paper | voice line | hierarchy | centred | high/med/low |',
  '|---|---|---|---|---|---|---|---|---|---|'];
for (const f of r.frames) {
  const c = s => f.issues.filter(i => i.sev === s).length;
  const s = f.soul;
  L.push(`| ${f.i} | ${f.title} | ${f.frame.join(',')} | ${s.artShare} | ${s.biggestArt} | ${s.emptyPaper} | ${s.voice} | ${s.hierarchy} | ${s.centredShare} | ${c('high')}/${c('med')}/${c('low')} |`);
}
L.push('', 'Soul signals are measurements to look at, not verdicts: art < 0.15 with biggest art < 0.1 = art shrunk to icon size; empty paper > 0.55 = a mostly empty frame; voice none or < 28px on the signature frame = no voice; hierarchy < 1.6 = flat; centred > 0.5 = everything centred.', '');
for (const f of r.frames) {
  if (!f.issues.length) continue;
  L.push(`## ${f.i} · ${f.title}`);
  for (const i of f.issues.sort((a, b) => sevOrder[a.sev] - sevOrder[b.sev])) L.push(`- ${i.sev} · ${i.check} · ${i.what}${i.rect ? ' · at ' + i.rect.join(',') : ''}`);
  L.push('');
}
writeFileSync(prefix + '.probe.md', L.join('\n'));
