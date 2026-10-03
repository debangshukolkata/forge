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


def _usable(key: str, answered: dict[str, bool] | None) -> bool:
    """With no azure result yet every model counts as usable; with one, only models that answered do."""
    return answered is None or answered.get(key, False)


def _fits(config: ForgeConfig, role: str, key: str) -> bool:
    return config.llm.models[key].vision if role == "vision" else True


def propose_plan(config: ForgeConfig, results: dict[str, Any], saved: dict[str, str]) -> dict[str, Any]:
    azure = results.get("azure")
    answered: dict[str, bool] | None = (
        azure.get("models") if isinstance(azure, dict) and azure.get("models") else None
    )
    models = config.llm.models
    roles = []
    for role in ROLES:
        default = getattr(config.llm.roles, role)
        wanted, why = default, "Default for this role"
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
        roles.append({"role": role, "model": wanted, "reason": why, "default": default})
    options = [
        {
            "key": key,
            "label": model.label,
            "vision": model.vision,
            "usable": _usable(key, answered),
        }
        for key, model in sorted(models.items())
    ]
    notes = []
    postgres = results.get("postgres")
    if isinstance(postgres, dict) and postgres.get("status") != "ok":
        notes.append("No database is reachable: Forge cannot check data or use scratch schemas.")
    return {"roles": roles, "options": options, "notes": notes}


def validate_plan(config: ForgeConfig, roles: dict[str, str]) -> dict[str, str]:
    """The user's confirmed choice; raises ValueError (shown on the screen) for anything Forge can't apply."""
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
