// The test of systemap.config.configures for the text of pyproject.toml.
//
// systemap parses the file as TOML 1.0 (Python tomllib). The file configures
// systemap if it has a tool.systemap value, or if its tool value is not a
// table. If the text is not correct TOML, the file configures systemap only if
// the text contains "tool.systemap", as in systemap. A hooks module cannot
// import a package. Thus this module has a small TOML reader. It reads keys and
// tables, and it reads the syntax of each value, but it keeps no value.
//
// Known limit: this reader finds a second definition only if the full name of
// the table or the key is the same. TOML does not accept some other second
// definitions, for example a table header for a table that a dotted key made.
// For such a text, systemap examines the text for "tool.systemap", and this
// module uses the parsed result.

/** A text that is not correct TOML. */
class NotToml extends Error {}

const BARE = /[A-Za-z0-9_-]/
const SCALAR = /[A-Za-z0-9_+.:-]/
const DATE = /^\d{4}-\d{2}-\d{2}$/
const SCALAR_FORMS = [
  /^(true|false|[+-]?(inf|nan))$/,
  /^[+-]?(0|[1-9](_?\d)*)(\.\d(_?\d)*)?([eE][+-]?\d(_?\d)*)?$/,
  /^0x[0-9A-Fa-f](_?[0-9A-Fa-f])*$|^0o[0-7](_?[0-7])*$|^0b[01](_?[01])*$/,
  /^\d{4}-\d{2}-\d{2}([Tt ]\d{2}:\d{2}:\d{2}(\.\d+)?([Zz]|[+-]\d{2}:\d{2})?)?$/,
  /^\d{2}:\d{2}:\d{2}(\.\d+)?$/,
]
const ESCAPES: Record<string, string> = {
  b: '\b',
  t: '\t',
  n: '\n',
  f: '\f',
  r: '\r',
  '"': '"',
  '\\': '\\',
}

class Reader {
  at = 0
  /** The full names of the defined tables and keys, as JSON lists. */
  readonly defined = new Set<string>()
  isConfigured = false

  readonly text: string

  constructor(text: string) {
    this.text = text
  }

  char(): string {
    return this.text[this.at] ?? ''
  }

  has(word: string): boolean {
    return this.text.startsWith(word, this.at)
  }

  take(word: string): void {
    if (!this.has(word)) {
      throw new NotToml(`"${word}" is necessary at character ${this.at}.`)
    }
    this.at += word.length
  }

  spaces(): void {
    while (this.char() === ' ' || this.char() === '\t') {
      this.at += 1
    }
  }

  /** The end of an expression: spaces, a comment, and a newline or the end. */
  lineEnd(): void {
    this.spaces()
    if (this.char() === '#') {
      while (this.char() !== '' && this.char() !== '\n') {
        this.at += 1
      }
    }
    if (this.has('\r\n')) {
      this.at += 2
    } else if (this.char() === '\n') {
      this.at += 1
    } else if (this.char() !== '') {
      throw new NotToml(`The line continues at character ${this.at}.`)
    }
  }

  /** Spaces, newlines and comments in an array. */
  blanks(): void {
    for (;;) {
      this.spaces()
      if (this.char() === '#' || this.char() === '\n' || this.has('\r\n')) {
        this.lineEnd()
      } else {
        return
      }
    }
  }

  /** A record of one defined name. A name that is defined again is not TOML. */
  define(path: readonly string[], isTable: boolean): void {
    const name = JSON.stringify(path)
    if (this.defined.has(name)) {
      throw new NotToml(`${path.join('.')} is defined again.`)
    }
    this.defined.add(name)
    const [first, second] = path
    if (first === 'tool' && (second === 'systemap' || (path.length === 1 && !isTable))) {
      this.isConfigured = true
    }
  }
}

function escape(r: Reader): string {
  r.take('\\')
  const letter = r.char()
  if (letter in ESCAPES) {
    r.at += 1
    return ESCAPES[letter] ?? ''
  }
  const size = letter === 'u' ? 4 : letter === 'U' ? 8 : 0
  const digits = r.text.slice(r.at + 1, r.at + 1 + size)
  const code = Number.parseInt(digits, 16)
  const isScalar = code <= 0x10ffff && (code < 0xd800 || code > 0xdfff)
  if (size === 0 || !/^[0-9A-Fa-f]+$/.test(digits) || digits.length !== size || !isScalar) {
    throw new NotToml(`The escape at character ${r.at} is not correct.`)
  }
  r.at += 1 + size
  return String.fromCodePoint(code)
}

/** A string on one line: its value. */
function lineString(r: Reader): string {
  const quote = r.char()
  r.at += 1
  let value = ''
  while (r.char() !== quote) {
    if (r.char() === '' || r.char() === '\n') {
      throw new NotToml(`The string at character ${r.at} has no end.`)
    }
    if (quote === '"' && r.char() === '\\') {
      value += escape(r)
    } else {
      value += r.char()
      r.at += 1
    }
  }
  r.at += 1
  return value
}

/** A string on more than one line. The value is not necessary. */
function blockString(r: Reader): void {
  const quotes = r.text.slice(r.at, r.at + 3)
  r.at += 3
  for (;;) {
    if (r.char() === '') {
      throw new NotToml('A string on more than one line has no end.')
    }
    if (r.has(quotes)) {
      r.at += 3
      // One or two quotation marks before the end mark are part of the string.
      for (let n = 0; n < 2 && r.char() === quotes[0]; n += 1) {
        r.at += 1
      }
      return
    }
    r.at += quotes[0] === '"' && r.char() === '\\' ? 2 : 1
  }
}

function simpleKey(r: Reader): string {
  if (r.char() === '"' || r.char() === "'") {
    return lineString(r)
  }
  const start = r.at
  while (BARE.test(r.char())) {
    r.at += 1
  }
  if (r.at === start) {
    throw new NotToml(`A key is necessary at character ${r.at}.`)
  }
  return r.text.slice(start, r.at)
}

/** A dotted key, for example `tool."systemap".writing`. */
function key(r: Reader): string[] {
  const parts = [simpleKey(r)]
  for (;;) {
    r.spaces()
    if (r.char() !== '.') {
      return parts
    }
    r.at += 1
    r.spaces()
    parts.push(simpleKey(r))
  }
}

function scalar(r: Reader): void {
  const start = r.at
  while (SCALAR.test(r.char())) {
    r.at += 1
  }
  // A date and a time can have a space between them.
  if (DATE.test(r.text.slice(start, r.at)) && /^ \d/.test(r.text.slice(r.at, r.at + 2))) {
    r.at += 1
    while (SCALAR.test(r.char())) {
      r.at += 1
    }
  }
  const word = r.text.slice(start, r.at)
  if (!SCALAR_FORMS.some(form => form.test(word))) {
    throw new NotToml(`The value at character ${start} is not correct.`)
  }
}

function array(r: Reader): void {
  r.take('[')
  for (;;) {
    r.blanks()
    if (r.char() === ']') {
      break
    }
    value(r, undefined)
    r.blanks()
    if (r.char() !== ',') {
      break
    }
    r.at += 1
  }
  r.take(']')
}

function inlineTable(r: Reader, path: readonly string[] | undefined): void {
  r.take('{')
  r.spaces()
  if (r.char() !== '}') {
    for (;;) {
      keyValue(r, path)
      r.spaces()
      if (r.char() !== ',') {
        break
      }
      r.at += 1
      r.spaces()
    }
  }
  r.take('}')
}

/** A value. `path` is its full name, or undefined in an array. */
function value(r: Reader, path: readonly string[] | undefined): void {
  const isTable = r.char() === '{'
  if (path !== undefined) {
    r.define(path, isTable)
  }
  if (isTable) {
    inlineTable(r, path)
  } else if (r.char() === '[') {
    array(r)
  } else if (r.has('"""') || r.has("'''")) {
    blockString(r)
  } else if (r.char() === '"' || r.char() === "'") {
    lineString(r)
  } else {
    scalar(r)
  }
}

/** `key = value` in the table `table`, or `table` is undefined in an array. */
function keyValue(r: Reader, table: readonly string[] | undefined): void {
  const name = key(r)
  r.spaces()
  r.take('=')
  r.spaces()
  value(r, table === undefined ? undefined : [...table, ...name])
}

/** `[table]` or `[[table]]`: the full name of the table for the next keys. */
function header(r: Reader, count: number): string[] {
  const isList = r.has('[[')
  r.take(isList ? '[[' : '[')
  r.spaces()
  const name = key(r)
  r.take(isList ? ']]' : ']')
  if (!isList) {
    r.define(name, true)
    return name
  }
  // A list is not a table. Thus `[[tool]]` also configures systemap.
  if (name[0] === 'tool' && (name.length === 1 || name[1] === 'systemap')) {
    r.isConfigured = true
  }
  // Each table of a list has its own keys.
  return [...name, `[${count}]`]
}

function document(r: Reader): void {
  let table: string[] = []
  for (let count = 0; r.char() !== ''; count += 1) {
    r.spaces()
    if (r.char() === '[') {
      table = header(r, count)
    } else if (r.char() !== '#' && r.char() !== '\n' && !r.has('\r\n') && r.char() !== '') {
      keyValue(r, table)
    }
    r.lineEnd()
  }
}

/** True if systemap.config.configures gives True for this text of pyproject.toml. */
export function configures(text: string): boolean {
  const body = text.startsWith('﻿') ? text.slice(1) : text
  const r = new Reader(body)
  try {
    document(r)
  } catch (error) {
    if (error instanceof NotToml) {
      return body.includes('tool.systemap')
    }
    throw error
  }
  return r.isConfigured
}
