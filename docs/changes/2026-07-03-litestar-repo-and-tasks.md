# 2026-07-03 — litestar repo added + 6 validated tasks

## What changed

- **New target repo `litestar`** (`REPO=litestar` in `harness/config.sh`),
  pinned @ `64aa84762` (2026-06-30), py3.12 out-of-tree venv. Pinned test
  stack = the repo's own `uv.lock` via `uv sync --locked --group dev --group
  test` targeted with `UV_PROJECT_ENVIRONMENT`. Same metadata-at-import quirk
  as dlt (`litestar/utils/version.py` reads `importlib.metadata`), covered by
  the existing per-run `install_editable`. Offline definition: `tests/unit`
  EXCEPT redis-parametrized cases (docker service fixtures) and
  `tests/unit/test_testing/test_sub_client/` (spawns a real uvicorn
  subprocess). Baseline: **4655 tests pass in ~60s** (8 xdist workers).
- **Six new validated tasks** (all gate1 FAIL / gate2 PASS / gate3 PASS,
  all `ty_status=working`, fixtures A–D built, prompts symptom-only):
  - `litestar-4866` — easy; response-cookie vs route-cookie precedence
    (`response/base.py` + 5 boilerplate siblings).
  - `litestar-4659` — easy-medium; Optional[UploadFile] 400 on empty file
    part (fix in `_kwargs/extractors.py`, decoy grep target `_multipart.py`).
  - `litestar-4815` — medium-light; msgspec Meta dropped on
    Optional[Annotated[...]] (`plugins/core/_msgspec.py`; OpenAPI symptom,
    plugin-file fix).
  - `litestar-4833` — medium; body declared only in dependency missing from
    OpenAPI requestBody (`_openapi/path_item.py` + `_kwargs/kwargs_model.py`).
  - `litestar-4806` — medium; Annotated metadata reclassifies
    dependency/path params as query params (`_kwargs/kwargs_model.py` +
    `typing.py`); 3 oracle tests block a partial fix.
  - `litestar-4687` — hard anchor; nullable-no-default fields missing from
    OpenAPI `required` (4 files: `typing.py` + dataclass/struct/attrs schema
    plugins); 3 oracle tests force the multi-file fix; `test_is_required`
    excluded as mechanism-coupled.
  Mining/screening ran as two subagent workflows (16 screeners + ranker, then
  5 builders); validity gates were run sequentially on the shared venv.
- **`launder.sh` ty pre-flight now passes `--python-version` = the venv
  interpreter's version.** Without it ty assumes the pyproject
  `requires-python` FLOOR (3.11 for litestar) and flags version-gated
  stdlib imports (`typing.TypeAliasType` behind try/except) as
  unresolved-import → false `ty_status=degraded` (hit litestar-4806/-4687).

## Files touched

`harness/config.sh` (litestar block + selector docs), `harness/launder.sh`
(`--python-version`), `holdout/litestar-{4866,4659,4815,4833,4806,4687}/*`,
`fixtures/litestar-*/{A,B,C,D}`, `repos/stage-litestar-*/`.

## What it invalidates

Nothing retroactively. Earlier dlt/feast `ty_status` labels were computed
without `--python-version`; none of them was version-gated (dlt's false
degradations were optional-module imports, already filtered), so labels are
unchanged — but recomputing them now could differ in principle.
