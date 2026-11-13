// Builds a PDF of board fixes from an audit dir: per board its verdict and soul scores, then per finding
// what was wrong, the fix, and the before (zoom) and after images found next to the findings file.
// Usage: node fixes-pdf.mjs <audit_dir> <out.pdf> [title]
import { readFileSync, writeFileSync, readdirSync, existsSync } from 'node:fs';
import { join, resolve, basename } from 'node:path';
import { execFileSync } from 'node:child_process';
import { pathToFileURL } from 'node:url';
const [dir, out, title = 'Board fixes'] = process.argv.slice(2);
const D = resolve(dir), files = readdirSync(D);
const esc = s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const img = p => { if (!p) return ''; const f = existsSync(p) ? p : join(D, basename(p)); return existsSync(f) ? `<img src="${pathToFileURL(f).href}">` : ''; };
let body = `<h1>${esc(title)}</h1><p class="m">${new Date().toISOString().slice(0, 10)} · ${esc(D)}</p>`;
for (const fm of files.filter(f => f.endsWith('.findings.md')).sort()) {
  const b = fm.replace('.findings.md', ''), t = readFileSync(join(D, fm), 'utf8');
  const lines = t.split('\n');
  body += `<section class="board"><h2>${esc(b)}</h2><p class="m">${esc(lines[0] || '')}</p>`;
  const soul = lines.find(l => /^soul:/i.test(l)); if (soul) body += `<p class="m">${esc(soul)}</p>`;
  for (const blk of t.split(/^### /m).slice(1)) {
    const [head, ...rest] = blk.split('\n'), txt = rest.join('\n');
    const id = (/^(f\d+)/.exec(head) || [])[1];
    const field = k => { const m = new RegExp('^' + k + ':\\s*([\\s\\S]*?)(?=\\n[A-Z][a-z]+:|\\n*$)', 'm').exec(txt); return m ? m[1].trim() : ''; };
    const zoom = (/zoom:\s*(\S+)/.exec(txt) || [])[1];
    const status = (/^(fixed|still:.*)$/im.exec(txt) || [])[1] || '';
    const after = files.filter(f => id && f.startsWith(`${b}-${id}-`) && /after|cmp|compare|squint/i.test(f) && f.endsWith('.png')).sort();
    body += `<div class="f"><h3>${esc(head)}${status ? ` <span class="s">${esc(status)}</span>` : ''}</h3>`
      + ['Rule', 'Seen', 'Fix'].map(k => field(k) ? `<p><b>${k}</b> ${esc(field(k))}</p>` : '').join('')
      + `<div class="imgs">${zoom ? `<figure>${img(zoom)}<figcaption>before</figcaption></figure>` : ''}`
      + after.map(a => `<figure>${img(join(D, a))}<figcaption>${esc(a.replace(b + '-' + id + '-', '').replace('.png', ''))}</figcaption></figure>`).join('')
      + `</div></div>`;
  }
  // re-check lines: "f3 fixed: what changed" / "f2 still: why"
  for (const l of lines) {
    const m = /^(f\d+)\s+([^:]{1,40}):\s*(.*)$/.exec(l.trim()); if (!m) continue;
    const [, id, st, what] = m;
    const before = files.find(f => f === `${b}-${id}.png`);
    const after = files.filter(f => f.startsWith(`${b}-${id}-`) && f.endsWith('.png')).sort();
    body += `<div class="f"><h3>${esc(id)} <span class="s">${esc(st)}</span></h3><p>${esc(what)}</p><div class="imgs">`
      + (before ? `<figure>${img(join(D, before))}<figcaption>before</figcaption></figure>` : '')
      + after.map(a => `<figure>${img(join(D, a))}<figcaption>${esc(a.replace(b + '-' + id + '-', '').replace('.png', ''))}</figcaption></figure>`).join('')
      + `</div></div>`;
  }
  body += `</section>`;
}
const html = `<!doctype html><meta charset="utf-8"><style>
@page{size:A4 landscape;margin:14mm}body{font:11pt/1.45 Jost,system-ui,sans-serif;color:#14213d}
h1{font:500 28pt 'Cormorant Garamond',Georgia,serif;margin:0}h2{font:500 22pt 'Cormorant Garamond',Georgia,serif;margin:0 0 4px}
.board{break-before:page}.m{color:#5f6778;margin:2px 0}.f{break-inside:avoid;border-top:1px solid #d9d7cf;padding:10px 0}
h3{font-size:12pt;margin:0 0 4px}.s{color:#1d5fa6;font-weight:500}p{margin:3px 0}
.imgs{display:flex;gap:10px;align-items:flex-start;margin-top:6px}figure{margin:0;flex:1;min-width:0}img{max-width:100%;max-height:105mm;border:1px solid #d9d7cf}
figcaption{font-size:9pt;color:#5f6778}</style>${body}`;
const h = join(D, 'fixes.html'); writeFileSync(h, html);
const edge = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
execFileSync(edge, ['--headless=new', '--disable-gpu', '--no-pdf-header-footer', '--allow-file-access-from-files', `--user-data-dir=${join(D, '.pdfprof')}`, `--print-to-pdf=${resolve(out)}`, pathToFileURL(h).href], { stdio: 'ignore', timeout: 120000 });
console.log(resolve(out));
