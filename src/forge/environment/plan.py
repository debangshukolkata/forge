"""The model plan (D-186): which model serves each role, proposed from what actually answered,
confirmed by the user, then applied to the router at every session start. Model names come from
config.yaml only (D-014)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from forge.config import ROLES, ForgeConfig
from forge.environment import store


class RoleRouter(Protocol):
    config: ForgeConfig

    def set_role_model(self, role: str, model_key: str) -> None: ...


# The proposed model for a role is the first of these that has answered its test (D-405, D-407, D-409, D-411); a role without an entry keeps its configured default. The roles follow the research
# and the user's decisions of 2026-10-15: the coder is gpt-5.4 (ahead of gpt-5.1 on coding and agent benchmarks, larger context, trained for long agent runs) when its resource is set up; the planner, the
# critic, the judge and the reviewer are another family than the builder (Gemini 4 Argon, else Gemini 3.1 Pro), because a judge from the builder's own family is lenient toward it; the fallback is another
# family too (a rate limit usually hits one provider), else gpt-5.1 from the first resource. The summariser, the knowledge builder and vision keep gpt-5.1: high-volume reading work where speed counts.
PREFERENCE: dict[str, tuple[str, ...]] = {
    "coder": ("gpt54",),
    "planner": ("gemini4argon", "gemini31pro"),
    "critic": ("gemini4argon", "gemini31pro", "gpt52"),
    "judge": ("gemini4argon", "gemini31pro", "gpt52"),
    "reviewer": ("gemini4argon", "gemini31pro", "gpt52"),
    "fallback": ("gemini31pro", "gpt51"),
}


def _answers(config: ForgeConfig, results: dict[str, Any]) -> dict[str, bool] | None:
    """Which models answered, from the Azure test and the Gemini test; None before any test. An Azure model counts as usable until the Azure test has run; a Gemini model only when it answered."""
    found: dict[str, bool] = {}
    tested = False
    for provider in ("azure", "gemini"):
        outcome = results.get(provider)
        if isinstance(outcome, dict) and outcome.get("models"):
            found.update(outcome["models"])
            tested = True
    if not tested:
        return None
    return found


def _usable(key: str, answered: dict[str, bool] | None) -> bool:
    """With no test result yet every model counts as usable; with one, only models that answered do."""
    return answered is None or answered.get(key, False)


def _fits(config: ForgeConfig, role: str, key: str) -> bool:
    return config.llm.models[key].vision if role in ("vision", "critic") else True


def _state(key: str, provider: str, answered: dict[str, bool] | None) -> str:
    """'ok' answered, 'failed' did not answer, 'untested' no test has covered it (a Gemini model before its test)."""
    if answered is None:
        return "untested" if provider == "gemini" else "ok"
    if key not in answered:
        return "untested"
    return "ok" if answered[key] else "failed"


def propose_plan(config: ForgeConfig, results: dict[str, Any], saved: dict[str, str]) -> dict[str, Any]:
    answered = _answers(config, results)
    models = config.llm.models
    roles = []
    chosen: dict[str, str | None] = {}
    for role in ROLES:
        # a critic or planner nobody chose is the coder's model, whichever the plan gave the coder
        default = getattr(config.llm.roles, role) or (
            chosen.get("coder") or config.llm.roles.coder if role in ("critic", "planner") else None
        )
        wanted, why = default, "Default for this role"
        liked = next(
            (
                k
                for k in PREFERENCE.get(role, ())
                if k in models
                and answered is not None
                and answered.get(k, False)
                and not (
                    role == "fallback" and k == chosen.get("coder")
                )  # a fallback that is the coder fails with it
            ),
            None,
        )
        if liked is not None:
            wanted, why = (
                liked,
                f"{models[liked].label} answered its test: proposed by default for this role",
            )
        if saved.get(role) in models and _fits(config, role, saved[role]):
            wanted, why = saved[role], "Your earlier choice"
        if wanted is None or not _usable(wanted, answered):
            stand_in = next(
                (
                    k
                    for k in [default, *sorted(models)]
                    if k in models and _usable(k, answered) and _fits(config, role, k)
                ),
                None,
            )
            if stand_in is None:
                wanted, why = None, "No model is answering"
            else:
                why = f"{wanted or 'The default'} is not answering; using {stand_in} instead"
                wanted = stand_in
        chosen[role] = wanted
        roles.append({"role": role, "model": wanted, "reason": why, "default": default})
    options = [
        {
            "key": key,
            "label": model.label,
            "vision": model.vision,
            "usable": _usable(key, answered),
            "provider": model.provider,
            "state": _state(key, model.provider, answered),
        }
        for key, model in sorted(models.items())
    ]
    notes = []
    forge_database = results.get("postgres_local")
    if isinstance(forge_database, dict) and forge_database.get("status") != "ok":
        notes.append(
            "The DebCraft database is not reachable: DebCraft cannot run database checks or use scratch schemas."
        )
    return {"roles": roles, "options": options, "notes": notes}


def validate_plan(config: ForgeConfig, roles: dict[str, str]) -> dict[str, str]:
    """The user's confirmed choice; raises ValueError (shown on the screen) for anything DebCraft can't apply."""
    unknown_roles = sorted(set(roles) - set(ROLES))
    if unknown_roles:
        raise ValueError(f"Unknown role: {', '.join(unknown_roles)}")
    missing = [role for role in ROLES if role not in roles]
    if missing:
        raise ValueError(f"No model chosen for: {', '.join(missing)}")
    for role, key in roles.items():
        if key not in config.llm.models:
            raise ValueError(f"Unknown model '{key}' for {role}")
        if not _fits(config, role, key):
            raise ValueError(f"{key} cannot read images, so it can't serve the {role} role")
    return dict(roles)


def apply_saved_plan(router: RoleRouter, home: Path) -> None:
    """Called when a session starts. A key that no longer exists in config.yaml is skipped, never fatal."""
    for role, key in store.load(home)["plan"].items():
        if role in ROLES and key in router.config.llm.models:
            router.set_role_model(role, key)
