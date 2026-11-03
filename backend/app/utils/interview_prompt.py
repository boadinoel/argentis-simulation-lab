"""Shared language and evidence contract for interactive and report interviews."""
from .locale import get_language_instruction

INTERVIEW_PROMPT_PREFIX = "Respond directly as your simulated persona, using saved actions and context. Do not call tools. Do not invent actual customers, contracts or outcomes. "

def optimize_interview_prompt(prompt):
    if not prompt or prompt.startswith(INTERVIEW_PROMPT_PREFIX):
        return prompt
    return f"{INTERVIEW_PROMPT_PREFIX}{get_language_instruction()}\nAnswer each question in plain text. Question: {prompt}"
