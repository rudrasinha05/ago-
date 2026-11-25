"""MGR-002: the Workforce Manager chooses a model per piece of work, by rules."""
from ago.model_manager import ModelManager, strength


def c(label, s, free=True):
    provider = label.split(":")[0]
    return {"label": label, "provider": provider, "strength": s, "free": free}


LOCAL = c("ollama:qwen3:4b", 1)
GROQ = c("groq:openai/gpt-oss-120b", 2)
CLAUDE = c("anthropic:claude-sonnet-4-6", 3, free=False)
OPENAI = c("openai:gpt-5", 3, free=False)


def pick(work, cands, results=None, failed=False, paid_ok=True, avoid=None):
    return ModelManager._pick(work, cands, results or {}, failed, paid_ok, avoid, None)


def test_strength_scale():
    assert strength("ollama", "qwen3:4b") == 1 and strength("ollama", "qwen2.5-coder:14b") == 2
    assert strength("anthropic", "claude-haiku-4-5") == 2 and strength("anthropic", "claude-sonnet-4-6") == 3
    assert strength("groq", "openai/gpt-oss-120b") == 2 and strength("groq", "llama-3.1-8b-instant") == 1
    assert strength("gemini", "gemini-2.5-flash") == 3 and strength("gemini", "gemini-2.5-flash-lite") == 2


def test_code_never_goes_to_a_small_local_model_when_a_capable_one_exists():
    assert pick("code", [LOCAL, GROQ, CLAUDE])["label"] == GROQ["label"]       # free and capable first
    assert pick("code", [LOCAL, CLAUDE])["label"] == CLAUDE["label"]           # Ollama 4B cannot write code
    assert "no free model is strong enough" in pick("code", [LOCAL, CLAUDE])["reason"]


def test_rework_and_weak_history_move_code_to_the_strongest_model():
    assert pick("code", [LOCAL, GROQ, CLAUDE], failed=True)["label"] == CLAUDE["label"]
    weak = {GROQ["label"]: {"passed": 1, "failed": 3}}
    chosen = pick("code", [LOCAL, GROQ, CLAUDE], results=weak)
    assert chosen["label"] == CLAUDE["label"] and "keeps failing QA" in chosen["reason"]


def test_paid_models_are_skipped_when_the_founder_does_not_allow_them():
    assert pick("code", [LOCAL, GROQ, CLAUDE], failed=True, paid_ok=False)["label"] == GROQ["label"]
    assert pick("code", [LOCAL, CLAUDE], paid_ok=False)["label"] == LOCAL["label"]   # nothing else allowed


def test_qa_prefers_a_different_provider_and_short_work_stays_free():
    assert pick("qa", [GROQ, CLAUDE, OPENAI], avoid="groq")["provider"] != "groq"
    assert pick("qa", [LOCAL, GROQ, CLAUDE])["label"] == GROQ["label"]
    for work in ("plan", "board", "chat"):
        chosen = pick(work, [LOCAL, GROQ, CLAUDE])
        assert chosen["free"] and "(free)" in chosen["reason"]


def test_choose_records_every_decision_and_returns_none_without_models(monkeypatch):
    recorded = []

    class Store:
        class connection:
            @staticmethod
            def transaction():
                import contextlib
                return contextlib.nullcontext()

        def builder_results(self, tenant):
            return {}

        def stage_failed_before(self, *a):
            return False

        def record(self, *row):
            recorded.append(row)

    class Repos:
        def resolve(self, port):
            return Store()

    monkeypatch.setenv("AGO_LLM_PROVIDER", "ollama_local")
    monkeypatch.setenv("AGO_ENABLE_LOCAL_MODELS", "true")
    monkeypatch.setenv("AGO_LLM_MODEL", "qwen3:4b")
    monkeypatch.setattr("ago.model_manager.cloud_models_available", lambda: False)
    m = ModelManager(None, repositories=Repos())
    chosen = m.choose(tenant_id="t", work="chat", task_id=None, role="ceo")
    assert chosen.label == "ollama:qwen3:4b" and chosen.cloud is None
    assert recorded == [("t", None, "chat", "ceo", "ollama:qwen3:4b", chosen.reason)]
    monkeypatch.setenv("AGO_ENABLE_LOCAL_MODELS", "false")
    assert m.choose(tenant_id="t", work="chat") is None


GEMINI = c("gemini:gemini-3.6-flash", 3)


def test_short_work_prefers_the_fastest_capable_free_model_and_keeps_a_backup():
    """Live run 2026-11-25: Gemini answered Board work slowly and was cut off;
    the local fallback then timed out. Short work now goes to the fastest capable
    free model, with a second free cloud model before the local one."""
    assert pick("board", [LOCAL, GEMINI, GROQ])["label"] == GROQ["label"]
    assert pick("plan", [LOCAL, GEMINI, GROQ])["label"] == GROQ["label"]
    # Code still wants the strongest free model.
    assert pick("code", [LOCAL, GEMINI, GROQ])["label"] == GEMINI["label"]
    assert ModelManager._backup("code", [LOCAL, GEMINI, GROQ], GEMINI)["label"] == GROQ["label"]
    assert ModelManager._backup("board", [LOCAL, GEMINI, GROQ], GROQ)["label"] == GEMINI["label"]
    # Never a paid backup, never the same provider, nothing behind the local model.
    assert ModelManager._backup("board", [LOCAL, GROQ, CLAUDE], GROQ) is None
    assert ModelManager._backup("board", [LOCAL, GROQ], LOCAL) is None


def test_a_failed_first_model_is_answered_by_the_backup_before_the_local_model():
    from ago.model_provider import CloudProviderError, FallbackProvider

    class Cut:
        label = "gemini:gemini-3.6-flash"

        def generate(self, prompt, **o):
            raise CloudProviderError("incomplete_answer")

    class Fast:
        label = "groq:openai/gpt-oss-120b"

        def generate(self, prompt, **o):
            return "BOARD_RECOMMENDATION: APPROVE"

    class Local:
        label = "ollama:qwen3:4b"

        def generate(self, prompt, **o):
            raise AssertionError("the local model must not be asked")

    chain = FallbackProvider(Cut(), FallbackProvider(Fast(), Local(), fallback_label="ollama:qwen3:4b"),
                             fallback_label="ollama:qwen3:4b")
    assert chain.generate("vote") == "BOARD_RECOMMENDATION: APPROVE"
    assert chain.label == "groq:openai/gpt-oss-120b" and chain.cloud_failures == ["incomplete_answer"]
