import re
from collections.abc import Callable

from groq import Groq

from config import API_KEY, HISTORY_LIMIT, HISTORY_PATH, MEMORY_PATH, MODEL_ID
from memory import default_memory, load_json, save_json
from tools import TOOLS

TOOL_RE = re.compile(r"\[\[\s*([A-Z_]+)(?::\s*(.*?))?\s*\]\]")
FACT_RE = re.compile(r"\[SAVE_FACT:\s*(.*?)\]")


def build_prompt(memory: dict) -> str:
    facts = memory.get("facts") or []
    return f"""You are ZEUS (Zero Effort Universal Sidekick).
User: {memory.get("user_name", "User")} | Context: {facts}

[AVAILABLE TOOLS]
- [[GET_TIME]]
- [[GET_SYSTEM_STATUS]]
- [[LIST_FILES: path]]
- [[READ_FILE: path]]
- [[SEARCH_WEB: query]]

[CRITICAL INSTRUCTIONS]
1. If you need information, output the tool tag ONLY. Example: [[SEARCH_WEB: news today]]
2. NEVER say "Awaiting observation" or "Waiting for system". Just output the tag.
3. Once you get the Observation, provide your final response to the user.
4. To remember something durable, include [SAVE_FACT: short fact] in a normal reply.
"""


def require_api_key() -> str:
    if not API_KEY:
        raise RuntimeError(
            "GROQ_API_KEY is not set. Copy .env.example to .env and add your key."
        )
    return API_KEY


class ZeusAgent:
    def __init__(self, client: Groq | None = None):
        self.memory = load_json(MEMORY_PATH, default_memory())
        if "facts" not in self.memory:
            self.memory["facts"] = []
        history = load_json(HISTORY_PATH, [])
        self.messages = [{"role": "system", "content": build_prompt(self.memory)}]
        for msg in history[-10:]:
            if isinstance(msg, dict) and msg.get("role") in ("user", "assistant"):
                self.messages.append(msg)
        self.client = client or Groq(api_key=require_api_key())

    def _complete(self) -> str:
        completion = self.client.chat.completions.create(
            model=MODEL_ID, messages=self.messages
        )
        return (completion.choices[0].message.content or "").strip()

    def _persist(self) -> None:
        transcript = [m for m in self.messages if m["role"] != "system"][-HISTORY_LIMIT:]
        save_json(HISTORY_PATH, transcript)
        save_json(MEMORY_PATH, self.memory)

    def _maybe_save_fact(self, response: str) -> str:
        match = FACT_RE.search(response)
        if not match:
            return response
        fact = match.group(1).strip()
        if fact and fact not in self.memory["facts"]:
            self.memory["facts"].append(fact)
        return FACT_RE.sub("", response).strip()

    def _run_tool(self, name: str, arg: str | None) -> str:
        fn = TOOLS[name]
        if arg:
            return fn(arg)
        return fn()

    def run_turn(self, user_text: str, on_tool: Callable[[str], None] | None = None) -> str:
        self.messages.append({"role": "user", "content": user_text})
        response = self._complete()
        match = TOOL_RE.search(response)

        if match:
            tool_name = match.group(1)
            tool_arg = match.group(2).strip() if match.group(2) else None
            if tool_name in TOOLS:
                if on_tool:
                    on_tool(tool_name)
                observation = self._run_tool(tool_name, tool_arg)
                self.messages.append({"role": "assistant", "content": response})
                self.messages.append(
                    {"role": "user", "content": f"SYSTEM OBSERVATION: {observation}"}
                )
                final = self._maybe_save_fact(self._complete())
                self.messages.append({"role": "assistant", "content": final})
                self._persist()
                return final

        clean = self._maybe_save_fact(response)
        self.messages.append({"role": "assistant", "content": response})
        self._persist()
        return clean
