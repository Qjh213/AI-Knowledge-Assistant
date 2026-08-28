from openai import OpenAI

from app.core.config import settings
from app.core.exceptions import ChatServiceError


class ChatService:
    def __init__(
        self,
        client: OpenAI | None = None,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> None:
        if client is None:
            if not settings.deepseek_api_key:
                raise ChatServiceError(
                    "DeepSeek API key is not configured"
                )

            client = OpenAI(
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url,
            )

        self.client = client
        self.model = model or settings.chat_model
        self.temperature = (
            temperature
            if temperature is not None
            else settings.chat_temperature
        )
        self.max_tokens = (
            max_tokens
            if max_tokens is not None
            else settings.chat_max_tokens
        )

        if not self.model.strip():
            raise ChatServiceError(
                "chat model cannot be empty"
            )

        if not 0.0 <= self.temperature <= 2.0:
            raise ChatServiceError(
                "temperature must be between 0 and 2"
            )

        if self.max_tokens <= 0:
            raise ChatServiceError(
                "max tokens must be greater than zero"
            )

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        if not system_prompt.strip():
            raise ChatServiceError(
                "system prompt cannot be empty"
            )

        if not user_prompt.strip():
            raise ChatServiceError(
                "user prompt cannot be empty"
            )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt.strip(),
                    },
                    {
                        "role": "user",
                        "content": user_prompt.strip(),
                    },
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
            )

            content = response.choices[0].message.content

        except ChatServiceError:
            raise
        except Exception as exc:
            raise ChatServiceError(str(exc)) from exc

        if not content or not content.strip():
            raise ChatServiceError(
                "model returned an empty response"
            )

        return content.strip()