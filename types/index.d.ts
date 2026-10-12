// The session values of the systemap mod ($.state). hooks/register.tsx
// imports these types; other plugins can read the values.

/**
 * One map update from `systemap live`: the delta line and its action.
 */
export type SystemapLine = { text: string; action: string }

/**
 * Where the live map is in this session.
 *
 * `off`: the session directory is not a systemap repository.
 * `idle`: a systemap repository, and the live map did not start.
 * `starting`, `rendering`, `ready`, `error`: the `systemap live` process runs.
 * `missing`: the command did not start. `stopped`: the process stopped.
 */
export type SystemapPhase =
  | 'off'
  | 'idle'
  | 'starting'
  | 'rendering'
  | 'ready'
  | 'error'
  | 'missing'
  | 'stopped'

/**
 * What the mod knows about the `systemap live` process of this session.
 */
export type SystemapLive = {
  phase: SystemapPhase
  /** The session directory that has the systemap configuration; '' when none. */
  cwd: string
  /** The page address, `http://127.0.0.1:PORT/`; '' before the server listens. */
  url: string
  /** The render number of the last `rendered` or `error` line. */
  version: number
  /** The number of map updates that need an action. */
  updates: number
  lines: SystemapLine[]
  /** The components that the comparison marks as changed. */
  components: string[]
  /** The absolute path of change.svg. */
  svg: string
  svgBytes: number
  /** The first line of the last render error. */
  error: string
  /** The line for `missing` and `stopped`. */
  notice: string
}

/**
 * The text of change.svg for one render. `source` is '' when the figure is
 * too large for a pane (`isTooLarge`) or when the mod could not read it.
 */
export type SystemapFigure = { version: number; source: string; isTooLarge: boolean }

declare module 'claude-code' {
  interface PluginState {
    systemap: {
      live: SystemapLive
      changed: boolean
      figure: SystemapFigure
    }
  }
}
