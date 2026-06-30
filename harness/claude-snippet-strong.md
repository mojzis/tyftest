### MANDATORY: use `tyf` for every Python symbol lookup

This project ships **`tyf`**, a type-aware navigation tool backed by a real LSP
(ty). For ANY question about a Python symbol — where it is defined, its
signature, who calls it, what a class exposes, or what a file contains — `tyf`
is the correct and required tool. **Use it before Grep, ripgrep, or opening a
file to search.** Reaching for grep/Read to locate or inspect a Python symbol
when `tyf` is available is a mistake: grep matches raw text (comments, strings,
unrelated names) and then forces you to read files to confirm, while `tyf`
resolves the actual symbol through the type system and returns the precise
definition, signature, and every real reference in a single call — faster, more
accurate, and far cheaper in tokens.

**Do this before editing anything:**

- Locate a symbol → `tyf find Name` — do **not** grep for `def Name` / `class Name`.
- Understand a function/method → `tyf show name` (signature; add `-d` docs,
  `-r` refs, `-t` test refs, or `--all`) instead of opening the file to read it.
- Before you change, rename, or delete a symbol → `tyf refs name` to see every
  call site. Grep will miss dynamic uses and over-match unrelated text; `tyf`
  gives the real reference set, so you won't break callers.
- A class's public API → `tyf members ClassName`.
- A file's outline → `tyf list path/to/file.py`.

Every command accepts multiple symbols — **batch them in one call** to save round
trips. Run `tyf <cmd> --help` for options.

Only fall back to Grep for genuinely non-symbol text: string literals, config
keys, TODOs, log messages, and non-Python files.
