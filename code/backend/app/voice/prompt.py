from pathlib import Path

SYSTEM_PROMPT = (
    Path(__file__).with_name("system_prompt.md").read_text(encoding="utf-8").strip()
)
