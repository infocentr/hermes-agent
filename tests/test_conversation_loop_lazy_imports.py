"""Guard against use-before-lazy-import inside ``run_conversation``.

``agent.conversation_loop.run_conversation`` is a several-thousand-line
function that imports some collaborators lazily (module-level would be
circular). A function-local import binds the name for the *whole* function
body, so any code path that references such a name *before* the import
statement runs raises ``UnboundLocalError``.

That is not hypothetical: the code-skew guard in 3a9b9d65d added an early
``return finalize_turn(...)`` inside the iteration loop while
``finalize_turn`` was imported ~5,100 lines further down. Every message to a
skewed gateway crashed the turn, and the guard could never fire. Upstream
resolved it by reverting the guard; this test makes the underlying trap
detectable if a similar early-return path is added again.
"""

import ast
import symtable
from pathlib import Path

_CONVERSATION_LOOP = Path(__file__).resolve().parents[1] / "agent" / "conversation_loop.py"


def _run_conversation_ast() -> ast.FunctionDef:
    src = _CONVERSATION_LOOP.read_text()
    return next(
        n
        for n in ast.parse(src).body
        if isinstance(n, ast.FunctionDef) and n.name == "run_conversation"
    )


class TestNoUseBeforeLazyImport:
    def test_run_conversation_has_no_use_before_lazy_import(self):
        src = _CONVERSATION_LOOP.read_text()
        fn = _run_conversation_ast()
        scope = next(
            c
            for c in symtable.symtable(src, "conversation_loop.py", "exec").get_children()
            if c.get_name() == "run_conversation"
        )

        first_import: dict[str, int] = {}
        for node in ast.walk(fn):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    name = (alias.asname or alias.name).split(".")[0]
                    first_import[name] = min(first_import.get(name, node.lineno), node.lineno)

        offenders = []
        for name, import_line in first_import.items():
            # Only function-locals are at risk; a same-named global is fine.
            if not scope.lookup(name).is_local():
                continue
            early = sorted(
                node.lineno
                for node in ast.walk(fn)
                if isinstance(node, ast.Name)
                and isinstance(node.ctx, ast.Load)
                and node.id == name
                and node.lineno < import_line
            )
            if early:
                offenders.append(f"{name}: imported@{import_line}, used@{early}")

        assert not offenders, (
            "name(s) used before their function-local import in run_conversation "
            "(these paths raise UnboundLocalError at runtime): " + "; ".join(offenders)
        )
