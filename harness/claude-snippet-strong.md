### `tyf` — Python symbol lookup

`tyf` resolves Python symbols through the type system (ty LSP). One call
returns the exact definition, signature, and every real reference — the
answer, not text matches you still have to open files to verify. For symbol
questions it's faster, more accurate, and cheaper in tokens than grep.

Catch yourself before running `grep "def X"` / `grep "class X"` or opening a
file to find a symbol — that's a `tyf` call:

- `tyf find Name` — definition location
- `tyf show name` — signature (`-d` docs, `-r` refs, `-t` test refs, `--all`)
- `tyf refs name` — every call site; check before changing, renaming, or
  deleting anything, so you don't break callers grep can't see
- `tyf members Class` — public API
- `tyf list file.py` — file outline

Every command takes multiple symbols — batch them in one call.

grep is for non-symbols: string literals, config keys, log messages,
non-Python files.
