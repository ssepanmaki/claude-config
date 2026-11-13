import type { Register } from 'claude-code'

const KEEP = new Set([
  'Bash', 'Read', 'Edit', 'Write', 'ToolSearch',
  'mcp__hearthbot__post_message', 'mcp__hearthbot__no_reply_needed',
  'mcp__hearthbot__update_progress_checklist', 'mcp__hearthbot__react',
])

const collapse = (text: string): string => {
  const names = text.match(/mcp__[A-Za-z0-9_-]+?__[A-Za-z0-9_.-]+/g) ?? []
  const groups = new Map<string, string[]>()
  for (const n of names) {
    const server = n.match(/^mcp__(.+?)__/)![1]
    groups.set(server, [...(groups.get(server) ?? []), n])
  }
  let out = text
  for (const [server, list] of groups) {
    if (list.length <= 5) continue
    const lines = out.split('\n')
    const first = lines.findIndex(l => l.includes(list[0]))
    const keep = lines.filter(l => !list.some(n => l.trim() === n))
    out = first < 0 ? out : [...keep.slice(0, first), `mcp__${server}__* (${list.length} tools)`, ...keep.slice(first)].join('\n')
  }
  return out
}

const TRIM: Record<string, (t: string) => string> = {
  deferred_tools_delta: collapse,
  skill_listing: t => `Skills (Skill tool): ${[...t.matchAll(/^- ([\w:-]+):/gm)].map(m => m[1]).join(', ')}`,
  agent_listing_delta: t => t.replace(/^(- [\w-]+: .{0,60}).*$/gm, '$1'),
}

type Ctx =Parameters<Parameters<Parameters<Register>[0]>[2]>[0]

const dumpDir = async ($: Ctx): Promise<string | null> => {
  const dir = (await $.env.get('LEAN_START_DUMP')) || `${await $.env.get('HOME')}/.claude/lean-start.dump`
  return (await $.fs.exists(dir)) ? dir : null
}

const dump = async ($: Ctx, file: string, data: unknown) => {
  try {
    const dir = await dumpDir($)
    if (dir) await $.fs.write(`${dir}/${file}`, JSON.stringify(data, null, 1))
  } catch {}
}

const tools: Record<string, unknown> = {}
const attachments: Record<string, unknown> = {}
const context: unknown[] = []

export const register: Register = on => {
  on('tool.describe', async ($, e, next) => {
    const r = await next(e)
    const deferred = !KEEP.has(e.tool)
    await dump($, 'tools.json', Object.assign(tools, { [e.tool]: { deferred, descChars: r.description.length } }))
    if (!deferred) return r
    return { ...r, isDeferred: true, breakPromptCache: true }
  }).catch(($, e, next) => next(e))

  on('prompt.attachment', async ($, e, next) => {
    const r = await next(e)
    if (r.text == null) return r
    await dump($, 'attachments.json', Object.assign(attachments, { [e.type + (e.agentId ? ':' + e.agentId : '')]: { chars: r.text.length, text: r.text } }))
    if (e.type === 'mcp_instructions_delta') return { ...r, text: null }
    const cut = TRIM[e.type]
    return cut ? { ...r, text: cut(r.text) } : r
  }).catch(($, e, next) => next(e))

  on('prompt.compose', async ($, e, next) => {
    const r = await next(e)
    await dump($, 'sections.json', r.sections.map(s => ({ id: s.id, scope: s.scope, chars: s.text.length, text: s.text })))
    return r
  }).catch(($, e, next) => next(e))

  on('prompt.context', async ($, e, next) => {
    const r = await next(e)
    context.length = 0
    context.push(...r.blocks.map(b => ({ name: b.name, chars: b.text.length, text: b.text })))
    await dump($, 'context.json', context)
    return r
  }).catch(($, e, next) => next(e))

  on('turn.step', async function* ($, e, next) {
    const r = yield* next(e)
    try {
      const dir = await dumpDir($)
      const u = r?.usage
      if (dir && u && !e.agentId) {
        const total = u.input_tokens + u.cache_read_input_tokens + u.cache_creation_input_tokens
        const file = `${dir}/usage.log`
        const old = (await $.fs.exists(file)) ? await $.fs.read(file) : ''
        await $.fs.write(file, `${old}${new Date().toISOString()} total=${total} input=${u.input_tokens} cache_read=${u.cache_read_input_tokens} cache_creation=${u.cache_creation_input_tokens}\n`)
      }
    } catch {}
    return r
  })
}
