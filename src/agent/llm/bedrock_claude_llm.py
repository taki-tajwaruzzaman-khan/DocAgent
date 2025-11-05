# Copyright (c) Meta Platforms, Inc. and affiliates
from typing import List, Dict, Any, Optional
import anthropic
from .base import BaseLLM
from .rate_limiter import RateLimiter
import logging

class BedrockClaudeLLM(BaseLLM):
    """Amazon Bedrock Claude API wrapper."""

    def __init__(
        self,
        model: str,
        aws_region: str = "us-east-1",
        aws_access_key: Optional[str] = None,
        aws_secret_key: Optional[str] = None,
        aws_session_token: Optional[str] = None,
        rate_limits: Optional[Dict[str, Any]] = None
    ):
        """Initialize Bedrock Claude LLM.

        Args:
            model: Model identifier (e.g., "anthropic.claude-3-5-sonnet-20241022-v2:0")
            aws_region: AWS region for Bedrock (default: us-east-1)
            aws_access_key: AWS access key (optional, uses environment/profile if not provided)
            aws_secret_key: AWS secret key (optional, uses environment/profile if not provided)
            aws_session_token: AWS session token (optional)
            rate_limits: Optional dictionary with rate limit settings
        """
        # Initialize Bedrock client
        client_kwargs = {"aws_region": aws_region}

        # Add credentials if provided, otherwise uses environment variables or AWS profile
        if aws_access_key:
            client_kwargs["aws_access_key"] = aws_access_key
        if aws_secret_key:
            client_kwargs["aws_secret_key"] = aws_secret_key
        if aws_session_token:
            client_kwargs["aws_session_token"] = aws_session_token

        self.client = anthropic.AnthropicBedrock(**client_kwargs)
        self.model = model

        # Default rate limits for Claude on Bedrock
        # Note: These should be adjusted based on your Bedrock quotas
        default_limits = {
            "requests_per_minute": 50,
            "input_tokens_per_minute": 20000,
            "output_tokens_per_minute": 8000,
            "input_token_price_per_million": 3.0,
            "output_token_price_per_million": 15.0
        }

        # Use provided rate limits or defaults
        limits = rate_limits or default_limits

        # Initialize rate limiter
        self.rate_limiter = RateLimiter(
            provider="Bedrock-Claude",
            requests_per_minute=limits.get("requests_per_minute", default_limits["requests_per_minute"]),
            input_tokens_per_minute=limits.get("input_tokens_per_minute", default_limits["input_tokens_per_minute"]),
            output_tokens_per_minute=limits.get("output_tokens_per_minute", default_limits["output_tokens_per_minute"]),
            input_token_price_per_million=limits.get("input_token_price_per_million", default_limits["input_token_price_per_million"]),
            output_token_price_per_million=limits.get("output_token_price_per_million", default_limits["output_token_price_per_million"])
        )

    def _count_tokens(self, text: str) -> int:
        """Count tokens in a string using Claude's tokenizer.

        Args:
            text: Text to count tokens for

        Returns:
            Token count
        """
        if not text:
            return 0

        try:
            # Format text as a message for token counting
            count = self.client.beta.messages.count_tokens(
                model=self.model,
                messages=[
                    {"role": "user", "content": text}
                ]
            )
            return count.input_tokens
        except Exception as e:
            # Log the error but don't fail
            logging.warning(f"Failed to count tokens with Claude tokenizer: {e}")
            # Fallback: rough estimate if tokenizer fails
            return len(text.split()) * 1.3

    def _count_messages_tokens(self, messages: List[Dict[str, str]], system_message: Optional[str] = None) -> int:
        """Count tokens in message list with optional system message.

        Args:
            messages: List of message dictionaries
            system_message: Optional system message

        Returns:
            Total token count
        """
        if not messages:
            return 0

        # Convert messages to Claude format
        claude_messages = [self._convert_to_claude_message(msg) for msg in messages
                          if msg["role"] != "system"]

        # Format system message if provided
        system_content = None
        if system_message:
            system_content = system_message

        try:
            # Use the API to count tokens for all messages at once
            count = self.client.beta.messages.count_tokens(
                model=self.model,
                messages=claude_messages,
                system=system_content
            )
            return count.input_tokens
        except Exception as e:
            # Log the error but don't fail
            logging.warning(f"Failed to count tokens with Claude tokenizer: {e}")

            # Fallback: count tokens individually
            total_tokens = 0
            for msg in claude_messages:
                if "content" in msg and msg["content"]:
                    total_tokens += self._count_tokens(msg["content"])

            # Add system message tokens if provided
            if system_message:
                total_tokens += self._count_tokens(system_message)

            # Add overhead for message formatting
            total_tokens += 10 * len(claude_messages)  # Add ~10 tokens per message for formatting

            return total_tokens

    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: Optional[int]
    ) -> str:
        """Generate a response using Bedrock Claude API with rate limiting.

        Args:
            messages: List of message dictionaries
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            Generated response text
        """
        # Extract system message if present
        system_message = None
        chat_messages = []

        for msg in messages:
            if msg["role"] == "system":
                system_message = msg["content"]
            else:
                chat_messages.append(self._convert_to_claude_message(msg))

        # Count input tokens
        input_tokens = self._count_messages_tokens(messages, system_message)

        # Wait if we're approaching rate limits
        self.rate_limiter.wait_if_needed(input_tokens, max_tokens)

        # Make the API call
        response = self.client.messages.create(
            model=self.model,
            messages=chat_messages,
            system=system_message,
            temperature=temperature,
            max_tokens=max_tokens
        )

        result_text = response.content[0].text

        # Count output tokens and record request
        output_tokens = self._count_tokens(result_text)
        self.rate_limiter.record_request(input_tokens, output_tokens)

        return result_text

    def format_message(self, role: str, content: str) -> Dict[str, str]:
        """Format message for Claude API.

        Args:
            role: Message role (system, user, assistant)
            content: Message content

        Returns:
            Formatted message dictionary
        """
        # Store in standard format, conversion happens in generate()
        return {"role": role, "content": content}

    def _convert_to_claude_message(self, message: Dict[str, str]) -> Dict[str, str]:
        """Convert standard message format to Claude's format.

        Args:
            message: Standard format message

        Returns:
            Claude format message
        """
        role_mapping = {
            "user": "user",
            "assistant": "assistant"
        }

        role = role_mapping[message["role"]]
        content = message["content"]

        return {"role": role, "content": content}
