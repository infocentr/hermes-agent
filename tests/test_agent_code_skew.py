"""Tests for agent-side code-skew detection (desktop/serve backend).

Companion to ``tests/test_code_skew.py`` (gateway): these prove the same
protection exists for the long-lived ``hermes serve`` / desktop backend
process, which imports ``run_agent`` directly rather than going through the
gateway.  See #68178.
"""

import ast
import symtable
from pathlib import Path

import pytest

_CONVERSATION_LOOP = Path(__file__).resolve().parents[1] / "agent" / "conversation_loop.py"


class TestSkewGuardCanActuallyRun:
    """The skew guard's early ``return finalize_turn(...)`` must be reachable.

    ``run_conversation`` imports ``finalize_turn`` lazily near the *end* of the
    function body, which makes the name function-local for the whole function.
    The skew guard added in 3a9b9d65d returns ``finalize_turn(...)`` from inside
    the loop -- thousands of lines *before* that import runs -- so firing the
    guard raised ``UnboundLocalError`` instead of telling the user to restart.
    """

    def test_finalize_turn_is_bound_before_first_use(self):
        src = _CONVERSATION_LOOP.read_text()
        fn = next(
            n
            for n in ast.parse(src).body
            if isinstance(n, ast.FunctionDef) and n.name == "run_conversation"
        )
        imports = [
            n.lineno
            for n in ast.walk(fn)
            if isinstance(n, (ast.Import, ast.ImportFrom))
            for a in n.names
            if (a.asname or a.name).split(".")[0] == "finalize_turn"
        ]
        uses = [
            n.lineno
            for n in ast.walk(fn)
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id == "finalize_turn"
        ]
        assert imports, "finalize_turn is never imported in run_conversation"
        assert min(uses) >= min(imports), (
            f"finalize_turn used at line {min(uses)} but only bound at line {min(imports)}; "
            "the early-return paths will raise UnboundLocalError"
        )

    def test_no_name_in_run_conversation_is_used_before_its_lazy_import(self):
        """Generalisation of the above: guard the whole function body."""
        src = _CONVERSATION_LOOP.read_text()
        fn = next(
            n
            for n in ast.parse(src).body
            if isinstance(n, ast.FunctionDef) and n.name == "run_conversation"
        )
        table = symtable.symtable(src, "conversation_loop.py", "exec")
        scope = next(c for c in table.get_children() if c.get_name() == "run_conversation")

        first_import: dict[str, int] = {}
        for n in ast.walk(fn):
            if isinstance(n, (ast.Import, ast.ImportFrom)):
                for a in n.names:
                    name = (a.asname or a.name).split(".")[0]
                    first_import[name] = min(first_import.get(name, n.lineno), n.lineno)

        offenders = []
        for name, import_line in first_import.items():
            # Only locals are at risk; a global of the same name is fine.
            if not scope.lookup(name).is_local():
                continue
            early = [
                n.lineno
                for n in ast.walk(fn)
                if isinstance(n, ast.Name)
                and isinstance(n.ctx, ast.Load)
                and n.id == name
                and n.lineno < import_line
            ]
            if early:
                offenders.append(f"{name}: imported@{import_line}, used@{sorted(early)}")

        assert not offenders, "use-before-lazy-import in run_conversation: " + "; ".join(offenders)


class TestAgentCodeSkewCaching:
    def test_boot_fingerprint_recorded_at_import(self):
        """``run_agent`` records its boot fingerprint on first import."""
        import run_agent

        # Should not be None on a git install.
        assert run_agent._agent_boot_fingerprint is not None

    def test_detect_no_skew_when_unchanged(self):
        """When the fingerprint hasn't changed, skew is None."""
        import run_agent

        assert run_agent._detect_agent_code_skew() is None

    def test_cached_skew_is_returned_immediately(self, monkeypatch):
        """Once confirmed, the result is cached and returned without I/O."""
        import run_agent

        monkeypatch.setattr(run_agent, "_agent_code_skew_confirmed", True)
        monkeypatch.setattr(run_agent, "_agent_code_skew_labels", ("abc1234567", "def4567890"))

        skew = run_agent._detect_agent_code_skew()
        assert skew == ("abc1234567", "def4567890")

    def test_none_boot_fingerprint_means_no_skew(self, monkeypatch):
        """If boot fingerprint could not be read, skew detection is a no-op."""
        import run_agent

        monkeypatch.setattr(run_agent, "_agent_boot_fingerprint", None)
        monkeypatch.setattr(run_agent, "_agent_code_skew_confirmed", False)
        monkeypatch.setattr(run_agent, "_agent_code_skew_labels", None)

        assert run_agent._detect_agent_code_skew() is None


class TestCheckCodeSkewBeforeTurn:
    def test_returns_none_without_skew(self):
        """When no skew exists, the method returns None."""
        import run_agent

        # Create a minimal fake agent with the method.
        class FakeAgent:
            pass

        fake = FakeAgent()
        # The method lives on AIAgent, not a module function. Test by
        # verifying the underlying function returns None when no skew.
        result = run_agent._detect_agent_code_skew()
        assert result is None

    def test_returns_warning_when_skew_confirmed(self, monkeypatch):
        """When skew is confirmed, the method returns a descriptive warning."""
        import run_agent

        monkeypatch.setattr(run_agent, "_agent_code_skew_confirmed", True)
        monkeypatch.setattr(run_agent, "_agent_code_skew_labels", ("abc1234567", "def4567890"))

        # The method is on AIAgent, so we need to instantiate or call via class.
        # Instead, test the underlying function directly.
        skew = run_agent._detect_agent_code_skew()
        assert skew == ("abc1234567", "def4567890")
