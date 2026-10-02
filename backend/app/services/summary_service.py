import os
import re
import time
import logging
from typing import Optional, List
from app.config import settings

logger = logging.getLogger(__name__)

GEMINI_PROMPT_TEMPLATE = """You are an assistant that summarizes audio transcripts.

Your task is to produce an accurate, concise and useful summary of the transcript below.

Structure the response as:

## Overview

Provide a short paragraph explaining what the audio is about.

## Key Points

List the most important points discussed in the audio.

## Important Details

Include important facts, explanations, decisions, conclusions, technical details, names, numbers or other information that is significant.

## Action Items

If the transcript contains action items, list them.
If there are no action items, do not invent any.

Rules:

- Only use information present in the transcript.
- Do not invent facts.
- Do not make assumptions.
- Do not add external information.
- Preserve important technical terms.
- Preserve important names and numbers.
- Do not distort the meaning of the transcript.
- Keep the summary concise and readable.
- If the transcript is unclear or incomplete, acknowledge the uncertainty rather than inventing missing information.

Transcript:

{transcript}"""


class GeminiError(Exception):
    """Base exception for Gemini summarization errors."""
    pass


class GeminiAuthError(GeminiError):
    """Authentication or invalid API key error."""
    pass


class GeminiRateLimitError(GeminiError):
    """Rate limit or quota error."""
    pass


class GeminiTimeoutError(GeminiError):
    """Timeout error."""
    pass


class SummaryService:
    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model_name = model_name or settings.GEMINI_MODEL or "gemini-3.5-flash-lite"
        self._client = None

    def _get_client(self):
        if not self.api_key:
            raise GeminiAuthError("GEMINI_API_KEY is not configured in environment.")

        if self._client is None:
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def _fallback_summary(self, transcript: str) -> str:
        """
        Extractive structured fallback when API key is missing or during offline testing.
        Never hallucinates and adheres to the required Markdown structure.
        """
        if not transcript or not transcript.strip():
            return "## Overview\n\nNo speech content was detected in this recording."

        text = transcript.strip()
        sentences = [s.strip() for s in re.split(r"(?<=[.!?]) +", text) if s.strip()]
        if not sentences:
            sentences = [text]

        overview_text = " ".join(sentences[:2])
        key_points = [f"- {s}" for s in sentences[1:6] if len(s) > 10]
        if not key_points:
            key_points = [f"- {s}" for s in sentences[:3]]

        return f"""## Overview

{overview_text}

## Key Points

{chr(10).join(key_points)}

## Important Details

- Audio transcribed from source recording without additional external context.

## Action Items

- Review the complete transcript below for detailed timestamps and context."""

    def _call_gemini_single(self, prompt: str, max_retries: int = 3) -> str:
        client = self._get_client()
        attempt = 0
        backoff = 2.0

        while attempt < max_retries:
            attempt += 1
            try:
                logger.info(f"Calling Google Gemini ({self.model_name}) - attempt {attempt}/{max_retries}")
                response = client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                )

                if not response:
                    raise GeminiError("Gemini returned an empty response object.")

                text = response.text
                if not text or not text.strip():
                    raise GeminiError("Gemini generated an empty text summary.")

                return text.strip()

            except (GeminiError, GeminiAuthError, GeminiRateLimitError, GeminiTimeoutError):
                # Explicit domain exceptions raised internally should propagate immediately
                raise
            except Exception as e:
                err_str = str(e)
                logger.warning(f"Gemini API attempt {attempt} error: {err_str}")

                # Check for non-retryable auth errors (401, 403, invalid key)
                if "API_KEY_INVALID" in err_str or "PERMISSION_DENIED" in err_str or "403" in err_str or "401" in err_str:
                    logger.error("Gemini authentication failure. Not retrying.")
                    raise GeminiAuthError("Gemini authentication failed: Invalid or unauthorized API key.")

                # Check for rate limit / quota (429)
                if "RESOURCE_EXHAUSTED" in err_str or "429" in err_str:
                    logger.warning("Gemini rate limit exceeded. Backing off...")
                    if attempt >= max_retries:
                        raise GeminiRateLimitError("Gemini rate limit reached. Please try again in a few moments.")
                    time.sleep(backoff * (2 ** (attempt - 1)))
                    continue

                # Check for timeout / network
                if isinstance(e, TimeoutError) or "timeout" in err_str.lower() or "timed out" in err_str.lower() or "deadline" in err_str.lower():
                    logger.warning("Gemini request timed out.")
                    if attempt >= max_retries:
                        raise GeminiTimeoutError("Connection to Google Gemini timed out.")
                    time.sleep(backoff)
                    continue

                # Server error or 503 overload
                if "503" in err_str or "500" in err_str or "UNAVAILABLE" in err_str:
                    logger.warning("Gemini service temporarily unavailable (503/500). Retrying...")
                    if attempt >= max_retries:
                        raise GeminiError(f"Google Gemini is temporarily unavailable ({err_str[:150]}).")
                    time.sleep(backoff * (2 ** (attempt - 1)))
                    continue

                if attempt >= max_retries:
                    raise GeminiError(f"Failed to generate summary with Gemini: {err_str[:200]}")
                time.sleep(backoff)

        raise GeminiError("Gemini summarization failed after maximum retries.")

    def generate_summary(self, transcript: str) -> str:
        """
        Generates a concise, structured executive summary of the audio transcript using Google Gemini.
        Handles long transcripts safely via hierarchical summarization if needed.
        """
        if not transcript or not transcript.strip():
            return "## Overview\n\nNo speech content was detected in this recording."

        # If GEMINI_API_KEY is not configured, fallback gracefully with a warning
        if not self.api_key:
            logger.warning("GEMINI_API_KEY is not set. Using structured extractive fallback.")
            return self._fallback_summary(transcript)

        words = transcript.strip().split()

        # For exceptionally large transcripts (> 15,000 words), use hierarchical chunking
        if len(words) > 15000:
            logger.info(f"Very large transcript ({len(words)} words). Processing with hierarchical summarization.")
            chunk_size = 10000
            chunks = [" ".join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)]
            intermediate_summaries = []

            for idx, ch in enumerate(chunks):
                ch_prompt = f"Summarize section {idx + 1} of {len(chunks)} of this audio recording:\n\n{ch}"
                inter_sum = self._call_gemini_single(ch_prompt)
                intermediate_summaries.append(inter_sum)

            combined_text = "\n\n".join(intermediate_summaries)
            final_prompt = GEMINI_PROMPT_TEMPLATE.format(transcript=combined_text)
            return self._call_gemini_single(final_prompt)

        # Standard transcript (<= 15,000 words): single direct Gemini prompt
        prompt = GEMINI_PROMPT_TEMPLATE.format(transcript=transcript.strip())
        return self._call_gemini_single(prompt)

    def summarize(self, transcript: str) -> str:
        """Alias for generate_summary to ensure backward compatibility."""
        return self.generate_summary(transcript)


summary_service = SummaryService()
