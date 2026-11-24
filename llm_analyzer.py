
import json
import os
import urllib.request
from pathlib import Path

CFG = {
    "llm_url": os.getenv("LLM_BASE_URL", "http://localhost:11434/v1"),
    "llm_key": os.getenv("LLM_API_KEY", "ollama"),
    "llm_model": os.getenv("LLM_MODEL", "qwen2.5:7b"),
    "timeout": 300,
}

PROMPT_PATH = Path(__file__).parent / "prompts" / "prompt_v1.md"
PROMPT = PROMPT_PATH.read_text(encoding="utf-8")


def call_llm(vacancy):
    body = json.dumps({
        "model": CFG["llm_model"],
        "temperature": 0,
        "messages": [
            {
                "role": "user",
                "content": PROMPT + "\n\n" + json.dumps(
                    vacancy, ensure_ascii=False
                )
            }
        ]
    }).encode("utf-8")

    req = urllib.request.Request(
        CFG["llm_url"].rstrip("/") + "/chat/completions",
        body,
        {
            "Content-Type": "application/json",
            "Authorization": "Bearer " + CFG["llm_key"]
        }
    )

    with urllib.request.urlopen(req, timeout=CFG["timeout"]) as r:
        content = json.load(r)["choices"][0]["message"]["content"]

    content = content.strip()

    if content.startswith("```"):
        content = content.removeprefix("```json")
        content = content.removeprefix("```")
        content = content.removesuffix("```").strip()

    try:
        result = json.loads(content)
        return result.get("issues", [])

    except (ValueError, AttributeError) as e:
        print("Ошибка обработки JSON:", e)
        return []
