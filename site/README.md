# The systemap website

This directory contains the source of the website at <https://0xfauzi.github.io/systemap/>.
GitHub Pages supplies the `docs/` directory of the `main` branch.
`site/build.py` writes the website into `docs/`.

## Make the website

```sh
uv run --group site python site/build.py
uv run --group site python site/build.py --check
```

The first command writes the files. The second command writes no file.
It exits 1 if a file in `docs/` is different from the build, or if a generated directory has an extra file.
`tests/test_site.py` does the same comparison.
After a change to a guide page, to `docs/reference.md`, or to `docs/benchmarks.md`, run the first command and commit the result.
The footer shows the version of the package, so a version change also changes the pages.

The build stops with exit 1 if a relative link or an anchor has no target.
The build also stops if a page loads a file from a different site.

## Files

| Source | Output |
|---|---|
| `site/index.html` | `docs/index.html`, the landing page |
| `site/pages/NN-slug.md` | `docs/guide/slug.html`, one guide page |
| `docs/reference.md` | `docs/guide/reference.html` |
| `docs/benchmarks.md` | `docs/guide/benchmarks.html` |
| all pages | `docs/guide/index.html`, the docs home |
| `site/site.css`, `src/systemap/theme.py`, `DESIGN.md` | `docs/assets/site.css` |
| `site/site.js` | `docs/assets/site.js` |
| `src/systemap/page_font.py` | `docs/assets/inter.woff2` |
| `src/systemap/fonts/Inter-OFL.txt` | `docs/assets/Inter-OFL.txt` |
| `src/systemap/page.py` (`mark_icon`), `theme.py` | `docs/assets/mark.svg`, the icon of the browser tab. The map page uses the same icon. |
| `site/delta.txt` | the recorded `systemap delta` output on the landing page |

The build owns `docs/index.html`, `docs/.nojekyll`, `docs/guide/`, and `docs/assets/`.
It does not change `docs/map/`, `docs/screenshots/`, or the `.md` files in `docs/`.

## Guide pages

A guide page is `site/pages/NN-slug.md`.
`NN` is two digits that give the order in the navigation.
`slug` gives the URL `guide/slug.html`. It contains lowercase letters, digits, and hyphens.
The slugs `index`, `reference`, and `benchmarks` are reserved.

The first line is `# Title`. The first paragraph after the title is the summary.
The docs home shows the summary under the title.
The pages use CommonMark, pipe tables, and fenced code blocks.
An HTML comment stays in the page.

## Links

Write a link relative to `docs/guide/`:

- Another guide page: `slug.html`.
- The reference: `reference.html#anchor`.
- The live example: `../map/`.

The build changes some links:

- A link to a Markdown file that the build renders goes to its page. For example, `../reference.md` becomes `reference.html`.
- A link to another file of the repository goes to that file on GitHub, on the `main` branch.

## Heading ids

The build gives each heading an id. These are the steps:

1. Take the text of the heading, with the text of its code spans.
2. Change the letters to lowercase.
3. Each group of ASCII letters and digits is a word. All other characters separate words.
4. Join the words with `-`.

If the heading has no word, the id is `section`.
If the id is already on the page, the build adds `-2`, `-3`, and so on.
The page layout uses the ids `main`, `side`, `toc`, `theme`, `top`, `content`, and `footer`.
A heading with one of these ids also gets `-2`.

Examples:

| Heading | Id |
|---|---|
| ``## What does `systemap check` reject?`` | `what-does-systemap-check-reject` |
| `` ### `systemap init [--no-ci \| --strict-ci]` `` | `systemap-init-no-ci-strict-ci` |
| `` ### `[delta] page_url` `` | `delta-page-url` |

The link check examines anchors only in the pages that the build makes.
The map page uses its anchors as view names, such as `#changes`.

## Design

The colors and the font stacks come from `src/systemap/theme.py`.
The radii, the spacing, and the type sizes come from the front matter of `DESIGN.md`.
The font is the Inter subset of the map page.
The site keeps the theme selection in the browser under the key of the map page, `systemap-theme`.
Thus one selection applies to the site and to the map page.
The site obeys the reduced motion setting of the browser.
