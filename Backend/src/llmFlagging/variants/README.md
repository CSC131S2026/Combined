# llmFlagging variants

Alternative conflict-matcher implementations kept for reference. The canonical
implementation wired into the GUI Pipeline tab and the build is
[`../higherSpec_openai.py`](../higherSpec_openai.py).

These files are **dormant**: nothing in `Frontend/`, the canonical matcher, or
the test suite imports them. They are not exercised by CI and have not been
updated alongside recent refactors (notably the `700Parse → form700_parse`
rename and the deeper path level introduced by moving them into this
subfolder), so their internal `importlib`/`_repo_root` bootstrap may need
patching before they will run again.

If you want to bring one back into rotation:

1. Update its `_repo_root` computation — it now sits one directory deeper than
   the original, so `pathlib.Path(__file__).parents[N]` needs N bumped by one.
2. Replace any remaining `src/700Parse/...` literals with `src/form700_parse/...`.
3. Wire it into `Frontend/core/pipeline_runner.py` (or expose a CLI entrypoint).
