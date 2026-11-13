import type { Register } from 'claude-code'

const CUT = [
  /<!--[\s\S]*?-->\s*/g,
  /This read was made at[\s\S]*?Verify anything surprising against primary sources before acting on it\.\s*/g,
]

const trim = (v: unknown): unknown =>
  typeof v === 'string' ? CUT.reduce((t, re) => t.replace(re, ''), v)
    : Array.isArray(v) ? v.map(trim)
      : v && typeof v === 'object' ? Object.fromEntries(Object.entries(v).map(([k, x]) => [k, trim(x)]))
        : v

export const register: Register = on => {
  on('tool.call', { tool: 'ReadNotifications' }, async ($, e, next) => {
    const r = await next(e)
    return 'result' in r && r.result !== undefined ? { ...r, result: trim(r.result) as typeof r.result, ref: undefined } : r
  }).catch(($, e, next) => next(e))
}
