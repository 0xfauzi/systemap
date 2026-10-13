"""The facts file: its fields, its read and write steps, and the extraction summary.

`FIELDS` gives each field that extraction writes. The skill schema reference comes from
this table. A test compares the reference with the table. The functions in this module
do not examine a language name, a file suffix, or source syntax.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from systemap import file_write
from systemap.source_facts import empty_markers

# Every field the extractor writes: (scope, field, what it holds). The
# scopes are the file itself, each module record under `components`, and
# each record under `entry_points`. `facts_doc` renders this table for the
# skill's schema reference; the test compares the rendered text with the
# shipped reference and the table with what `build` actually writes.
FIELDS: tuple[tuple[str, str, str], ...] = (
    (
        "facts",
        "version",
        "The facts format is 11, with portable syntax hashes, compiler provenance, "
        "module completeness, the folder package in `package`, `call_sites`, `types`, "
        "`type_only`, `same_as`, and decorators in the `api` fingerprints. "
        "Each re-export has `defined_in` and `defined_as`. Each unknown record has a "
        "`cause`: `read`, `encoding`, `syntax`, `declaration`, `target`, "
        "`declaration file`, `script file`, `package`, `binding`, or `reexport`. "
        "`extract --check` marks older formats stale",
    ),
    (
        "facts",
        "built_at_commit",
        "The commit read during extraction (`HEAD`), or empty outside Git. The page "
        "prints `facts from <sha>`. Extraction occurs before the commit that records the facts",
    ),
    ("facts", "packages", "The import names of package roots"),
    (
        "facts",
        "provenance",
        "The parser, the compiler settings, and the extraction inputs. A change to the "
        "extraction inputs makes a new source review necessary, even without source-file "
        "changes. A parser or compiler change alone does not, because these values can be "
        "different on another computer",
    ),
    (
        "facts",
        "tests_dirs",
        "Root-relative test directories: configured `tests_dir`, or every directory "
        "with the name `tests` or `test`",
    ),
    ("facts", "spec_sections", "The `##` headings in `spec_path`, with `level` and `title`"),
    ("facts", "entry_points", "One record for each entry point, with the fields below"),
    (
        "facts",
        "entry_point_issues",
        "Package entry targets or Python decorators with unresolved framework "
        "bindings. Each record has `kind`, `name`, `target`, `reason`, and `cause`. "
        "The list is empty if there are none",
    ),
    (
        "facts",
        "test_file_issues",
        "Test files that could not be read or parsed. Each record has `file`, and a "
        "`problem` with `line`, `reason`, `source`, and `cause`. "
        "The test functions of these files are not known. `check` prints these records "
        "and does not fail. The Python adapter does not write an empty list",
    ),
    (
        "facts",
        "config_issues",
        "The configuration packages that a configuration file extends, and that the adapter "
        "cannot read. Each record has `file`, `reference`, and `cause`. Only the TypeScript "
        "adapter writes this field, for an npm package in the `extends` key of a tsconfig "
        "file. The list is empty if there are none",
    ),
    ("facts", "components", "One module record for each dotted name, with the fields below"),
    ("module", "id", "The dotted module name"),
    ("module", "file", "The root-relative source path"),
    (
        "module",
        "package",
        "The dotted name of the package that contains the module. The language adapter "
        "writes it. A dot in a file name does not change it. A Python `__init__` module "
        "is in the parent package of its own package. A package root gives its own name",
    ),
    ("module", "plane", "The second module-name segment if `planes` includes it, or `core`"),
    ("module", "loc", "The file line count"),
    (
        "module",
        "sha",
        "The first twelve hex digits of the source SHA-1. This is the change-detector key",
    ),
    (
        "module",
        "source_sha256",
        "The full SHA-256 of UTF-8 source text with normalized newlines, for source references",
    ),
    (
        "module",
        "syntax_sha",
        "The parsed-syntax digest for source review. Comments and text format do not change it",
    ),
    (
        "module",
        "docstring",
        "The first paragraph of the module description, with a length limit. The Python "
        "adapter reads the module docstring. The TypeScript adapter reads the first "
        "documentation comment",
    ),
    (
        "module",
        "functions",
        "Public functions with `name` and `signature`. A function with overload "
        "signatures has one record for each signature, and one record in `names`",
    ),
    (
        "module",
        "classes",
        "Public class declarations other than errors, with `name` and public method "
        "signatures in `methods`. A type declaration that is not a class is in `types`",
    ),
    (
        "module",
        "errors",
        "Public classes with Error or Exception in their names or bases. They use the "
        "same fields as classes",
    ),
    (
        "module",
        "types",
        "Public type declarations that are not classes, with `name`, `category`, and public "
        "method signatures in `methods`. The category is `interface`, `enum`, or "
        "`type_alias`. The TypeScript adapter records the three categories. The Python "
        "adapter records the `type` statement as `type_alias`. Python 3.11 cannot parse "
        "this statement",
    ),
    ("module", "constants", "The first 14 UPPER_CASE assignments, with `name` and `value`"),
    (
        "module",
        "names",
        "Public module-level names in source order, with `kind`: `function`, `class`, "
        "`error`, `type` (a record in `types`), `constant` (UPPER_CASE), or `object` (other "
        "assignments such as `app`). TypeScript uses `unknown` for unresolved kinds. "
        "A package `__init__` "
        "includes local re-exports, with `reexport_of` and the kind in their source module. A "
        "full-module import uses kind `module`. Each re-export and each local alias has "
        "`defined_in` and `defined_as`: the module and the symbol that define it, through "
        "all re-exports and aliases. `defined_as` is `*` for a full module. The two values "
        "are `null` if the defining module is not known. A `*` re-export of the module does not "
        "give a name that has `star_export` set to `false`. A name with `star_export` set to "
        "`null` can be in the `*` re-export or not. The TypeScript adapter sets `false` for "
        "`default`. The Python adapter sets the value from `__all__`. A Python name that is "
        "not in `__all__` stays in `names`, because an import of that name can use it. "
        "`type_only` is `true` for a type-only export. A type-only export is not an entry "
        "point, because the emitted code has no value for it. A name without `type_only` "
        "is not type-only. Python has no type-only export. `entry` and `interface` "
        "can use these names",
    ),
    (
        "module",
        "api",
        "Full export identities for public-surface comparisons: exported name, "
        "display bucket, and declaration fingerprint. The fingerprint includes "
        "decorators. It does not include callable bodies. A `*` re-export has the "
        "name `*`, because one module cannot supply the names that it gives",
    ),
    ("module", "executes", "Python-only: a top-level call makes a package initializer nonempty"),
    (
        "module",
        "empty_marker",
        "`true` for a module that only marks a package and holds no code: a Python "
        "`__init__.py` file or a TypeScript `index` file without statements. A Python "
        "docstring, `pass`, `__future__` import, and literal value for a dunder name such "
        "as `__all__` are not statements for this rule. Coverage does not include these "
        "modules",
    ),
    (
        "module",
        "unknown",
        "TypeScript surface entries with unresolved syntax or kinds. Each has a "
        "source line, reason, short source excerpt, and `cause`. A parse record also has "
        "`parser`, the parser version. The finding line gives only the reason. The line, "
        "the excerpt, and the parser version go into rows below the line",
    ),
    (
        "module",
        "uses",
        "Imported local modules with the names taken from each. `*` means the full module",
    ),
    (
        "module",
        "call_sites",
        "The local names that the module gets from a name of a module in `uses`, and the "
        "lines that use them. Each record has `local`, `target`, `name` (`*` for the full "
        "module), `bound`, `line`, and `uses`. `bound` is `import` for a name that an import "
        "statement makes, or for a re-export without a local name, such as `export { a } "
        "from`. It is `value` for a name that gets its value or type from that "
        "name, such as `ledger` after `ledger = Ledger()`. `line` is the binding line. Each "
        "use is `[line, function line, property]`. The function line is the line of the "
        "named function or method that contains the use, or 0. The property is the "
        "attribute that the use reads, or an empty string. The value is `null` if the "
        "source did not parse",
    ),
    ("module", "imports", "The keys of `uses`"),
    ("module", "imported_by", "Local modules that import this module"),
    (
        "module",
        "external",
        "Third-party dotted import names, such as `anthropic` or `google.adk`. "
        "Standard-library and local-package imports are excluded. `model sdk` "
        "findings read this field",
    ),
    (
        "module",
        "tests_total",
        "The number of test functions with an import reference to this module",
    ),
    ("module", "tests_primary", "The number of those functions in a file with the module name"),
    ("module", "tests", "Up to 25 test names, with primary tests first"),
    (
        "module",
        "tests_digest",
        "A digest of every qualified test identity. It also includes hidden identities",
    ),
    (
        "module",
        "parse_error",
        "Python source read or parse errors, with line, parser version, and `cause`. "
        "Other systemap modules read `completeness`",
    ),
    (
        "module",
        "completeness",
        "The read condition of the module, with the same meaning for each language. "
        "`parsed` is `false` if the extractor could not read or parse all of the source, "
        "and `line`, `reason`, and `cause` then give the first problem. Such a module does "
        "not reject the map. `unresolved_imports` lists "
        "each local import, as the source writes it, that has no module in the facts. A "
        "local import is a relative import, a path, a TypeScript path alias, or a name below a "
        "package root. If `parsed` is `false`, the import list is not known and is `null`. "
        "Third-party packages, standard-library modules, Node.js built-in modules, and imports "
        "with a calculated module name are not in the list",
    ),
    (
        "entry point",
        "kind",
        "`console_script`, `main_module`, `main_function`, `subcommand`, `public_function`, "
        "`route`, `command`, `task`, or `plugin`",
    ),
    (
        "entry point",
        "name",
        "The script name, `python -m` command, `main`, subcommand name, route, command "
        "name, plugin hook, or function name",
    ),
    ("entry point", "module", "The module that defines the entry point"),
    (
        "entry point",
        "target",
        "The console-script function, the console script for a subcommand, or the "
        "registered function. It is empty for other kinds",
    ),
    (
        "entry point",
        "label",
        "The display name that the language adapter gives to the entry point. A sequence "
        "can name it in `starts`",
    ),
    (
        "entry point",
        "symbol",
        "The name in `module` that the entry point starts, such as the console-script "
        "function or a public function. It is an empty string when the entry point starts "
        "no single name, for example a package bin or a `__main__` module that starts the "
        "full module, or a subcommand. A symbol claim includes the entry point only when "
        "the module and this name agree. If the field is missing, the name is not known. "
        "Then no symbol claim includes the entry point",
    ),
    (
        "entry point",
        "same_as",
        "The identity of a different entry point that starts the same operation. The "
        "language adapter writes it only from an accurate indication. The Python adapter "
        "writes it for a console script, a `main` function, or a command that starts the "
        "same function as an entry point before it. An import binding of the function is "
        "permitted if it is the only module-level binding of the name, other than in an "
        "`except` clause. The Python adapter also writes it for a `__main__` module that "
        "imports that function and uses it. Coverage then counts the two entry points as "
        "one. An empty "
        "string tells that the adapter found no such entry point. Then this entry point "
        "must have a sequence. If the field is missing, the value is not known. Then the "
        "entry point also must have a sequence",
    ),
)

SCOPE_TITLES = {
    "facts": "The file",
    "module": "Each module, under `components`",
    "entry point": "Each entry point, under `entry_points`",
}


def fields_of(scope: str) -> set[str]:
    return {name for sc, name, _ in FIELDS if sc == scope}


def facts_doc() -> str:
    """Write the skill facts reference from `FIELDS`."""
    out = [
        "## The facts file",
        "",
        "`systemap extract` writes `docs/map/map.json` by default.",
        "These fields come from `systemap.facts_file.FIELDS`.",
    ]
    for scope, title in SCOPE_TITLES.items():
        out += ["", f"**{title}**", ""]
        out += [f"- `{name}`: {what}." for sc, name, what in FIELDS if sc == scope]
    out += [
        "",
        "**The extract summary**",
        "",
        "The numbers from `systemap extract` describe source facts.",
        "They do not describe the purposes of the map components.",
        "`modules` counts records under `components`.",
        "`functions`, `classes`, `types`, and `errors` give the sums of those module fields.",
        "`tests` gives the sum of `tests_total`. Thus the count has one item for each pair",
        "of a test function and a module that it imports. A test function that imports three",
        "modules counts three times. The count for test files with the module name gives the",
        "sum of `tests_primary`.",
        "",
        "`empty package markers` counts the records with `empty_marker` set to true.",
        "Coverage automatically excludes these records.",
    ]
    return "\n".join(out) + "\n"


def read_facts(path: Path, root: Path) -> dict[str, Any]:
    """Read stored facts. The root is the repository root.

    Give an empty table if the file is missing or the JSON parser cannot read it.
    A link out of the root (at the file or at a folder), a FIFO, and a device give
    `file_write.RefusedFile` with the cause. They do not give an empty table.
    """
    try:
        text = file_write.read_text(root, path)
        data = json.loads(text) if text is not None else {}
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(data) if isinstance(data, dict) else {}


def dumps(facts: dict[str, Any]) -> str:
    """Write compact facts with sorted keys and one module record per line.

    Indented output was 635 KB on a 144-module tree and exceeded a repository hook.
    Compact module records have no spaces. A diff can compare records by module.
    Top-level keys also use one line each.
    """

    def compact(value: Any) -> str:
        return json.dumps(value, separators=(",", ":"), sort_keys=True, ensure_ascii=False)

    parts: list[str] = []
    for key in sorted(facts):
        value = facts[key]
        if key == "components" and isinstance(value, dict):
            records = ",\n".join(
                f"{json.dumps(module)}:{compact(record)}"
                for module, record in sorted(value.items())
            )
            parts.append(f'"components":{{\n{records}\n}}')
        else:
            parts.append(f"{json.dumps(key)}:{compact(value)}")
    return "{\n" + ",\n".join(parts) + "\n}\n"


def write_facts(path: Path, facts: dict[str, Any], root: Path) -> None:
    """Write the facts. The folder must be in the root. A link at the path is replaced."""
    file_write.write_atomic(root, path, dumps(facts))


def summary(facts: dict[str, Any]) -> list[str]:
    """Give extraction counts with their source fields.

    These counts supply the change detector. The map does not show them.
    `modules` counts `components`. Functions, classes, types, and errors use their module
    fields. If a record has no `types`, the types count is not known. Test counts use
    `tests_total` and `tests_primary`: one for each pair of a test function and a module.
    Empty markers are package records without public names, imports, or execution.
    """
    comps = facts["components"]
    guarded = sum(c["tests_total"] for c in comps.values())
    primary = sum(c["tests_primary"] for c in comps.values())
    dirs: list[str] = list(facts.get("tests_dirs", []))
    if guarded:
        tests = (
            f"{guarded} pairs of a test function and a module that it imports, "
            f"{primary} in a test file with the module name"
        )
    elif dirs:
        # Zero is a finding, not a count: say where the extractor looked, so
        # a tests directory it did not find is set in `tests_dir`.
        tests = f"none import a module. The extractor searched {', '.join(dirs)}"
    else:
        tests = "none import a module. The extractor found no tests or test directory"
    # A record of an older facts format has no `types`. Its count is not known.
    types = (
        str(sum(len(c["types"]) for c in comps.values()))
        if all("types" in c for c in comps.values())
        else "unknown, because the facts file has an older format"
    )
    out = [
        "facts for the change detector (these never appear on the map):",
        f"  modules:          {len(comps)}",
        f"  functions:        {sum(len(c['functions']) for c in comps.values())}",
        f"  classes:          {sum(len(c['classes']) for c in comps.values())}",
        f"  types:            {types}",
        f"  errors:           {sum(len(c['errors']) for c in comps.values())}",
        f"  tests:            {tests}",
    ]
    markers = empty_markers(facts)
    if markers:
        out.append(
            f"  empty package markers: {len(markers)} ({', '.join(markers)}). Each only marks a "
            "package and holds no code. The coverage rule omits them."
        )
    return out
