from __future__ import annotations

import json
from typing import Any


class OllamaFailure(RuntimeError):
    """A sanitized, classifiable failure from the Ollama API."""

    def __init__(self, category: str, message: str) -> None:
        super().__init__(message)
        self.category = category


def request_json(
    httpx_module: Any,
    url: str,
    payload: dict[str, Any],
    timeout: float,
) -> dict[str, Any]:
    """Make one bounded Ollama request; retries are intentionally not automatic."""

    try:
        with httpx_module.Client(timeout=timeout) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            envelope = response.json()
    except httpx_module.TimeoutException as error:
        raise OllamaFailure("timeout", "Ollama inference timed out.") from error
    except httpx_module.ConnectError as error:
        raise OllamaFailure("connection", "Ollama could not be reached.") from error
    except httpx_module.HTTPStatusError as error:
        status_code = error.response.status_code
        category = "model_unavailable" if status_code == 404 else "http_error"
        raise OllamaFailure(category, "Ollama returned an HTTP error.") from error
    except httpx_module.HTTPError as error:
        raise OllamaFailure("connection", "Ollama network request failed.") from error
    except (ValueError, TypeError) as error:
        raise OllamaFailure("invalid_response", "Ollama returned an invalid response.") from error

    if not isinstance(envelope, dict):
        raise OllamaFailure("invalid_response", "Ollama returned an unexpected response.")

    model_text = envelope.get("response")
    if not isinstance(model_text, str) or not model_text.strip():
        raise OllamaFailure("empty_output", "Ollama returned an empty response.")

    try:
        parsed = json.loads(model_text)
    except (json.JSONDecodeError, TypeError) as error:
        raise OllamaFailure("invalid_output", "Ollama returned malformed JSON.") from error

    if not isinstance(parsed, dict):
        raise OllamaFailure("invalid_output", "Ollama returned an unexpected JSON structure.")
    return parsed


def public_reason(failure: OllamaFailure) -> str:
    return {
        "connection": "Ollama connection failed",
        "timeout": "Ollama inference timed out",
        "http_error": "Ollama returned an HTTP error",
        "model_unavailable": "Ollama model is unavailable",
        "empty_output": "Ollama returned empty output",
        "invalid_response": "Ollama returned an invalid response",
        "invalid_output": "Ollama returned invalid structured output",
    }.get(failure.category, "Ollama inference failed")
