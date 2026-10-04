"""
Thin client for Gemma 4 via the local Ollama HTTP API (127.0.0.1 only).

- One request at a time (a lock), because a laptop runs one model instance.
- Structured output through Ollama's JSON-schema `format` option.
- Low temperature, explicit num_ctx, keep_alive so the model stays loaded.
"""
from __future__ import annotations

import base64
import json
import threading
import time

import httpx

import config


class GemmaError(RuntimeError):
    pass


class Gemma:
    def __init__(self, host: str = config.OLLAMA_HOST, model: str = config.MODEL):
        self.host = host
        self.model = model
        self._lock = threading.Lock()
        self._client = httpx.Client(
            base_url=host,
            timeout=httpx.Timeout(config.LLM_TIMEOUT_S, connect=3.0),
            trust_env=False,  # never route localhost traffic through a proxy
        )
        self.last_stats: dict = {}
        self._avail, self._avail_at = False, -1e9

    # ---------- status ----------
    def status(self) -> dict:
        try:
            r = self._client.get("/api/tags", timeout=3.0)
            r.raise_for_status()
            names = [m["name"] for m in r.json().get("models", [])]
        except Exception as e:  # noqa: BLE001 - any failure means "not available"
            return {"running": False, "model": self.model, "model_present": False, "error": str(e)}
        want = self.model if ":" in self.model else f"{self.model}:latest"
        return {"running": True, "model": self.model, "model_present": want in names, "installed": names}

    def available(self) -> bool:
        # Cached briefly: on Windows a refused localhost connection can take ~2 s.
        now = time.monotonic()
        if now - self._avail_at > 10:
            s = self.status()
            self._avail, self._avail_at = s["running"] and s["model_present"], now
        return self._avail

    # ---------- calls ----------
    def chat(self, messages: list[dict], schema: dict | None = None, *, num_predict: int | None = None,
             think: bool | None = None) -> tuple[str, str | None]:
        options = {"temperature": config.TEMPERATURE, "num_ctx": config.NUM_CTX}
        if num_predict:
            options["num_predict"] = num_predict
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "keep_alive": config.KEEP_ALIVE,
            "options": options,
        }
        if schema is not None:
            payload["format"] = schema
        # Gemma 4 thinks by default in recent Ollama builds (~10x slower on CPU), so always
        # say so explicitly; reasoning is only requested for the one "deep" clause when enabled.
        payload["think"] = bool(config.THINK and think)

        t0 = time.perf_counter()
        with self._lock:
            try:
                r = self._client.post("/api/chat", json=payload)
                r.raise_for_status()
            except httpx.HTTPError as e:
                raise GemmaError(f"Ollama request failed: {e}") from e
        data = r.json()
        msg = data.get("message", {})
        self.last_stats = {
            "wall_s": round(time.perf_counter() - t0, 2),
            "eval_count": data.get("eval_count"),
            "prompt_eval_count": data.get("prompt_eval_count"),
            "tokens_per_s": round(data["eval_count"] / (data["eval_duration"] / 1e9), 1)
            if data.get("eval_count") and data.get("eval_duration") else None,
        }
        return msg.get("content", ""), msg.get("thinking")

    def chat_json(self, system: str, user: str, schema: dict, *, retries: int = 1,
                  num_predict: int | None = 700, think: bool | None = None,
                  media: list[bytes] | None = None) -> tuple[dict, str | None]:
        """`media`: raw image or WAV bytes attached to the user turn (Gemma 4 E2B/E4B accept audio)."""
        user_msg: dict = {"role": "user", "content": user}
        if media:
            user_msg["images"] = [base64.b64encode(m).decode("ascii") for m in media]
        messages = [{"role": "system", "content": system}, user_msg]
        last_err = None
        for _ in range(retries + 1):
            content, thinking = self.chat(messages, schema, num_predict=num_predict, think=think)
            try:
                return json.loads(content), thinking
            except json.JSONDecodeError as e:
                last_err = e
        raise GemmaError(f"model did not return valid JSON: {last_err}")

    def warmup(self) -> dict:
        t0 = time.perf_counter()
        self.chat([{"role": "user", "content": "Reply with the word OK."}], num_predict=4)
        return {"warmup_s": round(time.perf_counter() - t0, 2)}
