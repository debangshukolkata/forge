"""The language model of the service: Azure OpenAI, configured by the AZURE_OPENAI_* variables."""

from __future__ import annotations

import os

from openai import AzureOpenAI


def complete(prompt: str, json_answer: bool = False) -> str:
    """The model's answer to one prompt. `json_answer`: it answers with one JSON object (say so in the prompt)."""
    client = AzureOpenAI(
        azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
        api_key=os.environ["AZURE_OPENAI_API_KEY"],
        api_version=os.environ["AZURE_OPENAI_API_VERSION"],
        timeout=120,
    )
    extra = {"response_format": {"type": "json_object"}} if json_answer else {}
    answer = client.chat.completions.create(
        model=os.environ["AZURE_OPENAI_DEPLOYMENT"], messages=[{"role": "user", "content": prompt}], **extra
    )
    return answer.choices[0].message.content or ""
