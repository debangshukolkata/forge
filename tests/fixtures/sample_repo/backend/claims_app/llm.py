"""LLM client creation. Tests inject a fake via the LLM_FACTORY config value."""

from __future__ import annotations

import os

from flask import current_app
from langchain_core.language_models import BaseChatModel


def get_chat_model() -> BaseChatModel:
    factory = current_app.config.get("LLM_FACTORY")
    if factory is not None:
        return factory()
    return _create_azure_chat_model()


def _create_azure_chat_model() -> BaseChatModel:
    # Imported lazily: langchain-openai is only installed where the real LLM is used.
    from langchain_openai import AzureChatOpenAI

    return AzureChatOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        api_version=os.environ["AZURE_OPENAI_API_VERSION"],
        azure_deployment=os.environ["AZURE_OPENAI_DEPLOYMENT"],
        temperature=0,
    )
