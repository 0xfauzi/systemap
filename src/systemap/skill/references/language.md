# ASD-STE100 language policy

All agents must use ASD-STE100 Issue 9 for all text that a person reads.
This is a requirement for new maps and map updates.
It is also a requirement for documentation and user interface text.

## Reference

ASD publishes the [official standard](https://www.asd-ste100.org/STE_downloads.html).
Use the writing rules in part 1 and the dictionary in part 2.
Do not substitute a general English dictionary or a summary of plain English.
Do not put a copy of the ASD dictionary in the repository.

Before you write, make sure that the official reference is available.
If it is not available, tell the maintainer that the reference is missing. Do not complete the language acceptance step.

## Text and names

Use ASD-STE100 for these fields and outputs:

- Component names, `does`, `plain`, and interface descriptions.
- Flow artifacts, relation sentences, and direction verbs.
- Container and region names and descriptions.
- Layer names, questions, and descriptions.
- Sequence names, labels, and step sentences.
- Invariants and the reasons for recorded decisions.
- New identifiers that are also names for the reader.
- Agent answers, command help, errors, explanations, and documentation.

Select short, literal names. Use one term for one concept.
For new names, use approved dictionary words or an applicable technical noun from the project glossary.
Keep a new multi-word noun to three words or fewer.
If a recorded technical noun has more words, use the full official name when necessary.
Do not use metaphors, slang, or new abbreviations to make a name shorter.

A sequence is the ordered set of steps that starts at an entry point.
The schema uses `Journey` and `journeys` for a sequence. Do not change these schema keys.
Use "sequence" in new prose. Use "entry point" for the place where a run starts.
Use "component" for the system part that a map card shows.

## Words and sentences

For each ordinary word, examine its dictionary entry.
Use only its approved meaning, part of speech, and word forms.
A word that is approved as a noun is not automatically approved as a verb.
For example, use "do a check" instead of the ordinary verb "check".

Use active voice and the permitted simple verb forms.
Use an imperative verb for an instruction.
Put a necessary condition before the instruction.
Use one instruction per sentence unless the actions occur at the same time.
Procedural sentences must not exceed 20 words.
Descriptive sentences must not exceed 25 words.
Use the word-count rules in section 8 of the standard.
Keep each paragraph to one topic and no more than six sentences.
Do not use contractions or semicolons in new prose.

If a word replacement changes the meaning, write a different sentence.
Do not remove uncertainty, evidence limits, source direction, or artifact identity.
Do not replace a specific computer process with a different process.

## Technical identities

Do not change these values:

- Commands, options, URLs, file paths, schema keys, and source symbols.
- Recorded component identifiers, sequence identifiers, and evidence state values.
- Quoted finding lines that a configuration uses as identifiers.
- Captured source text, external quotations, legal notices, and recorded experiment output.

These values are technical identities or quoted evidence.
This exception does not apply to new explanations or labels around them.
Do not rename a recorded identifier without a migration of every reference.
Do not rewrite recorded evidence as if the new words were the original result.

## Project glossary

The tables give project technical terms, not additions to the ASD dictionary.
Use a term only for its specified technical meaning.
Category 19 refers to computer science, information, and communication technology.
Category 7 refers to mathematical, scientific, and engineering terms.
Category 15 refers to documentation and standards.

### Technical nouns

These nouns belong to category 19 unless a different category is shown.
Plural forms and modifiers within an applicable technical noun are permitted.

| Term | Technical meaning |
|---|---|
| agent | A configured program that asks a model to do work. |
| API | An interface that a program supplies to other programs. |
| artifact | The named data or control item that a flow carries. |
| AST, syntax tree | The tree that a parser makes from source syntax. |
| baseline | The source revision used for a comparison. |
| branch | A Git reference to a sequence of commits. |
| cache | Stored results that a later call can use again. |
| card | The visual representation of one map component. |
| CI | Automated repository checks after a push or pull request. |
| CLI | The command-line interface of a program. |
| component | The system part that a map assigns to source modules or symbols. |
| configuration | The settings that control a program. |
| contrast ratio | The measured relation between two color luminances (category 7). |
| control flow | A flow that causes a component to do an action. |
| data flow | A flow that carries data between components. |
| digest | A hash value of recorded source or claim contents. |
| docstring | A string in source code that documents a module or symbol. |
| entry point | A command, route, or public symbol where a run can start. |
| evidence state | The recorded classification of support for a flow claim. |
| export, re-export | A public source symbol, including one supplied through another module. |
| fixture | Recorded test input or a small source project used by a test. |
| flow | A directed relation with one artifact and two component endpoints. |
| flow path | The calculated line between two component endpoints in a map. |
| function | A named executable unit in source code. |
| Git commit | A recorded revision in a Git repository. |
| heuristic | A specified procedure that gives an approximate result (category 7). |
| import | A source reference to another module or public symbol. |
| inspector | The user interface panel for a selected component or flow. |
| interface | The specified input and output of a program or component. |
| invariant | A source-supported rule that applies to specified components. |
| journey | The existing schema and command term for a sequence. |
| JSON, JSONC | Data formats for structured records and configuration. |
| layer | A map view that shows a specified set of components and flows. |
| map | The authored model and its visual representation of a system. |
| metadata | Data about a source record, output, or interface item. |
| model | The structured map description, or a named machine-learning system. |
| model SDK | A software package used to call a model. |
| module | A source unit identified by its import name. |
| package | A set of modules supplied under one import name or distribution. |
| palette | The specified set of colors in a user interface. |
| parser | The program that reads syntax and makes source records. |
| precision | The fraction of positive results that are correct (category 7). |
| probability | A mathematical value for an event or decision (category 7). |
| provenance | Recorded information about the origin of a source fact or output. |
| public surface | The exports and entry points available to other code. |
| pull request | A request to merge a branch into a repository branch. |
| Python, TypeScript | The source languages that systemap reads. |
| recall | The fraction of applicable items that a method finds (category 7). |
| repository | The source files and version history of a project. |
| revision | An identified version of source files or map output. |
| schema | The specified fields and types of a data format. |
| SDK | A software development kit with program interfaces. |
| snapshot | The saved map and source facts for one extraction. |
| source claim | An authored statement about what source code does. |
| source code | The program text that an extractor or maintainer reads. |
| source record | The module, symbol, path, and digest cited for a claim. |
| source review | A recorded examination of source support for a claim. |
| SVG | The vector image format used for map figures. |
| symbol | A named function, class, or object in source code. |
| threshold | The specified acceptance value for a measurement (category 7). |
| token | A unit of model input or output, or a parser symbol. |
| TSX | TypeScript syntax that includes JSX elements. |
| viewport | The visible area in which the browser shows a map. |

| actor | A map component outside the system source boundary. |
| alias | An alternative source name for an import or public symbol. |
| AUC | The area under a measured threshold curve (category 7). |
| barycenter | The weighted mean position used by the layout procedure (category 7). |
| benchmark | A recorded comparison of program or model results under specified conditions (category 7). |
| camera | The transform that positions and scales the map within its viewport. |
| claim | An authored statement about source behavior or a map relationship. |
| CLI output | Text that a command writes for a person or another program. |
| compiler | A program that translates or analyses source code. |
| container | A map boundary for a process, host, or source directory. |
| contrast probe | A procedure that calculates contrast ratios for specified colors (category 7). |
| CSS token | A named theme value used by style rules. |
| diagnostic | A finding from a source, map, or consistency check. |
| diagnostic kind | The stable prefix that classifies a finding. |
| DOM | The browser representation of a page and its elements. |
| exact answer | A recorded configuration answer for one complete finding line. |
| exception | A software error object or type. |
| false alarm | A positive result for an item outside the target class (category 7). |
| family selector | A pattern that identifies a specified family of findings. |
| fingerprint | A deterministic identity for source or claim contents. |
| framing | The camera operation that fits selected map bounds within the viewport. |
| Git ancestor | A commit reachable through the parent history of another commit. |
| Git blob | The Git object that stores file contents. |
| Git ref | A named Git reference to an object or commit. |
| gutter | The layout space between regions or card columns. |
| holdout | Recorded evaluation cases excluded from fitting a method (category 7). |
| import connection | An extracted source import between two component module sets. |
| layout geometry | The coordinates and bounds used by the map layout (category 7). |
| legend | The diagram explanation for its colors and marks. |
| keyboard focus | The user interface control that receives keyboard input. |
| label | The text that identifies a user interface control or a map flow. |
| list | A user interface group with one selection control for each record. |
| pointer | The screen position that receives mouse or touch input. |
| preview | A temporary map view that shows a flow before selection. |
| measurement | A quantitative value with specified units and conditions (category 7). |
| module match | A paired source module record in a revision comparison. |
| newline | The character or character sequence that ends a text line. |
| owner, ownership | The component assignment of a source module. |
| plan projection | A computed component selection from a stated change plan. |
| port | A map flow endpoint position on a component boundary. |
| probability weight | A probability value used by the component selection procedure (category 7). |
| public name | A module-level source symbol available to other code. |
| recorded answer reason | The configuration explanation for a recorded finding answer. |
| region | A component group and its map layout bounds. |
| regression test | A test of behavior that a later source change must keep. |
| router | The procedure that calculates flow paths around map bounds. |
| routing score | The numerical comparison of candidate flow paths (category 7). |
| scheme | A specified set of user interface theme values. |
| semantic ownership | The component assignment based on the source purpose and boundary. |
| slot | A candidate card position in the layout grid. |
| source boundary | The module or symbol set that a component represents. |
| source extraction | The process that reads source files and makes source facts. |
| source hash | The digest of complete source file contents. |
| syntax hash | The digest of normalized source syntax. |
| test suite | The repository tests executed as one set. |
| text encoding | The specified mapping between text characters and stored bytes. |
| theme | The style values that control the page appearance. |
| Clay | The named theme with a terracotta accent and dark surfaces (category 17). |
| terracotta | The brown-orange color from 0xfauzi.com used in the Clay theme (category 17). |
| device theme | The Light or Dark theme that the browser reads from the computer. |
| isometric projection, projection | The diagram transform with two axes at equal angles to the horizontal (category 7). |
| plate | The rounded surface that represents a component in the map with an isometric projection. |
| sequence role | The acting or measurement classification of a component in a sequence step (category 19). |
| acting component | A component in the `acts` field of a sequence step (category 19). |
| measurement component | A component in the `measures` field of a sequence step (category 19). |
| application | A computer program with a user interface (category 19). |
| reduced motion | The browser or page preference that stops interface animation (category 19). |
| source evidence | Source records and review data that support a map claim (category 19). |
| stroke pattern | The SVG line marks that show a map evidence state (category 19). |
| caption | The horizontal component name in a plate. |
| threshold curve | The measured results across specified threshold values (category 7). |
| exact match | A full identity comparison with no wildcard or substring matching. |
| source pattern | A module name or wildcard expression used for component assignment. |
| wildcard | A pattern symbol that matches a specified set of names. |

| Term | Technical meaning |
|---|---|
| advance | The font distance between the origin of a glyph and the origin of the next glyph. |
| animation | A display that shows a group of images one after the other. |
| appearance | The colors, fonts, and shapes that a user interface shows. |
| ASCII | The character code standard used for the measured characters in the font table. |
| assertion | A software test statement that gives an error if a specified condition is not correct. |
| assignment | The recorded component for a source module. |
| bearing | The signed distance in a font between a glyph outline and its origin or advance limit. |
| border | The line that shows the limits of a card or page item. |
| bounds | The coordinate limits that contain a glyph, text line, or diagram item (category 7). |
| canvas | The page area that contains the map and its controls. |
| character | One text item, such as a letter or symbol. |
| CI job | A named set of commands that a CI configuration executes together. |
| clipping | The renderer operation that shows only the image parts in specified bounds. |
| cognitive complexity | The number that complexipy calculates for a function to compare the structure of its source code (category 7). |
| coordinate | A number that gives a position in a geometric system (category 7). |
| coordinate precision | The smallest difference between two different permitted coordinate values (category 7). |
| desktop | A computer with a keyboard and a screen used for the larger browser measurements. |
| design | The specified structure and appearance of a user interface. |
| font | A named set of glyphs and their dimensions for text. |
| font metrics | The recorded dimensions that a font supplies for glyph positions and text width. |
| font size | The font dimension in CSS pixels that controls the scale of its glyphs. |
| font unit | A unit in the coordinate system of a font (category 9). |
| frame | One image in a video or animation. |
| glyph | A shape that a font supplies for a character or a group of characters. |
| image | A digital figure that software keeps or shows. |
| infinity | The mathematical value that is more than all finite numbers (category 7). |
| keyboard | The input device that supplies keys for text entry and user interface control. |
| kerning | A font adjustment to the distance between specified glyph pairs. |
| ligature | One glyph that a font uses for two or more characters. |
| margin | The specified space between glyph outlines and card bounds. |
| multiple | The result of a specified number multiplied by an integer (category 7). |
| normalization | The procedure that changes equivalent software data into one specified representation. |
| offset | The coordinate difference between a text origin and its specified position (category 7). |
| origin | The specified reference position for a glyph or text line. |
| outline | The contour that gives the shape of a glyph. |
| overhang | A glyph shape extension that is not between its origin and its advance limit. |
| overflow | The condition in which specified bounds do not contain all text or page contents. |
| padding | The specified distance between a page item and its contents. |
| phone | The computer device used for the smaller browser measurements. |
| pixel | A unit for image or browser dimensions (category 9). |
| placement | The procedure that gives card positions to a map. |
| renderer | The software that makes a page or figure from a model and source facts. |
| requirement | A condition that gives a necessary result (category 15). |
| rounding | The procedure that changes a number to a permitted value under a specified rule (category 7). |
| screen | The computer device that shows the user interface. |
| screen reader | A software tool that gives users access to user interface contents through voice output. |
| screenshot | A recorded image of a page or screen at a specified time. |
| separator | A character that divides a description into words. |
| space character | A character that gives separation between words. |
| speech | The voice output that a screen reader supplies. |
| static design check | A software check that compares the source code of a user interface with its design requirements. |
| style | The software values that control text and image appearance. |
| subset | A group that includes only items from a specified group (category 7). |
| tour | The recorded map animation that shows its controls and views. |
| type hierarchy | The specified differences in font dimensions and style between user interface text groups. |
| Unicode | The character code standard that gives codes for text from different languages. |
| user comprehension | A test result that measures if the user knows the component and flow information in a map (category 7). |
| visibility | The condition in which the viewport shows a map item. |

Documentation terms such as language policy, sentence, paragraph, glossary,
description, heading, reference, text, dictionary, and writing rule belong to category 15.
The reader and maintainer are documentation roles in category 11.
They refer only to the contents and structure of documentation.

### Technical verbs

These verbs belong to the computer-process category in rule 1.12.
Use them only for the specified computer operation.
If approved dictionary words give the same meaning, use those words instead.

| Verb | Computer operation |
|---|---|
| cache | Keep an answer under a key for a later identical request. |
| call | Invoke a software function or API. |
| compile | Translate source code into another executable representation. |
| configure | Set software configuration values. |
| define | Declare a source symbol with its specified name and contents. |
| execute, run | Start a command, program, or specified computer procedure. |
| export, re-export | Supply a public symbol through a module interface. |
| extract | Read source files and make structured source facts. |
| hash | Calculate a cryptographic identity for specified data. |
| import | Load or reference a module or public symbol. |
| load | Read stored software data into a program. |
| normalize | Convert equivalent data representations to one specified form. |
| parse | Read source syntax into structured records. |
| render | Make a page or figure from a model and source facts. |
| resolve | Identify the source target of a module, symbol, or path reference. |
| restore | Replace software data or files with a saved copy. |
| serialize | Convert a structured value into its stored representation. |
| update | Change stored software data or interface contents. |
| type | Enter text into a computer input field. |
| validate | Do the specified schema or consistency checks on software data. |

| format | Convert software records into specified display text. |
| group | Give software records a group through a specified algorithm. |
| index | Associate software records with lookup keys. |
| pair | Associate source records as candidates in a revision comparison. |
| route | Calculate a map flow path around layout bounds. |
| return | Supply the result of a software function to its caller. |

Do not use these verbs for general human actions.
Use "examine the source" for a human source review.
Use "compare the revisions" only if the dictionary meaning of "compare" applies.

## Acceptance procedure

Before you complete a map or documentation update:

1. Read every new or changed name and sentence.
2. Examine the applicable dictionary entries and their meanings.
3. Examine each technical term against the glossary and the standard categories.
4. Make sure that sentences, verb forms, punctuation, and word counts obey the standard.
5. Compare each claim with its source. Keep the meaning and evidence limits.
6. Do the repository checks. Record any language uncertainty for the maintainer.

If a necessary technical term is missing, add its meaning and category before use.
Do not add an ordinary word to the glossary to avoid its dictionary rule.
An automated word list cannot show correct meanings, parts of speech, or source claims.
Do not use an automated check as the only evidence of language compliance.
