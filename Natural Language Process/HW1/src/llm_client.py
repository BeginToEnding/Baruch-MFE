from __future__ import annotations
import os
import requests
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()


class BaseLLMClient:
    def __init__(self, config: dict):
        self.config = config

    def generate(self, messages: List[Dict], **kwargs) -> str:
        raise NotImplementedError


class OpenAIClient(BaseLLMClient):
    def __init__(self, config: dict):
        super().__init__(config)
        try:
            from openai import OpenAI
        except ImportError as e:
            raise ImportError("Please install openai package to use OpenAIClient.") from e

        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            raise ValueError("OPENAI_API_KEY not found.")
        self.client = OpenAI(api_key=api_key)

    def generate(self, messages: List[Dict], **kwargs) -> str:
        model_name = kwargs.get("model_name", self.config["model_name"])
        max_tokens = kwargs.get("max_tokens", self.config.get("max_tokens", 1800))
        temperature = kwargs.get("temperature", self.config.get("temperature", 0.1))

        request_kwargs = {
            "model": model_name,
            "messages": messages,
            "max_completion_tokens": max_tokens,
        }

        # Some newer models may not support temperature; keep it optional.
        if temperature is not None:
            request_kwargs["temperature"] = temperature

        resp = self.client.chat.completions.create(**request_kwargs)
        return resp.choices[0].message.content or ""


class OllamaClient(BaseLLMClient):
    def __init__(self, config: dict):
        super().__init__(config)
        self.host = config.get("ollama_host", "http://localhost:11434")

    def generate(self, messages: List[Dict], **kwargs) -> str:
        model_name = kwargs.get("model_name", self.config["model_name"])
        payload = {
            "model": model_name,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": kwargs.get("temperature", self.config.get("temperature", 0.1)),
                "num_ctx": kwargs.get("num_ctx", self.config.get("num_ctx", 32768)),
                "num_predict": kwargs.get("max_tokens", self.config.get("max_tokens", 1800)),
            },
            "think": kwargs.get("think", self.config.get("think", False)),
        }
        timeout = kwargs.get("timeout", self.config.get("timeout", 180))
        r = requests.post(f"{self.host}/api/chat", json=payload, timeout=timeout)
        r.raise_for_status()
        obj = r.json()
        return obj.get("message", {}).get("content", "")


class LLMClientFactory:
    @staticmethod
    def create(config: dict) -> BaseLLMClient:
        provider = config.get("provider", "openai").lower()
        if provider == "openai":
            return OpenAIClient(config)
        if provider == "ollama":
            return OllamaClient(config)
        raise ValueError(f"Unsupported provider: {provider}")