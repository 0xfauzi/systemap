// Tests of the systemap mod with a fake `systemap live` process. The spawn
// stream, $.http.fetch, $.fs and the engine calls are hooks of the test, so
// no test starts a process or opens a network connection.
// Run them with `claude plugin test .` at the repository root.

import { describe, expect, mock, test } from 'claude-code/testing'
import type { Engine, MockClock } from 'claude-code/testing'
import type { On } from 'claude-code'

const PLUGIN = 'systemap'
const URL = 'http://127.0.0.1:41234/'
/** The address of Open map: localhost in place of 127.0.0.1. */
const PAGE = 'http://localhost:41234/'
const SVG_PATH = '/tmp/live/change.svg'
const SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"></svg>'
const LIVE_ARGS = ['live', '--port', '0', '--json', '--no-watch']
const SURFACES = ['terminal', 'desktop'] as const
/** The pane line when no render was good. */
const NO_RENDER = 'systemap did not render the map. Correct the cause. Then change a file.'
const LONG = 3_600_000
/** The time limit of a test in which the fake process runs. */
const SLOW = { timeoutMs: 30_000 }

const SERVING = { event: 'serving', url: URL, base: 'origin/main', comparison_base: 'abc' }
const RENDERING = { event: 'rendering', version: 1 }
const RENDERED = {
  event: 'rendered',
  version: 1,
  seconds: 5.7,
  updates: 3,
  components: ['Page', 'Render'],
  svg: SVG_PATH,
  svg_bytes: SVG.length,
}
const LINES = [
  { text: 'added: systemap.live, No component has a claim for it.', action: 'Add it to a component.' },
  { text: 'changed: Page', action: 'Examine the claims of Page.' },
  { text: 'removed: systemap.old', action: 'Remove its claim.' },
]
const STATUS = {
  version: 1,
  state: 'ready',
  seconds: 5.7,
  updates: 3,
  lines: LINES,
  components: ['Page', 'Render'],
  error: '',
  url: URL,
  svg: SVG_PATH,
  svg_bytes: SVG.length,
  base: 'origin/main',
  comparison_base: 'abc',
}

const BAND = {
  component: 'AbovePrompt',
  props: {
    hasSurvey: false,
    isWorking: false,
    maxRows: 10,
    bodyColumns: 100,
    scroll: { offset: 0, bodyRows: 10 },
    view: {},
  },
} as const

const PANE = {
  component: 'Pane',
  requestId: 'map',
  props: {
    title: 'Map',
    isFocused: false,
    bodyColumns: 80,
    placement: 'inline',
    scroll: { offset: 0, bodyRows: 30 },
    view: {},
  },
} as const

const SESSION = { cwd: '/repo', surface: 'terminal', isInteractive: true } as const
const TURN = { answer: 'Done.', durationMs: 1000, isAborted: false, turnId: 't', reason: 'answer' } as const
const MAPPED = { 'systemap.toml': 'name = "x"\n', [SVG_PATH]: SVG }

const line = (value: object) => `${JSON.stringify(value)}\n`

/** One step of the fake process: print a line, or wait on the test clock. */
type Step = { out: string } | { err: string } | { wait: number }

const READY: Step[] = [
  { out: line(SERVING) },
  { out: line(RENDERING) },
  { out: line(RENDERED) },
  { wait: LONG },
]

type Setup = {
  /** The files that exist, by path; a relative path is in the session directory. */
  files?: Record<string, string>
  /** The fake `systemap live`; 'missing' is a command that cannot start. */
  process?: Step[] | 'missing'
  /** The answer of GET /status; the default is STATUS. */
  status?: object
}

type World = {
  clock: MockClock
  spawned: string[][]
  posts: string[]
  gets: string[]
  commands: string[]
  panes: string[]
}

/** The engine and the computer beneath the plugin, from memory. */
function world(on: On, setup: Setup = {}): World {
  const files: Record<string, string> = setup.files ?? MAPPED
  const steps = setup.process ?? READY
  const clock = mock.clock(on)
  const found: World = { clock, spawned: [], posts: [], gets: [], commands: [], panes: [] }

  // The engine gives a relative path to the hooks as an absolute path in the
  // session directory. A key with no '/' is a file in that directory.
  const fileOf = (path: string) => files[path] ?? files[path.slice(path.lastIndexOf('/') + 1)]
  on('fs.exists', ($, e) => ({ value: fileOf(e.path) !== undefined }))
  on('fs.read', ($, e) => {
    const text = fileOf(e.path)
    return text === undefined ? { deny: `ENOENT: ${e.path}` } : { value: text }
  })
  on('command.register', ($, e) => {
    found.commands.push(e.name)
    return { value: { command: e.name } }
  })
  on('ui.open', ($, e) => {
    found.panes.push(e.id)
    return { value: { isPlaced: true as const } }
  })
  on('http.fetch', ($, e) => {
    const isPost = e.init?.method === 'POST'
    ;(isPost ? found.posts : found.gets).push(e.url)
    const body = e.url.endsWith('/status') ? (setup.status ?? STATUS) : { queued: true }
    return { value: { status: isPost ? 202 : 200, ok: true, headers: {}, text: JSON.stringify(body) } }
  })
  on('process.spawn', async function* ($, e) {
    found.spawned.push([...e.argv])
    if (steps === 'missing') {
      // The engine rejects the first pull of a command that cannot start.
      return { deny: 'spawn systemap ENOENT' }
    }
    for (const step of steps) {
      if ('out' in step) {
        yield { stream: 'stdout' as const, text: step.out }
      } else if ('err' in step) {
        yield { stream: 'stderr' as const, text: step.err }
      } else {
        await clock.sleep(step.wait)
      }
    }
    return { value: { code: 1, signal: null } }
  })
  on('session.start', ($, e) => ({ cwd: e.cwd }))
  on('turn.complete', () => ({ text: '' }))
  on('command.run', () => ({ text: 'no command' }))
  on('tool.call', ($, e) =>
    e.tool === 'Bash' ? { result: undefined, isReadOnly: true as const } : { result: undefined },
  )
  on('ui.render', { component: 'AbovePrompt' }, ($, e) => {
    const { Text } = $.ui.resolve(e)
    return <Text>engine band</Text>
  })

  return found
}

type Surface = (typeof SURFACES)[number]

/**
 * The band as one text (its Text elements and control labels in order), its
 * Button keys, and its link. One read: each act waits until the plugin's
 * work is quiet, about half a second while the fake process runs.
 */
async function band($: Engine, surface: Surface = 'terminal') {
  const ui = await $.ui.mount({ plugin: PLUGIN, surface, ...BAND })
  const drawn = await ui.findAll({})
  await ui.unmount()
  const words = drawn
    .filter(one => ['Text', 'Button', 'Link', 'Markdown'].includes(one.type))
    // A Markdown link reads as its label.
    .map(one => one.text.replace(/\[([^\]]*)\]\([^)]*\)/g, '$1'))
    .join('')
  const buttons = drawn.filter(one => one.type === 'Button').map(one => one.key)
  const link = drawn.find(one => one.type === (surface === 'terminal' ? 'Link' : 'Markdown'))
  return { words, buttons, link }
}

async function startLive($: Engine) {
  await $.session.start(SESSION)
  const ui = await $.ui.mount({ plugin: PLUGIN, surface: 'terminal', ...BAND })
  await ui.press({ key: 'start' })
  await ui.unmount()
}

async function runMap($: Engine) {
  return $.command.run({
    command: 'map',
    args: '',
    origin: { kind: 'composer' },
    presentation: { isFullscreen: false, columns: 120 },
  })
}

describe('a directory without systemap', () => {
  test('starts nothing, registers nothing and draws nothing', async ($, on) => {
    const found = world(on, { files: { 'pyproject.toml': '[project]\nname = "x"\n' } })
    await $.session.start(SESSION)
    expect(found.spawned).toEqual([])
    expect(found.commands).toEqual([])
    for (const surface of SURFACES) {
      const drawn = await band($, surface)
      expect(drawn.words).toBe('engine band')
      expect(drawn.buttons).toEqual([])
    }
  })

  test('pyproject.toml with [tool.systemap] is a systemap repository', async ($, on) => {
    world(on, { files: { 'pyproject.toml': '[tool.systemap]\nname = "x"\n' } })
    await $.session.start(SESSION)
    expect((await band($)).words).toBe('map: not started · Start live map')
  })
})

/**
 * Each pyproject.toml text and the answer of systemap.config.configures for it
 * (issue 95). The acceptance value: the mod gives the same answer for each text.
 * For a text that is not correct TOML, the answer is true only if the text
 * contains "tool.systemap".
 */
const PYPROJECTS: [string, boolean][] = [
  ['[tool."systemap"]\nname = "x"\n', true],
  ['[tool.systemap.writing]\nprofile = "plain"\n', true],
  ['[project]\nname = "x"\n# [tool.systemap]\n', false],
  ['[project]\ndescription = """\n[tool.systemap]\n"""\n', false],
  ["[project]\ndescription = '''\n[tool.systemap]\n'''\n", false],
  ['[tool]\nsystemap = { name = "x" }\n', true],
  ['tool.systemap.name = "x"\n', true],
  ['[ tool . systemap ]\n', true],
  ['[tool.other]\nx = "[tool.systemap]"\n', false],
  ['[tool.systemap\n', true],
  ['[tool."systemap"\n', false],
  ['[[tool.systemap.figures]]\nout = "a"\n', true],
  ['tool = 1\n', true],
  ['[[tool]]\nx = 1\n', true],
  ['[tool]\n"systemap" = {}\n', true],
  ['[tool.ruff]\nline-length = 1\n', false],
  ["['tool'.'systemap']\n", true],
  ['[tool]\nsystemap.writing.profile = "plain"\n', true],
  ['[project]\nx = [\n  "[tool.systemap]",\n  # [tool.systemap]\n]\n', false],
  ['\ufeff[tool.systemap]\n', true],
  ['[tool.systemap]\n[tool.systemap]\n', true],
  ['"tool.systemap" = 1\n', false],
  ['[tool]\nsystemaps = 1\n', false],
  ['tool = { systemap = { name = "x" } }\n', true],
  ['tool = { ruff = { line-length = 1 } }\n', false],
  ['["tool"."\\u0073ystemap"]\n', true],
  ['[project]\nname = "x"\n[tool.uv]\ndev = ["a", \'b\', { x = 1 }]\n', false],
  ['x = 1979-05-27T07:32:00Z\ny = -inf\nz = 0x1F\n[tool.systemap]\n', true],
  ['[project] # [tool.systemap]\nname = "x"\n', false],
  ['[project]\nname = "a\\"[tool.systemap]"\n', false],
  ['[project]\nx = \'a\' # "\n[tool.systemap]\n', true],
]

describe('the configuration in pyproject.toml, as systemap finds it', () => {
  for (const [text, isMapped] of PYPROJECTS) {
    test(`${JSON.stringify(text)} is ${isMapped ? '' : 'not '}a configuration`, async ($, on) => {
      world(on, { files: { 'pyproject.toml': text } })
      await $.session.start(SESSION)
      const words = isMapped ? 'map: not started · Start live map' : 'engine band'
      expect((await band($)).words).toBe(words)
    })
  }
})

describe('the start of the live map', () => {
  test('session.start without autostart starts nothing and offers a start', async ($, on) => {
    const found = world(on)
    await $.session.start(SESSION)
    expect(found.spawned).toEqual([])
    expect(found.commands).toEqual(['map'])
    for (const surface of SURFACES) {
      const drawn = await band($, surface)
      expect(drawn.words).toBe('map: not started · Start live map')
      expect(drawn.buttons).toEqual(['start'])
    }
  })

  test('the Start button starts one process with the command option', { ...SLOW, options: { command: 'uv run systemap' } }, async ($, on) => {
    const found = world(on)
    await $.session.start(SESSION)
    const ui = await $.ui.mount({ plugin: PLUGIN, surface: 'terminal', ...BAND })
    await ui.press({ key: 'start' })
    expect(found.spawned).toEqual([['uv', 'run', 'systemap', ...LIVE_ARGS]])
    await ui.unmount()
    // The band has no Start button now, and a second start does not start a second process.
    expect((await band($)).buttons).toEqual(['show'])
    await runMap($)
    expect(found.spawned).toHaveLength(1)
  })

  // Issue 95: the acceptance value is one argument for each quoted path.
  const COMMANDS: [string, string[]][] = [
    ['"/Applications/Map Tools/systemap"', ['/Applications/Map Tools/systemap']],
    ["'/Applications/Map Tools/systemap'", ['/Applications/Map Tools/systemap']],
    ['uv run --directory "/Users/a b/tools" systemap', ['uv', 'run', '--directory', '/Users/a b/tools', 'systemap']],
    ['  uvx   systemap ', ['uvx', 'systemap']],
  ]
  for (const [command, words] of COMMANDS) {
    test(`the command ${command} gives ${words.length} words`, { ...SLOW, options: { command } }, async ($, on) => {
      const found = world(on)
      await $.session.start(SESSION)
      await runMap($)
      expect(found.spawned).toEqual([[...words, ...LIVE_ARGS]])
    })
  }

  test('/map starts one process and opens the pane', SLOW, async ($, on) => {
    const found = world(on)
    await $.session.start(SESSION)
    const answer = await runMap($)
    expect(answer.text).toBe('The map pane is open.')
    await runMap($)
    expect(found.spawned).toEqual([['systemap', ...LIVE_ARGS]])
    expect(found.panes).toEqual(['map', 'map'])
  })

  test('session.start with autostart starts the process', { ...SLOW, options: { autostart: true } }, async ($, on) => {
    const found = world(on)
    await $.session.start(SESSION)
    await found.clock.settle()
    expect(found.spawned).toEqual([['systemap', ...LIVE_ARGS]])
    expect((await band($)).words).toBe('map: live · 3 map updates · Open map · Show')
  })

  test('a command that cannot start gives one line until a turn is complete', SLOW, async ($, on) => {
    world(on, { process: 'missing' })
    await startLive($)
    const { words, buttons } = await band($)
    expect(words).toStartWith('map: The command "systemap live" did not start')
    expect(words).toContain('Set the "command" value in the plugin configuration.')
    expect(buttons).toEqual(['start'])
    await $.turn.complete(TURN)
    expect((await band($)).words).toBe('map: not started · Start live map')
  })
})

describe('the band above the prompt', () => {
  test('a rendered line changes the band', SLOW, async ($, on) => {
    const found = world(on, {
      process: [{ out: line(SERVING) }, { out: line(RENDERING) }, { wait: 1000 }, { out: line(RENDERED) }, { wait: LONG }],
    })
    await startLive($)
    expect((await band($)).words).toBe('map: rendering · Open map · Show')
    await found.clock.advance(1000)
    for (const surface of SURFACES) {
      const drawn = await band($, surface)
      expect(drawn.words).toBe('map: live · 3 map updates · Open map · Show')
      expect(drawn.buttons).toEqual(['show'])
      const target = surface === 'terminal' ? drawn.link?.props.href : drawn.link?.props.text
      expect(String(target)).toContain(PAGE)
    }
    expect(found.gets).toContain(`${URL}status`)
  })

  test('a render error gives its first line', SLOW, async ($, on) => {
    world(on, {
      process: [
        { out: line(SERVING) },
        { out: line({ event: 'error', version: 1, text: 'map/model.py line 3: invalid syntax\nTraceback' }) },
        { wait: LONG },
      ],
    })
    await startLive($)
    expect((await band($)).words).toBe('map: not updated: map/model.py line 3: invalid syntax · Open map · Show')
  })

  test('Show opens the pane', SLOW, async ($, on) => {
    const found = world(on)
    await $.session.start(SESSION)
    const ui = await $.ui.mount({ plugin: PLUGIN, surface: 'terminal', ...BAND })
    await ui.press({ key: 'start' })
    await ui.press({ key: 'show' })
    await ui.unmount()
    expect(found.panes).toEqual(['map'])
  })
})

describe('the request for a new render', () => {
  test('a turn that changed files posts /refresh, a turn with no change does not', SLOW, async ($, on) => {
    const found = world(on)
    await startLive($)
    await $.turn.complete(TURN)
    expect(found.posts).toEqual([])

    await $.tool.call({ tool: 'Bash', command: 'ls' })
    await $.turn.complete(TURN)
    expect(found.posts).toEqual([])

    await $.tool.call({ tool: 'Edit', file_path: '/repo/a.py', old_string: 'a', new_string: 'b' })
    await $.turn.complete(TURN)
    expect(found.posts).toEqual([`${URL}refresh`])

    await $.turn.complete(TURN)
    expect(found.posts).toEqual([`${URL}refresh`])
  })

  test('a change before the start does not post', async ($, on) => {
    const found = world(on)
    await $.session.start(SESSION)
    await $.tool.call({ tool: 'Write', file_path: '/repo/a.py', content: 'x' })
    await $.turn.complete(TURN)
    expect(found.posts).toEqual([])
    expect(found.spawned).toEqual([])
  })
})

/** Every element of the map pane on a surface, from one read. */
async function pane($: Engine, surface: Surface) {
  const ui = await $.ui.mount({ plugin: PLUGIN, surface, ...PANE })
  const drawn = await ui.findAll({})
  await ui.unmount()
  return {
    texts: drawn.filter(one => one.type === 'Text').map(one => one.text),
    of: (type: string) => drawn.find(one => one.type === type),
  }
}

describe('the map pane', () => {
  test('terminal: the map update lines and the link, with no figure', SLOW, async ($, on) => {
    world(on)
    await startLive($)
    const { texts, of } = await pane($, 'terminal')
    expect(of('Link')?.props.href).toBe(PAGE)
    expect(of('Svg')).toBeUndefined()
    expect(texts).toContain('3 map updates:')
    for (const one of LINES) {
      expect(texts).toContain(one.text)
      expect(texts).toContain(one.action)
    }
  })

  test('desktop: the figure with the changed components, then the lines', SLOW, async ($, on) => {
    world(on)
    await startLive($)
    const { texts, of } = await pane($, 'desktop')
    const svg = of('Svg')
    expect(svg?.props.source).toBe(SVG)
    expect(svg?.props.alt).toBe('System map. Changed components: Page, Render.')
    expect(svg?.props.isInteractive).toBe(true)
    expect(String(of('Markdown')?.props.text)).toContain(PAGE)
    for (const one of LINES) {
      expect(texts).toContain(one.text)
      expect(texts).toContain(one.action)
    }
  })

  // Issue 95: the acceptance value is the cause, and no "The map is current." line.
  test('a failed first render shows the error and its cause', SLOW, async ($, on) => {
    const cause = 'map/model.py line 3: invalid syntax'
    const failed = { state: 'error', updates: 0, lines: [], components: [], error: cause, svg: '', svg_bytes: 0 }
    world(on, {
      process: [
        { out: line(SERVING) },
        { out: line(RENDERING) },
        { out: line({ event: 'error', version: 1, text: `${cause}\nTraceback` }) },
        { wait: LONG },
      ],
      status: { ...STATUS, ...failed },
    })
    await startLive($)
    for (const surface of SURFACES) {
      const { texts } = await pane($, surface)
      expect(texts).not.toContain('The map is current.')
      expect(texts).toContain(`map: not updated: ${cause}`)
      expect(texts).toContain(NO_RENDER)
    }
  })

  test('a figure larger than 131,072 characters is text and the link', SLOW, async ($, on) => {
    const large = `<svg>${'x'.repeat(131_072)}</svg>`
    world(on, { files: { ...MAPPED, [SVG_PATH]: large } })
    await startLive($)
    const { texts, of } = await pane($, 'desktop')
    expect(of('Svg')).toBeUndefined()
    expect(texts).toContain('The map is too large for this pane. To see it, use Open map.')
    expect(String(of('Markdown')?.props.text)).toContain(PAGE)
  })
})
