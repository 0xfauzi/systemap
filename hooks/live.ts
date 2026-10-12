// The parts of the systemap mod that use no engine interface: the command
// words, the JSON lines of `systemap live --json`, its /status answer, and
// the words of the line above the prompt. hooks/register.tsx uses them.

import type { SystemapLine, SystemapLive, SystemapPhase } from '../types'

/** The most characters that an `Svg` element takes as its source. */
export const SVG_LIMIT = 131072

/** A UTF-8 character has at most four bytes, so a larger file cannot fit. */
export const READ_LIMIT = 4 * SVG_LIMIT

/** The tools that can change files. A read-only Bash call does not count. */
export const FILE_TOOLS: ReadonlySet<string> = new Set([
  'Edit',
  'Write',
  'MultiEdit',
  'NotebookEdit',
  'Bash',
])

/** The phases in which a `systemap live` process of this module runs. */
export const RUNNING: ReadonlySet<SystemapPhase> = new Set([
  'starting',
  'rendering',
  'ready',
  'error',
])

export const OFF: SystemapLive = {
  phase: 'off',
  cwd: '',
  url: '',
  version: 0,
  updates: 0,
  lines: [],
  components: [],
  svg: '',
  svgBytes: 0,
  error: '',
  notice: '',
}

/** The `command` option split on spaces, `systemap` when it is empty. */
export function commandWords(command: unknown): string[] {
  const words =
    typeof command === 'string' ? command.split(' ').filter(word => word !== '') : []

  return words.length > 0 ? words : ['systemap']
}

export function liveArgv(command: unknown): string[] {
  return [...commandWords(command), 'live', '--port', '0', '--json', '--no-watch']
}

/** `[tool.systemap]` in pyproject.toml, as systemap's own config.find_root reads it. */
export function hasToolTable(pyproject: string): boolean {
  return pyproject.includes('[tool.systemap]')
}

export function firstLine(text: string): string {
  return (
    text
      .split('\n')
      .map(line => line.trim())
      .find(line => line !== '') ?? ''
  )
}

/** Gives the complete lines of a stream that arrives in pieces. */
export function lineSplitter(): { push: (text: string) => string[]; rest: () => string } {
  let rest = ''

  return {
    push: text => {
      const lines = (rest + text).split('\n')
      rest = lines.pop() ?? ''

      return lines
    },
    rest: () => rest,
  }
}

/**
 * The address of `Open map`: the page address with `localhost` for
 * 127.0.0.1, the same computer. Measured: Claude Code 2.1.286 to 2.1.288
 * refuse a Link to http: if its host is not localhost, and then draw no
 * band. Version 2.1.296 takes both.
 */
export function pageUrl(url: string): string {
  return url.replace(/^http:\/\/127\.0\.0\.1(?=[:/]|$)/, 'http://localhost')
}

export function joinUrl(url: string, path: string): string {
  return url.endsWith('/') ? `${url}${path}` : `${url}/${path}`
}

export type LiveEvent =
  | { event: 'serving'; url: string }
  | { event: 'rendering'; version: number }
  | {
      event: 'rendered'
      version: number
      updates: number
      components: string[]
      svg: string
      svgBytes: number
    }
  | { event: 'error'; version: number; text: string }
  | { event: 'stopped' }

type Fields = Record<string, unknown>

function asFields(value: unknown): Fields | undefined {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
    ? (value as Fields)
    : undefined
}

function text(value: unknown): string {
  return typeof value === 'string' ? value : ''
}

function count(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : 0
}

function texts(value: unknown): string[] {
  return Array.isArray(value) ? value.filter(item => typeof item === 'string') : []
}

function readJson(line: string): Fields | undefined {
  const trimmed = line.trim()
  if (!trimmed.startsWith('{')) {
    return undefined
  }
  try {
    return asFields(JSON.parse(trimmed))
  } catch {
    return undefined
  }
}

function rendered(fields: Fields): LiveEvent {
  return {
    event: 'rendered',
    version: count(fields.version),
    updates: count(fields.updates),
    components: texts(fields.components),
    svg: text(fields.svg),
    svgBytes: count(fields.svg_bytes),
  }
}

/** One JSON line of `systemap live --json`; undefined for any other line. */
export function parseEvent(line: string): LiveEvent | undefined {
  const fields = readJson(line)
  const version = count(fields?.version)
  switch (fields?.event) {
    case 'serving':
      return { event: 'serving', url: text(fields.url) }
    case 'rendering':
      return { event: 'rendering', version }
    case 'rendered':
      return rendered(fields)
    case 'error':
      return { event: 'error', version, text: text(fields.text) }
    case 'stopped':
      return { event: 'stopped' }
    default:
      return undefined
  }
}

/** The state after one JSON line. */
export function applyEvent(live: SystemapLive, event: LiveEvent): SystemapLive {
  switch (event.event) {
    case 'serving':
      return { ...live, url: event.url }
    case 'rendering':
      return { ...live, phase: 'rendering' }
    case 'rendered': {
      const { event: _, ...values } = event
      return { ...live, ...values, phase: 'ready', error: '' }
    }
    case 'error':
      return { ...live, phase: 'error', version: event.version, error: firstLine(event.text) }
    case 'stopped':
      return live
  }
}

export type LiveStatus = {
  version: number
  updates: number
  lines: SystemapLine[]
  components: string[]
  svg: string
  svgBytes: number
}

function line(value: unknown): SystemapLine | undefined {
  const fields = asFields(value)

  return fields === undefined
    ? undefined
    : { text: text(fields.text), action: text(fields.action) }
}

/** The answer of `GET /status`; undefined when it is not a JSON object. */
export function parseStatus(body: string): LiveStatus | undefined {
  const fields = readJson(body)
  if (fields === undefined) {
    return undefined
  }
  const lines = Array.isArray(fields.lines) ? fields.lines.map(line) : []

  return {
    version: count(fields.version),
    updates: count(fields.updates),
    lines: lines.filter(item => item !== undefined),
    components: texts(fields.components),
    svg: text(fields.svg),
    svgBytes: count(fields.svg_bytes),
  }
}

/**
 * The state with the values of a /status answer. The phase comes from the
 * JSON lines only, so an older answer cannot hide a render that runs now.
 */
export function applyStatus(live: SystemapLive, status: LiveStatus): SystemapLive {
  return status.version < live.version ? live : { ...live, ...status }
}

export type Ending = {
  command: string
  hasServed: boolean
  code: number | null
  signal: string | null
  reason: string
}

const SETTING = 'Set the "command" value in the plugin configuration.'

/** The line that the band shows after the process stopped or did not start. */
export function endNotice(ending: Ending): string {
  const why =
    firstLine(ending.reason) ||
    (ending.signal ? `signal ${ending.signal}` : '') ||
    (ending.code === null ? '' : `exit code ${ending.code}`)
  if (ending.hasServed) {
    return why ? `map: The live map stopped: ${why}` : 'map: The live map stopped.'
  }
  const start = `map: The command "${ending.command} live" did not start`

  return why ? `${start}: ${why}. ${SETTING}` : `${start}. ${SETTING}`
}

export function updateCount(updates: number): string {
  return updates === 1 ? '1 map update' : `${updates} map updates`
}

export type Band = {
  /** The words before the controls. */
  words: string
  /** Show `Open map` and `Show`. */
  hasLink: boolean
  /** Show `Start live map`. */
  canStart: boolean
}

/**
 * The phase to show. A running phase that no process of this module holds
 * (the module loaded again, and its process stopped with the old module) is
 * shown as `idle`.
 */
export function shownPhase(live: SystemapLive, isFollowing: boolean): SystemapPhase {
  return RUNNING.has(live.phase) && !isFollowing ? 'idle' : live.phase
}

/** The band above the prompt for a phase; undefined draws nothing. */
export function band(live: SystemapLive, phase: SystemapPhase): Band | undefined {
  const hasLink = live.url !== ''
  switch (phase) {
    case 'off':
      return undefined
    case 'idle':
      return { words: 'map: not started', hasLink: false, canStart: true }
    case 'starting':
    case 'rendering':
      return { words: 'map: rendering', hasLink, canStart: false }
    case 'ready':
      return { words: `map: live · ${updateCount(live.updates)}`, hasLink, canStart: false }
    case 'error':
      return { words: `map: not updated: ${live.error}`, hasLink, canStart: false }
    case 'missing':
    case 'stopped':
      return { words: live.notice, hasLink: false, canStart: true }
  }
}

/** What a screen reader says for the figure: the changed components. */
export function figureAlt(components: readonly string[]): string {
  return components.length > 0
    ? `System map. Changed components: ${components.join(', ')}.`
    : 'System map. No component changed.'
}
