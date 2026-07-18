from __future__ import annotations

import os
from typing import Any

from langchain.chat_models import init_chat_model
from langchain_core.language_models.chat_models import BaseChatModel

from big_bear_ai.config import Settings


def create_chat_model(
    settings: Settings, model_name: str | None = None
) -> BaseChatModel:
    selected_model = model_name or settings.model
    kwargs: dict[str, Any] = {}
    if selected_model.startswith("google_genai:"):
        api_key = os.getenv("GOOGLE_GENERATIVE_AI_API_KEY")
        if api_key:
            kwargs["api_key"] = api_key
    return init_chat_model(selected_model, **kwargs)
