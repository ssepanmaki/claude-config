// How many past subagent final messages the stop guard would send back.
import { readFileSync, readdirSync, existsSync, statSync } from 'node:fs';
import { join } from 'node:path';
const PROMISE = /\b(?:I'll|I will|let me|will (?:commit|report|check|continue)|once (?:it|they|the \w+) (?:finish|complete|pass)|(?:is|are) (?:still )?running in the background|wait(?:ing)? for (?:the|its|it))\b/i;
const root = join(process.env.USERPROFILE, '.claude', 'projects'); let n = 0, hit = [];
for (const p of readdirSync(root)) for (const s of readdirSync(join(root, p))) {
  const d = join(root, p, s, 'subagents'); if (!existsSync(d) || !statSync(d).isDirectory()) continue;
  for (const f of readdirSync(d).filter((x) => x.endsWith('.jsonl'))) {
    const meta = existsSync(join(d, f.replace('.jsonl', '.meta.json'))) ? JSON.parse(readFileSync(join(d, f.replace('.jsonl', '.meta.json')), 'utf8')) : {};
    if (['Explore', 'claude-code-guide', 'statusline-setup'].includes(meta.agentType)) continue;
    let last = '';
    for (const l of readFileSync(join(d, f), 'utf8').split('\n')) { try { const j = JSON.parse(l); if (j.type === 'assistant') { const t = (j.message.content || []).filter((x) => x.type === 'text').map((x) => x.text).join('\n'); if (t) last = t; } } catch {} }
    n++; if (PROMISE.test(last.slice(-400))) hit.push(last.slice(-140).replace(/\n/g, ' '));
  }
}
console.log(`${hit.length}/${n} would be sent back`); hit.slice(0, 25).forEach((h) => console.log(' -', h));
