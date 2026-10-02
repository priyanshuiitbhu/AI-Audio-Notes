import os
import re
import time
import logging
from typing import Optional, List
import requests
from app.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert AI meeting and audio notes summarizer.
Your goal is to extract key insights, actionable takeaways, and a clear executive summary from transcribed audio.

Structure your output in clear, professional Markdown:
### Overview
A concise paragraph capturing the core theme, objective, and context of the recording.

### Key Points
- Bulleted list of the most important concepts, facts, or discussions mentioned.

### Decisions & Conclusions
- Clear summary of any conclusions reached, consensus established, or strategic decisions made (or "None explicitly discussed" if not applicable).

### Action Items
- Concrete next steps, follow-ups, or responsibilities mentioned (or "None identified" if not applicable).

Rules:
- Do not hallucinate or invent information not present in the transcript.
- Keep the summary clear, objective, and well-structured.
"""


class SummaryService:
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
    ):
        self.api_key = api_key or settings.LLM_API_KEY
        self.model = model or settings.LLM_MODEL
        self.base_url = (base_url or settings.LLM_BASE_URL).rstrip("/")

    def _fallback_summary(self, transcript: str) -> str:
        """
        Extractive summary fallback when no LLM API key is provided or API is unreachable.
        Produces structured, high-quality audio notes from the transcript text.
        """
        if not transcript or not transcript.strip():
            return "### Overview\nNo speech content was detected in this recording."

        text = transcript.strip()
        sentences = [s.strip() for s in re.split(r"(?<=[.!?]) +", text) if s.strip()]
        if not sentences:
            sentences = [text]

        # Extract first 2-3 sentences for overview
        overview_text = " ".join(sentences[:3])

        # Extract key points
        key_points = []
        for s in sentences[1:8]:
            if len(s) > 15:
                key_points.append(f"- {s}")

        if not key_points:
            key_points = [f"- {s}" for s in sentences]

        summary_md = f"""### Overview
{overview_text}

### Key Points
{chr(10).join(key_points[:5])}

### Decisions & Conclusions
- Automated notes extracted directly from audio transcript.

### Action Items
- Review full transcript below for additional context and granular timestamps.
"""
        return summary_md

    def _call_llm_api(self, prompt: str, max_retries: int = 3) -> str:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
            "max_tokens": 1200,
        }

        attempt = 0
        backoff = 2.0
        while attempt < max_retries:
            attempt += 1
            try:
                logger.info(f"Calling LLM API ({self.model}) - attempt {attempt}")
                resp = requests.post(url, headers=headers, json=payload, timeout=60)
                if resp.status_code == 200:
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"]
                    return content.strip()
                elif resp.status_code == 429:
                    logger.warning("LLM API rate limited. Retrying...")
                    time.sleep(backoff * attempt)
                    continue
                else:
                    logger.warning(f"LLM API returned status {resp.status_code}: {resp.text[:200]}")
                    time.sleep(backoff)
            except Exception as e:
                logger.warning(f"Error calling LLM API: {e}")
                time.sleep(backoff)

        raise RuntimeError("LLM API call failed after retries.")

    def summarize(self, transcript: str) -> str:
        """
        Generates structured summary of the transcript.
        If transcript is very long (> 2,500 words), chunks and synthesizes.
        Falls back safely if LLM is unavailable.
        """
        if not transcript or not transcript.strip():
            return "### Overview\nNo spoken words were identified in the audio to summarize."

        # If no LLM key is configured, use the smart extractive fallback
        if not self.api_key:
            logger.info("No LLM_API_KEY configured. Using extractive summarizer fallback.")
            return self._fallback_summary(transcript)

        try:
            words = transcript.split()
            if len(words) > 2500:
                # Hierarchical summarization for very long audio
                logger.info(f"Long transcript ({len(words)} words). Using hierarchical summarization.")
                chunk_size = 2000
                chunks = [" ".join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)]
                chunk_summaries = []
                for idx, ch in enumerate(chunks[:4]):
                    prompt = f"Summarize key aspects of part {idx+1}/{len(chunks)} of this transcript:\n\n{ch}"
                    sub_sum = self._call_llm_api(prompt)
                    chunk_summaries.append(sub_sum)

                combined_prompt = (
                    "Below are intermediate notes from a long recording. "
                    "Produce an overarching, unified executive summary adhering to the standard format:\n\n"
                    + "\n\n".join(chunk_summaries)
                )
                return self._call_llm_api(combined_prompt)
            else:
                prompt = f"Please provide a structured summary for the following audio transcript:\n\n{transcript}"
                return self._call_llm_api(prompt)
        except Exception as e:
            logger.error(f"LLM summarization failed: {e}. Falling back to extractive summary.")
            return self._fallback_summary(transcript)


summary_service = SummaryService()
