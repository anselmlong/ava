"""Google Gemini LLM service."""

from typing import List, Optional, AsyncGenerator

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

from src.config.settings import settings
from src.config.logging import get_logger

logger = get_logger(__name__)


class GeminiService:
    """Service for interacting with Google Gemini API."""

    def __init__(self):
        """Initialize the Gemini service."""
        if not settings.google_api_key:
            raise ValueError("GOOGLE_API_KEY is required for Gemini service")

        genai.configure(api_key=settings.google_api_key)

        # Configure the model
        self.model = genai.GenerativeModel(
            model_name=settings.gemini_model,
            generation_config={
                "temperature": settings.gemini_temperature,
                "max_output_tokens": settings.gemini_max_tokens,
                "top_p": 0.95,
                "top_k": 40,
            },
            safety_settings={
                HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
                HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
            },
        )

        self.system_prompt = """You are Ava, a helpful, young, excited, and enthusiastic personal assistant. You are sassy and slightly sarcastic, but always helpful.
Answer concisely and succintly.

Key traits:
- Type in lowercase unless explicitly instructed otherwise
- Be sassy and slightly sarcastic in your responses
- Use emojis rarely and only when appropriate
- Stay helpful and proactive despite your sass
- Remember context from the conversation
- Be honest about limitations

You can help with:
- Answering questions and providing information
- Task planning and organization
- Research and analysis
- General conversation and support"""

    async def generate(
        self,
        message: str,
        history: Optional[List[dict]] = None,
        system_prompt: Optional[str] = None,
    ) -> str:
        """Generate a response to a message.

        Args:
            message: The user's message
            history: Optional conversation history as list of {role, content} dicts
            system_prompt: Optional custom system prompt

        Returns:
            The generated response text
        """
        try:
            # Build the conversation history
            contents = []

            # Add system prompt as first message
            prompt = system_prompt or self.system_prompt
            contents.append(
                {"role": "user", "parts": [f"[System Instructions]\n{prompt}"]}
            )
            contents.append(
                {
                    "role": "model",
                    "parts": [
                        "Understood. I am Ava, your AI assistant. How can I help you today?"
                    ],
                }
            )

            # Add conversation history
            if history:
                for msg in history:
                    role = "user" if msg["role"] == "user" else "model"
                    contents.append({"role": role, "parts": [msg["content"]]})

            # Add the current message
            contents.append({"role": "user", "parts": [message]})

            # Generate response
            response = await self.model.generate_content_async(contents)

            if not response.text:
                logger.warning("Empty response from Gemini")
                return (
                    "I apologize, but I couldn't generate a response. Please try again."
                )

            return response.text

        except Exception as e:
            logger.error("Error generating response", error=str(e))
            raise

    async def generate_stream(
        self,
        message: str,
        history: Optional[List[dict]] = None,
        system_prompt: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """Generate a streaming response.

        Args:
            message: The user's message
            history: Optional conversation history
            system_prompt: Optional custom system prompt

        Yields:
            Chunks of the generated response
        """
        try:
            # Build contents same as generate()
            contents = []

            prompt = system_prompt or self.system_prompt
            contents.append(
                {"role": "user", "parts": [f"[System Instructions]\n{prompt}"]}
            )
            contents.append(
                {
                    "role": "model",
                    "parts": [
                        "Understood. I am Ava, your AI assistant. How can I help you today?"
                    ],
                }
            )

            if history:
                for msg in history:
                    role = "user" if msg["role"] == "user" else "model"
                    contents.append({"role": role, "parts": [msg["content"]]})

            contents.append({"role": "user", "parts": [message]})

            # Generate streaming response
            response = await self.model.generate_content_async(
                contents,
                stream=True,
            )

            async for chunk in response:
                if chunk.text:
                    yield chunk.text

        except Exception as e:
            logger.error("Error in streaming generation", error=str(e))
            raise

    async def count_tokens(self, text: str) -> int:
        """Count the number of tokens in text.

        Args:
            text: The text to count tokens for

        Returns:
            Number of tokens
        """
        try:
            result = await self.model.count_tokens_async(text)
            return result.total_tokens
        except Exception as e:
            logger.error("Error counting tokens", error=str(e))
            # Return estimate based on character count
            return len(text) // 4


# Singleton instance
_gemini_service: Optional[GeminiService] = None


def get_gemini_service() -> GeminiService:
    """Get the Gemini service singleton."""
    global _gemini_service
    if _gemini_service is None:
        _gemini_service = GeminiService()
    return _gemini_service
