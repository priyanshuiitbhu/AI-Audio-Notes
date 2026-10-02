#!/usr/bin/env python3
"""
Development/test script for Google Gemini summarization integration.
Loads GEMINI_API_KEY from environment and generates a structured summary for a test transcript.
DOES NOT PRINT THE API KEY.
"""

import os
import sys

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv

load_dotenv()

from app.config import settings
from google import genai

SAMPLE_TRANSCRIPT = """
Hello everyone. In today's product sync we discussed the release roadmap for the Audio Notes platform.
Sarah reported that the speech-to-text accuracy with Gnani ASR improved by fifteen percent after enabling inverse text normalization.
David confirmed that the backend task queue is now processing two-minute audio recordings asynchronously with no timeouts.
The main decision reached was to use Google Gemini for generating executive summaries and action items.
Action item for Sarah: Finalize the Indian language benchmark tests by Friday.
Action item for David: Deploy the background worker to Railway and connect it with the production PostgreSQL database.
"""

PROMPT_TEMPLATE = """You are an assistant that summarizes audio transcripts.

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


def main():
    api_key = os.environ.get("GEMINI_API_KEY") or settings.GEMINI_API_KEY
    if not api_key:
        print("ERROR: GEMINI_API_KEY is not configured in environment or .env file.")
        sys.exit(1)

    model_name = os.environ.get("GEMINI_MODEL") or settings.GEMINI_MODEL
    print(f"Initializing Google Gemini client with model: '{model_name}'...")

    try:
        client = genai.Client(api_key=api_key)
        prompt = PROMPT_TEMPLATE.format(transcript=SAMPLE_TRANSCRIPT)

        print("Sending sample transcript to Gemini...")
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
        )

        if not response or not response.text:
            print("ERROR: Gemini returned an empty response.")
            sys.exit(1)

        print("\n" + "=" * 60)
        print("GENERATED GEMINI SUMMARY:")
        print("=" * 60 + "\n")
        print(response.text.strip())
        print("\n" + "=" * 60)
        print("SUCCESS: Gemini integration verified successfully!")

    except Exception as e:
        print(f"ERROR calling Gemini: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
