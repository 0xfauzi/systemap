// The systemap mod: the live map of a systemap repository in Claude Code.
//
// In a repository with systemap.toml, or pyproject.toml with [tool.systemap],
// the band above the prompt shows `map: not started` and a Button that starts
// `systemap live`. The process stays open and serves on the loopback address,
// so it starts only on a press, on /map, or with the `autostart` option.
// After a turn that changed files, the mod asks the process for a new
// render. The band shows the state and the number of map updates, and /map
// shows change.svg and the map update lines in a pane.

import { atom, read, update } from 'claude-code'
import type { EngineInterface, Register, ResolveInput } from 'claude-code'

import type { SystemapFigure, SystemapLive } from '../types'
import {
  FILE_TOOLS,
  OFF,
  READ_LIMIT,
  SVG_LIMIT,
  applyEvent,
  applyStatus,
  band,
  commandWords,
  endNotice,
  figureAlt,
  hasToolTable,
  joinUrl,
  lineSplitter,
  liveArgv,
  pageUrl,
  parseEvent,
  parseStatus,
  shownPhase,
  updateCount,
} from './live'
import type { LiveEvent } from './live'

const NO_FIGURE: SystemapFigure = { version: 0, source: '', isTooLarge: false }

const live = atom({ plugin: 'systemap', key: 'live' } as const, OFF)
const changed = atom({ plugin: 'systemap', key: 'changed' } as const, false)
const figure = atom({ plugin: 'systemap', key: 'figure' } as const, NO_FIGURE)

type Engine = EngineInterface

async function isMapped($: Engine): Promise<boolean> {
  if (await $.fs.exists('systemap.toml')) {
    return true
  }
  const pyproject = await $.fs.read('pyproject.toml').catch(() => '')

  return hasToolTable(pyproject)
}

async function readStatus($: Engine): Promise<void> {
  const { url } = await read($, live)
  if (url === '') {
    return
  }
  const answer = await $.http.fetch(joinUrl(url, 'status')).catch(() => undefined)
  const status = answer?.ok === true ? parseStatus(answer.text) : undefined
  if (status !== undefined) {
    await update($, live, value => applyStatus(value, status))
  }
}

async function readFigure($: Engine): Promise<void> {
  const { svg, svgBytes, version } = await read($, live)
  if (svg === '') {
    return
  }
  const source = svgBytes > READ_LIMIT ? '' : await $.fs.read(svg).catch(() => '')
  const isTooLarge = svgBytes > READ_LIMIT || source.length > SVG_LIMIT
  await update($, figure, () => ({ version, source: isTooLarge ? '' : source, isTooLarge }))
}

async function onEvent($: Engine, event: LiveEvent): Promise<void> {
  await update($, live, value => applyEvent(value, event))
  if (event.event === 'serving' || event.event === 'rendered') {
    await readStatus($)
    await readFigure($)
  }
}

/**
 * `Open map`. A remote surface draws a Link to an address that is not https:
 * as plain text, so there the link is Markdown, which draws an http: link.
 */
function link($: Engine, e: ResolveInput, url: string) {
  if (e.surface === 'terminal') {
    const { Link } = $.ui.resolve(e)
    return <Link href={pageUrl(url)} label="Open map" />
  }
  const { Markdown } = $.ui.resolve(e)
  return <Markdown text={`[Open map](${pageUrl(url)})`} />
}

/**
 * The values of this load of the module. The engine loads the module again
 * in a new environment after a change, so a new load starts from these
 * values: the process of the old load stopped with it.
 */
const run = {
  argv: liveArgv(undefined),
  command: 'systemap',
  /** True while a `systemap live` process of this load runs. */
  isFollowing: false,
}

async function follow($: Engine, cwd: string): Promise<void> {
  const stdout = lineSplitter()
  const stderr = lineSplitter()
  let reason = ''
  let hasServed = false
  let code: number | null = null
  let signal: string | null = null
  try {
    const child = $.process.spawn({ argv: run.argv, cwd })
    for await (const piece of child) {
      if (piece.stream === 'stderr') {
        reason = stderr.push(piece.text).findLast(text => text.trim() !== '')?.trim() ?? reason
        continue
      }
      for (const text of stdout.push(piece.text)) {
        const event = parseEvent(text)
        if (event !== undefined) {
          hasServed ||= event.event === 'serving'
          await onEvent($, event)
        }
      }
    }
    ;({ code, signal } = await child.result)
  } catch (error) {
    reason ||= error instanceof Error ? error.message : String(error)
  }
  run.isFollowing = false
  const why = stderr.rest().trim() || reason
  const notice = endNotice({ command: run.command, hasServed, code, signal, reason: why })
  const phase = hasServed ? 'stopped' : 'missing'
  await update($, live, (value): SystemapLive => ({ ...value, phase, notice }))
}

/** Starts `systemap live` once. A second call while it runs does nothing. */
async function start($: Engine): Promise<void> {
  if (run.isFollowing) {
    return
  }
  run.isFollowing = true
  const { cwd } = await read($, live)
  if (cwd === '') {
    run.isFollowing = false
    return
  }
  await update($, live, (value): SystemapLive => ({ ...OFF, cwd: value.cwd, phase: 'starting' }))
  await update($, figure, () => NO_FIGURE)
  // The last state write fails when the module unloads first; nothing is left to show then.
  void follow($, cwd).catch(() => undefined)
}

async function afterTurn($: Engine): Promise<void> {
  const value = await read($, live)
  if (value.phase === 'missing' || value.phase === 'stopped') {
    // The line about a failed start or a stop shows until one turn is complete.
    await update($, live, (now): SystemapLive => ({ ...now, phase: 'idle', notice: '' }))
    return
  }
  if (!run.isFollowing || value.url === '' || !(await read($, changed))) {
    return
  }
  await update($, changed, () => false)
  await $.http.fetch(joinUrl(value.url, 'refresh'), { method: 'POST' }).catch(() => undefined)
}

async function openPane($: Engine): Promise<void> {
  await $.ui.open({ id: 'map', title: 'Map' })
}

export const register: Register = (on, options) => {
  run.argv = liveArgv(options.command)
  run.command = commandWords(options.command).join(' ')
  run.isFollowing = false

  on('session.start', async ($, e, next) => {
    const started = await next(e)
    if (!(await isMapped($))) {
      return started
    }
    await update($, live, (): SystemapLive => ({ ...OFF, cwd: e.cwd, phase: 'idle' }))
    await update($, figure, () => NO_FIGURE)
    await $.command.register({
      name: 'map',
      description: 'Starts the live system map if it is not started, and shows it in a pane.',
    })
    if (options.autostart === true) {
      await start($)
    }

    return started
  })

  on('command.run', { command: 'map' }, async $ => {
    await start($)
    await openPane($)

    return { text: 'The map pane is open.' }
  })

  on('tool.call', async ($, e, next) => {
    const done = await next(e)
    const canChange = FILE_TOOLS.has(String(e.tool)) && done.isReadOnly !== true
    if (run.isFollowing && canChange && done.deny === undefined) {
      await update($, changed, () => true)
    }

    return done
  }).catch(($, e, next) => next(e))

  on('turn.complete', async ($, e, next) => {
    const done = await next(e)
    await afterTurn($)

    return done
  })

  on('ui.render', { component: 'AbovePrompt' }, async ($, e, next) => {
    const value = await read($, live)
    const shown = band(value, shownPhase(value, run.isFollowing))
    if (e.props.hasSurvey || shown === undefined) {
      return next(e)
    }
    const { Box, Button, Text } = $.ui.resolve(e)

    return (
      <Box flexDirection="row">
        <Text wrap="truncate-end">{shown.words}</Text>
        {shown.hasLink && <Text> · </Text>}
        {shown.hasLink && link($, e, value.url)}
        {shown.hasLink && <Text> · </Text>}
        {shown.hasLink && (
          <Button key="show" label="Show" plain onPress={() => void openPane($)} />
        )}
        {shown.canStart && <Text> · </Text>}
        {shown.canStart && (
          <Button key="start" label="Start live map" plain onPress={() => void start($)} />
        )}
      </Box>
    )
  })

  on('ui.render', { component: 'Pane', requestId: 'map' }, async ($, e) => {
    const value = await read($, live)
    const phase = shownPhase(value, run.isFollowing)
    const shown = band(value, phase)
    const { Box, Text } = $.ui.resolve(e)
    const lines = value.lines.map(one => (
      <Box flexDirection="column">
        <Text>{one.text}</Text>
        <Text dimColor>{one.action}</Text>
      </Box>
    ))
    const hasMap = phase === 'ready' || phase === 'error' || phase === 'rendering'
    const updates =
      value.updates === 0 ? 'The map is current.' : `${updateCount(value.updates)}:`
    const body = (
      <Box flexDirection="column">
        <Text>{shown?.words ?? 'map: not started'}</Text>
        {hasMap && value.url !== '' && link($, e, value.url)}
        {hasMap && value.version > 0 && <Text bold>{updates}</Text>}
        {hasMap && lines}
      </Box>
    )
    if (e.surface === 'terminal' || !hasMap) {
      return body
    }
    const { Svg } = $.ui.resolve(e)
    const drawn = await read($, figure)
    const picture =
      drawn.source !== '' ? (
        <Svg source={drawn.source} alt={figureAlt(value.components)} isInteractive />
      ) : (
        <Text>
          {drawn.isTooLarge
            ? 'The map is too large for this pane. To see it, use Open map.'
            : 'The map figure is not available.'}
        </Text>
      )

    return (
      <Box flexDirection="column">
        {picture}
        {body}
      </Box>
    )
  })
}
