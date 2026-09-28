"""Dev-only, run by the user (docs/DECISIONS.md D-019).

One-off: copy Orchestrix's Azure chat provider into Forge's .env. Read-only on Orchestrix's DB.
Never prints secret values — only presence, lengths and the endpoint host."""

import asyncio
from urllib.parse import urlparse

from app.core.crypto import decrypt_secret
from app.core.db import async_session_factory
from app.models.credential import Credential
from app.models.llm_model import LLMModel
from app.models.llm_provider import LLMProvider
from sqlalchemy import select

FORGE_ENV = r"c:\Work\Projects\Forge\.env"


async def main() -> None:
    async with async_session_factory() as db:
        rows = (await db.execute(select(LLMProvider))).scalars().all()
        chat = [p for p in rows if str(p.kind).lower().endswith("azure") and "embed" not in p.name.lower()]
        print("azure chat providers found:", [p.name for p in chat])
        if len(chat) != 1:
            raise SystemExit("expected exactly one Azure chat provider — stopping")
        provider = chat[0]
        cred = await db.get(Credential, provider.credential_id)
        models = (
            (await db.execute(select(LLMModel).where(LLMModel.provider_id == provider.id))).scalars().all()
        )
        print("models on provider:", [(m.display_name, m.model_id) for m in models])
        if len(models) != 1:
            raise SystemExit("expected exactly one model — stopping")
        key = decrypt_secret(cred.encrypted_secret)
        values = {
            "AZURE_OPENAI_ENDPOINT": provider.api_base,
            "AZURE_OPENAI_API_VERSION": provider.api_version,
            "AZURE_OPENAI_DEPLOYMENT": models[0].model_id,
            "AZURE_OPENAI_API_KEY": key,
        }
    with open(FORGE_ENV, "a", encoding="utf-8") as f:
        f.write(f"# Azure OpenAI — copied from Orchestrix provider '{provider.name}'\n")
        for k, v in values.items():
            f.write(f"{k}={v}\n")
    print("endpoint host:", urlparse(provider.api_base).hostname)
    print("api_version:", provider.api_version)
    print("deployment:", models[0].model_id)
    print("key: present, length", len(key))


asyncio.run(main())
