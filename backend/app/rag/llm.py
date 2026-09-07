# -*- coding: utf-8 -*-
"""智法通 V2 —— 统一 LLM 客户端（Ollama /api/chat），复用连接，支持 JSON 模式与流式。"""
from __future__ import annotations

import json
from typing import AsyncGenerator, Optional

import httpx

from app.config import settings


class LLMClient:
    def __init__(self) -> None:
        self.base_url = settings.OLLAMA_BASE_URL.rstrip("/")
        self.model = settings.OLLAMA_MODEL
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(settings.OLLAMA_TIMEOUT, connect=5.0)
        )

    async def close(self) -> None:
        try:
            await self._client.aclose()
        except Exception:
            pass

    async def complete(
        self,
        messages: list[dict],
        *,
        json_mode: bool = False,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """完整生成。失败返回空串（调用方做兜底）。"""
        body: dict = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": settings.OLLAMA_TEMPERATURE if temperature is None else temperature,
                "num_predict": settings.OLLAMA_MAX_TOKENS if max_tokens is None else max_tokens,
            },
        }
        if json_mode:
            body["format"] = "json"
        try:
            resp = await self._client.post(f"{self.base_url}/api/chat", json=body)
            if resp.status_code == 200:
                return resp.json().get("message", {}).get("content", "") or ""
        except Exception:
            pass
        return ""

    async def complete_stream(self, messages: list[dict], temperature: float = 0.7) -> AsyncGenerator[str, None]:
        body = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": {"temperature": temperature, "num_predict": settings.OLLAMA_MAX_TOKENS},
        }
        try:
            async with self._client.stream("POST", f"{self.base_url}/api/chat", json=body) as resp:
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        tok = data.get("message", {}).get("content", "")
                        if tok:
                            yield tok
                        if data.get("done"):
                            break
                    except Exception:
                        continue
        except Exception:
            return


llm_client = LLMClient()
