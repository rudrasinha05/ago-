"""Opt-in text generation adapter for the OpenAI Responses API.

No network request occurs unless the operator explicitly enables paid models.
The gateway never offers tools, web browsing, function calls or shell execution.
"""
from __future__ import annotations

import json
from urllib.request import Request, urlopen


class ResponsesTextProvider:
    ENDPOINT = "https://api.openai.com/v1/responses"

    def __init__(self, *, api_key: str, model: str,
                 timeout_seconds: int = 20, max_output_tokens: int = 256,
                 opener=None):
        if not api_key.strip() or not model.strip():
            raise ValueError("Model and API key required")
        if not 1 <= timeout_seconds <= 60 or not 32 <= max_output_tokens <= 1024:
            raise ValueError("Invalid response bounds")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout_seconds
        self.max_output_tokens = max_output_tokens
        self.opener = opener or urlopen

    def generate(self, prompt: str) -> str:
        if not 1 <= len(prompt.strip()) <= 4000:
            raise ValueError("Prompt out of bounds")
        payload = {
            "model": self.model,
            "store": False,
            "max_output_tokens": self.max_output_tokens,
            "input": [
                {"role": "developer", "content":
                 "Write a concise factual internal review brief. No tool use. "
                 "Never claim an action was executed. Flag uncertain details."},
                {"role": "user", "content": prompt},
            ],
        }
        request = Request(
            self.ENDPOINT, data=json.dumps(payload).encode("utf-8"),
            headers={"Authorization": "Bearer " + self.api_key,
                     "Content-Type": "application/json"},
            method="POST",
        )
        with self.opener(request, timeout=self.timeout) as response:
            raw = response.read(65_537)
        if len(raw) > 65_536:
            raise ValueError("Provider response too large")
        parsed = json.loads(raw)
        outputs = [
            content["text"]
            for item in parsed.get("output", [])
            if item.get("type") == "message"
            for content in item.get("content", [])
            if content.get("type") == "output_text"
            and isinstance(content.get("text"), str)
        ]
        result = "\n".join(outputs).strip()
        if parsed.get("status") != "completed" or not result:
            raise RuntimeError("Text generation did not complete")
        return result[:12000]
