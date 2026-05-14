from secretzero.agent_context import env_sz_agent_mode, spill_guard_active


def test_env_sz_agent_mode_false(monkeypatch) -> None:
    monkeypatch.delenv("SZ_AGENT_MODE", raising=False)
    assert env_sz_agent_mode() is False


def test_env_sz_agent_mode_true(monkeypatch) -> None:
    monkeypatch.setenv("SZ_AGENT_MODE", "true")
    assert env_sz_agent_mode() is True


def test_spill_guard_union(monkeypatch) -> None:
    monkeypatch.delenv("SZ_AGENT", raising=False)
    monkeypatch.delenv("SZ_AGENT_MODE", raising=False)
    assert spill_guard_active() is False
    monkeypatch.setenv("SZ_AGENT_MODE", "1")
    assert spill_guard_active() is True
