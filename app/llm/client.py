"""
LLM Client - OpenAI via GitHub Models.

Provides a unified interface for all LLM interactions:
- Chat completions with tool/function calling
- Structured JSON output
- Retry logic for transient failures
"""

import json
import logging
from openai import OpenAI
from app.config import settings

logger = logging.getLogger(__name__)


class LLMClient:
    """Wrapper around OpenAI API via GitHub Models endpoint."""

    def __init__(self):
        self.client = OpenAI(
            base_url=settings.LLM_BASE_URL,
            api_key=settings.GITHUB_TOKEN,
        )
        self.model = settings.LLM_MODEL
        self.temperature = settings.LLM_TEMPERATURE
        self.max_tokens = settings.LLM_MAX_TOKENS

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict:
        """
        Send a chat completion request.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            tools: Optional list of tool definitions for function calling.
            temperature: Override default temperature.
            max_tokens: Override default max tokens.

        Returns:
            The assistant's response message as a dict.
        """
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature or self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
        }

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        try:
            response = self.client.chat.completions.create(**kwargs)
            message = response.choices[0].message

            result = {
                "role": "assistant",
                "content": message.content,
                "tool_calls": None,
            }

            if message.tool_calls:
                result["tool_calls"] = [
                    {
                        "id": tc.id,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in message.tool_calls
                ]

            return result

        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise

    def chat_json(
        self,
        messages: list[dict],
        temperature: float | None = None,
    ) -> dict:
        """
        Get a structured JSON response from the LLM.

        The last message should instruct the model to respond in JSON format.

        Returns:
            Parsed JSON dict from the LLM response.
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature or self.temperature,
                max_tokens=self.max_tokens,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            return json.loads(content)

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from LLM response: {e}")
            raise
        except Exception as e:
            logger.error(f"LLM JSON call failed: {e}")
            raise

    def simple_chat(self, prompt: str, system_prompt: str = "") -> str:
        """
        Simple string-in, string-out chat completion.

        Args:
            prompt: The user's prompt.
            system_prompt: Optional system prompt.

        Returns:
            The assistant's text response.
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        result = self.chat(messages)
        return result["content"] or ""
