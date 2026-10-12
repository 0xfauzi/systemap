# The live map

`systemap live` renders the map of the working tree and supplies it on 127.0.0.1. It renders the map again after each change.

A change is a change to a source, model, or configuration file.
The browser loads each new page and keeps your view. The command writes no tracked file.

## Start the live map

Run the command in the repository. Then open the URL in a browser:

```text
$ systemap live
map: The live map is at http://127.0.0.1:8765/. Use Ctrl-C to stop the server.
map: The Changes view compares the working tree with main at the merge base 5e0837b.
map: The command renders version 1.
map: Version 1 is on the page (0.1 s). Map updates: 0. Changed components: CommandLine, OrderFiles, Orders.
```

Each render makes a new version of the page.
A map update is a `systemap delta` line that needs an action, for the working tree and the merge base.
Ctrl-C or SIGTERM stops the command with exit code 0. On Windows, use Ctrl-Break in place of SIGTERM.

In Claude Code, the systemap plugin starts this command for you. [Coding agents](coding-agents.html#the-live-map-in-claude-code) tells how.

## Options

| Option | Effect |
|---|---|
| `--port N` | The server port. The default is 8765. `0` selects an available port. If the port is not available, the command exits 2. |
| `--base REF` | The base of the Changes view. The default is the first of `origin/HEAD`, `origin/main`, `main`, `origin/master`, and `master` that has a merge base with HEAD. |
| `--no-watch` | Do not scan the files. Render the page again only after `POST /refresh`. |
| `--json` | Write one JSON object on a line for each event. |

The [reference](reference.html#systemap-live-port-8765-base-ref-no-watch-json) gives each option and each JSON line.

## What the Changes view compares

The Changes view compares the working tree with the merge base of the base ref and HEAD.
The comparison includes the commits since the merge base and the edits that are not in a commit.
It also includes the untracked files that Git does not ignore.
If no base ref has a merge base with HEAD, the page has no revision comparison.

## What the command writes

The command writes the pages and `change.svg` into a temporary directory. It deletes the directory when it stops.
It does not write the output directory, the facts file, or a tracked file.

For the comparison, the command can add the facts of the merge base to a cache in `.systemap/facts/`.
Git shows this directory as untracked unless `.gitignore` contains it.

## When the command renders again

Without `--no-watch`, the command scans the files one time each second.
It scans the configuration files, the model files, and the source and test files.
When a scan finds a change and the next scan finds no more change, the command renders the page again:

```text
map: The command renders version 2.
map: Version 2 is on the page (0.1 s). Map updates: 1. Changed components: CommandLine, OrderFiles, Orders.
```

The command renders one version at a time.
A request during a render causes one more version after the current version.

If the command cannot render a version, the last page stays, and the command gives the error.
Examples are a model file that does not load, a source syntax error, and an extraction error:

```text
map: The command could not render version 1. The page does not change.
map/model.py could not import: NameError: name 'Meanin' is not defined
```

If the first version fails, the page gives the error. When you correct the error, the page shows the map.

## The reload that keeps your view

`systemap live` adds one script to each page that it supplies. The page from `systemap render` does not have this script.
When a newer version is on the server, the script keeps your view in the session storage of the browser. Then it loads the page again.

The new page puts back:

- the view: Map, Sequences, or Changes,
- the layer,
- the selected component or flow,
- the sequence and its step,
- the camera of the map and of the change map. A camera at Fit stays at Fit.

The script identifies a flow by its two components and its artifact, and a sequence by its identifier.
If the new page does not have the selected item, nothing is selected.

If the command cannot render a version, a notice at the bottom left gives the first line of the error.
If the connection to the command breaks, the script stops. The page does not load again.

## HTTP requests

Other programs can read the state of the live map. The Claude Code plugin uses these requests.

| Request | Answer |
|---|---|
| `GET /` | The page of the top map. Nested maps are at `<map id>/index.html`. |
| `GET /change.svg` | The change figure. If the comparison has no change, the system figure. |
| `GET /events` | Server-sent events: `rendered` after each version, and `error` if the command cannot render a version. |
| `POST /refresh` | Asks for a version. The answer is 202 with `{"queued": true}`. |
| `GET /status` | The state as JSON. |

`POST` to another path gives 404 with `{"error": "Use POST /refresh."}`.
This is a `GET /status` answer from the example project, with two of its four lines:

```json
{
    "version": 1,
    "state": "ready",
    "seconds": 0.13,
    "updates": 4,
    "lines": [
        {
            "text": "moved: shop.store -> shop.storage (same content). OrderFiles specifies shop.store in implemented_by. Change this claim to shop.storage in map/model.py",
            "action": "Change the module claim to the new name. Or put the module in the component for its task at this snapshot."
        },
        {
            "text": "added: shop.discounts, No component has a claim for it. Add it to a component implemented_by in map/model.py, or give a reason to ignore it in [coverage]",
            "action": "Add the module to the component for its task, or give a reason to ignore it in `[coverage]`."
        }
    ],
    "components": [
        "CommandLine",
        "OrderFiles"
    ],
    "error": "",
    "url": "http://127.0.0.1:8790/",
    "svg": "/tmp/systemap-live-aq122e_r/change.svg",
    "svg_bytes": 14636,
    "base": "main",
    "comparison_base": "5e0837b07a17f92ea02b1602ec4f0d134e8cfd6c"
}
```

With `--json`, the command writes the same events on standard output:

```text
{"event": "serving", "url": "http://127.0.0.1:8765/", "base": "main", "comparison_base": "5e0837b07a17f92ea02b1602ec4f0d134e8cfd6c"}
{"event": "rendering", "version": 1}
{"event": "rendered", "version": 1, "seconds": 0.11, "updates": 0, "components": ["CommandLine", "OrderFiles", "Orders"], "svg": "/tmp/systemap-live-79fpemzx/change.svg", "svg_bytes": 15042}
{"event": "stopped"}
```

## Update time

In the small example project above, each version took about 0.1 s. The systemap repository is larger.
`bench/jev/README.md` records measurements on the systemap repository: 86 modules at commit 7b29986, 87 with the live page module, 4 processors, and CPython 3.11.17.

| Measurement | Result |
|---|---|
| One render, no change from the base | 7.00 s |
| One render, 13 changed components | 8.09 s |
| From a file edit to the `rendered` line, with the file scan | 9.1 s |

The acceptance value for extraction and the compared page was 3.0 s or less. The measured time was 5.73 s, so the result failed.
For this reason, the command does not render while the files continue to change.
It renders after the files stop changing, or one time for each agent turn with `--no-watch` and `POST /refresh`.

## The loopback Host rule

The server listens only on 127.0.0.1.
It answers only a request whose Host header is `127.0.0.1` or `localhost` with the server port.
For another Host header, it answers 403 with "The server answers only requests to 127.0.0.1 or localhost."
Thus a web page that makes its own domain name point at 127.0.0.1 cannot read the map.
`systemap serve` has the same rule. [Trust and security](trust-and-security.html#the-local-servers) gives more information.
