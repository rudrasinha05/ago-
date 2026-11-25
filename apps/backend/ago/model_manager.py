"""Workforce Manager: which AI model does each piece of work (MGR-002).

Rules, not guesses, so every choice can be explained and repeated:

* Every model has a strength: 3 strong (Claude Sonnet/Opus, OpenAI sol/astra,
  Gemini pro/flash), 2 capable (Groq gpt-oss-120b / 70B, Claude Haiku, lighter
  OpenAI and Gemini models, local models of 14B+), 1 light (small local models).
* Every kind of work has a need: code and learning need at least 2; QA needs 2
  and, when possible, a different provider than the one that wrote the work;
  plans, Board votes and chat can run on light models.
* Free first (Groq, Gemini, local Ollama). Paid models (Claude, OpenAI) only
  when the Founder allows them, within the monthly paid-call limit, and when
  the work needs it: no free model is strong enough, the free model's work keeps
  failing QA, or this project stage already failed QA once (the rework gets the
  strongest model).
* Every choice is recorded with its reason. The Founder Assistant is never
  chosen or changed here.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass

from ago.backend_contracts import DatabaseConnection, RepositoryScope
from ago.model_manager_store import ModelManagerStore
from ago.model_provider import PAID_PROVIDERS, ProviderVault, cloud_models_available

WORKS = ("code", "qa", "plan", "board", "chat", "learn")
# (minimum strength, wanted strength) per kind of work.
NEEDS = {"code": (2, 3), "learn": (2, 3), "qa": (2, 2), "plan": (1, 2), "board": (1, 2), "chat": (1, 2)}
# Longest answer each kind of work needs from a cloud model (tokens). AGO stores
# a bounded excerpt of Board, plan and chat answers, so a long answer there only
# adds time; code and skills need room for whole files.
OUTPUT_TOKENS = {"code": 4096, "learn": 2048, "qa": 1200, "plan": 1500, "board": 1200, "chat": 800}
WORK_NAMES = {"code": "Code writing", "learn": "Writing a skill", "qa": "QA review",
              "plan": "Planning", "board": "Board review", "chat": "Board chat"}


def strength(provider: str, model: str) -> int:
    m = model.lower()
    if provider == "ollama":
        size = re.search(r"(\d+(?:\.\d+)?)b\b", m)
        return 2 if size and float(size.group(1)) >= 14 else 1
    if provider == "anthropic":
        return 2 if "haiku" in m else 3
    if provider == "openai":
        if re.search(r"(nano|mini|luna)", m):
            return 2
        return 3 if re.search(r"(sol|astra|gpt-5|gpt-6|o3|gpt-4\.1$)", m) else 2
    if provider == "gemini":
        if "lite" in m or "gemma" in m:
            return 2
        return 3 if re.search(r"(pro|flash|argon|carbon|neon)", m) else 2
    if provider == "groq":
        if re.search(r"(120b|70b|32b|qwen3|kimi|deepseek)", m):
            return 2
        return 1
    return 1


@dataclass(frozen=True)
class Choice:
    label: str           # "groq:openai/gpt-oss-120b" or "ollama:qwen3:4b"
    cloud: object | None  # metered cloud provider, or None = use the local model
    reason: str


def _local_label() -> str | None:
    if (os.getenv("AGO_LLM_PROVIDER") == "ollama_local"
            and os.getenv("AGO_ENABLE_LOCAL_MODELS") == "true"):
        return "ollama:" + (os.getenv("AGO_LLM_MODEL") or "qwen2.5:3b")
    return None


class ModelManager:
    """Chooses a model per piece of work and records why."""

    def __init__(self, connection: DatabaseConnection, *,
                 repositories: RepositoryScope | None = None):
        self.connection = connection
        self.repositories = repositories or RepositoryScope(connection)

    def choose(self, *, tenant_id: str, work: str, task_id: str | None = None,
               role: str | None = None, project_id: str | None = None,
               stage: str | None = None, avoid_provider: str | None = None) -> Choice | None:
        """The model for this work, or None when no model at all is available."""
        if work not in WORKS:
            raise ValueError("Unknown kind of work")
        vault = ProviderVault()
        policy = vault.policy(tenant_id) if cloud_models_available() else None
        candidates = []
        local = _local_label()
        if local:
            name, _, model = local.partition(":")
            candidates.append({"label": local, "provider": "ollama", "strength": strength("ollama", model),
                               "free": True})
        for entry in (policy or {}).get("models", []):
            candidates.append({"label": entry["provider"] + ":" + entry["model"],
                               "provider": entry["provider"],
                               "strength": strength(entry["provider"], entry["model"]),
                               "free": entry["provider"] not in PAID_PROVIDERS})
        if not candidates:
            return None
        store = self._store()
        results = self._safe(lambda: store.builder_results(tenant_id), {}) if work in ("code", "learn") else {}
        failed_before = bool(work == "code" and project_id and stage and self._safe(
            lambda: store.stage_failed_before(tenant_id, project_id, stage), False))
        paid_ok = bool(policy and policy["allow_paid"] and not policy["paid_cap_reached"])
        choice = self._pick(work, candidates, results, failed_before, paid_ok, avoid_provider, policy)
        cloud = None
        if choice["provider"] != "ollama":
            cloud = vault.metered(tenant_id, choice["provider"], max_output_tokens=OUTPUT_TOKENS[work])
        decided = Choice(label=choice["label"], cloud=cloud, reason=choice["reason"])
        self._safe(lambda: self._record(store, tenant_id, task_id, work, role, decided), None)
        return decided

    @staticmethod
    def _pick(work, candidates, results, failed_before, paid_ok, avoid_provider, policy) -> dict:
        least, wanted = NEEDS[work]
        name = WORK_NAMES[work]

        def proven_weak(c):
            r = results.get(c["label"]) or {}
            total = r.get("passed", 0) + r.get("failed", 0)
            return total >= 3 and r.get("passed", 0) / total < 0.5

        pool = [c for c in candidates if c["free"] or paid_ok]
        able = [c for c in pool if c["strength"] >= least] or pool or candidates

        def order(c):
            different = 0 if avoid_provider and c["provider"] != avoid_provider else 1
            return (different, -c["strength"] if c["strength"] < wanted else -wanted,
                    0 if c["free"] else 1, c["label"])

        if work in ("code", "learn"):
            strongest = max(c["strength"] for c in able)
            if failed_before:
                best = sorted((c for c in able if c["strength"] == strongest),
                              key=lambda c: (0 if c["free"] else 1, c["label"]))[0]
                return {**best, "reason": name + ": this stage already failed QA once, so the rework "
                        "gets the strongest model AGO has (" + best["label"] + ")."}
            free_good = [c for c in able if c["free"] and c["strength"] >= least and not proven_weak(c)]
            if free_good:
                best = sorted(free_good, key=lambda c: (-c["strength"], c["label"]))[0]
                return {**best, "reason": name + ": a free model strong enough for code ("
                        + best["label"] + ") goes first; a stronger paid model is kept for a rework."}
            best = sorted(able, key=lambda c: (-c["strength"], 0 if c["free"] else 1, c["label"]))[0]
            why = ("the free models' work keeps failing QA" if any(proven_weak(c) for c in able if c["free"])
                   else "no free model is strong enough")
            return {**best, "reason": name + ": " + why + ", so AGO uses " + best["label"] + "."}
        if work == "qa":
            best = sorted(able, key=order)[0]
            other = " from a different provider than the builder" if avoid_provider and best["provider"] != avoid_provider else ""
            return {**best, "reason": name + ": a capable model" + other + " checks the work ("
                    + best["label"] + ")" + ("" if best["free"] else "; no free model was capable enough") + "."}
        # Plans, Board votes and chat: short work, never worth a paid call when a
        # free model can do it.
        free = [c for c in able if c["free"]] or able
        best = sorted(free, key=order)[0]
        return {**best, "reason": name + " is short work: " + best["label"]
                + (" (free)" if best["free"] else " (no free model available)") + "."}

    def _store(self) -> ModelManagerStore:
        return self.repositories.resolve(ModelManagerStore)

    @staticmethod
    def _safe(work, default):
        """Records and statistics never stop the work they describe."""
        try:
            return work()
        except Exception:  # noqa: BLE001 - optional evidence by design
            return default

    def _record(self, store, tenant_id, task_id, work, role, decided) -> None:
        with store.connection.transaction():
            store.record(tenant_id, task_id, work, role, decided.label, decided.reason)

    def recent(self, tenant_id: str) -> list[dict]:
        return [{**d, "id": str(d["id"]), "task_id": str(d["task_id"]) if d["task_id"] else None,
                 "created_at": d["created_at"].isoformat()}
                for d in self._store().recent(tenant_id)]
