# The live map

`systemap live` renders the map of the working tree and supplies it on 127.0.0.1. It renders the map again after each change.

## Start the live map

Run the command in the repository. Then open the URL in a browser:

```text
$ systemap live
map: The live map is at http://127.0.0.1:8765/. Use Ctrl-C to stop the server.
map: The Changes view compares the working tree with main at the merge base 5e0837b.
map: The command renders version 1.
map: Version 1 is on the page (0.1 s). Map updates: 0. Changed components: CommandLine, OrderFiles, Orders.
```

A map update is a `systemap delta` line that needs an action.
Ctrl-C or SIGTERM stops the command with exit code 0. On Windows, use Ctrl-Break in place of SIGTERM.
In Claude Code, the plugin [starts this command](coding-agents.html#the-live-map-in-claude-code).

## Options

- `--port N`: the server port. The default is 8765. `0` selects an available port.
- `--base REF`: the base of the Changes view.
- `--no-watch`: do not scan the files. Render the page again only after `POST /refresh`.
- `--json`: write one JSON object on a line for each event.

The [reference](reference.html#systemap-live-port-8765-base-ref-no-watch-json) gives the default base and each JSON line.

## What the command writes

The command writes the pages and `change.svg` into a temporary directory, and deletes it when it stops.
It does not write the output directory, the facts file, or a tracked file.
It can add the facts of the merge base to a cache in `.systemap/facts/`. Git shows this directory as untracked unless a `.gitignore` file contains it.
If `systemap init` wrote the file `.systemap/.gitignore`, Git ignores this directory.

## When the command renders again

Without `--no-watch`, the command scans the configuration, model, source, and test files one time each second.
If a scan takes more than half a second, the next scan starts after two times the time of that scan.
When a scan finds a change and the next scan finds no more change, the command renders the page again.
If a scan fails, the command gives the error one time, and the scans continue.

If the command cannot render a version, the last page stays, and the command gives the error:

```text
map: The command could not render version 1. The page does not change.
map/model.py could not import: NameError: name 'Meanin' is not defined
```

If the first version fails, the page gives the error.

## The reload that keeps your view

When a newer version is on the server, a script keeps your view in the session storage of the browser.
Then it loads the page again. The new page puts back:

- the view and the layer,
- the selected component or flow,
- the sequence and its step,
- the camera of the map and of the change map. A camera at Fit stays at Fit.

If the new page does not have the selected item, nothing is selected.
A notice at the bottom left gives the first line of a render error.
If the connection to the command breaks, the script stops. The page does not load again.

## HTTP requests

Other programs can read the state with `GET /status` and `GET /events`, and ask for a version with `POST /refresh`.
The [reference](reference.html#systemap-live-port-8765-base-ref-no-watch-json) gives all requests and answers.

## Update time

[bench/jev/README.md](../../bench/jev/README.md) records these measurements on the systemap repository, with 4 processors and CPython 3.11.17.

| Measurement | Result |
|---|---|
| One render, no change from the base | 7.00 s |
| One render, 13 changed components | 8.09 s |
| From a file edit to the `rendered` line, with the file scan | 9.1 s |

Thus the command waits until the files stop changing.
With `--no-watch` and `POST /refresh`, it renders one time for each agent turn.

## The loopback Host rule

The server listens only on 127.0.0.1.
It answers only a request whose Host header is `127.0.0.1` or `localhost` with the server port. For another Host header, it answers 403.
Thus a web page that makes its own domain name point at 127.0.0.1 cannot read the map.
[Trust and security](trust-and-security.html#the-local-servers) gives more information.
