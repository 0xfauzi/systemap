# Make the first map

This test page tells the site generator how a guide page looks. It has a title, a summary, sections, a table, code, and links.

## Install systemap

Install the command. Then write the initial files:

```sh
uv tool install systemap
systemap init
```

The [check rules](reference.html#what-does-systemap-check-reject) tell you what `systemap check` rejects.
The [live example](../map/) shows the map of systemap itself.
The [next page](read-the-map.html#layers) gives the layers.

## Install systemap

A second heading with the same text gets the id `install-systemap-2`.

### `systemap extract [--check]`

| Option | Effect |
|---|---|
| `--check` | Exit 1 if the stored facts differ from the source tree. |

<!-- loader: update after the merge -->
The language policy is in [language.md](../../../../src/systemap/skill/references/language.md).

## Main

A heading with the text of a layout id gets a number after its id.

1. Run `systemap extract`.
2. Run `systemap check`.

> The model gives the order of these steps. It is not a record of program execution.
