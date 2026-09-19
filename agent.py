import re
from collections.abc import Callable

from openai import OpenAI

from config import (
    API_KEY,
    HISTORY_LIMIT,
    HISTORY_PATH,
    MEMORY_PATH,
    MODEL_ID,
    OPENROUTER_API_KEY,
    OPENROUTER_APP_TITLE,
    OPENROUTER_BASE_URL,
    OPENROUTER_HTTP_REFERER,
    OPENROUTER_MAX_TOKENS,
    OPENROUTER_MODEL,
)
from memory import default_memory, load_json, save_json
from tools import TOOLS

TOOL_RE = re.compile(r"\[\[\s*([A-Z0-9_]+)(?:\s*:\s*(.*?))?\s*\]\]", re.DOTALL)
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
- READ_FILE supports TXT, Word (.docx), PDF, Excel (.xlsx/.xlsm), and PowerPoint (.pptx).
- [[SEARCH_WEB: query]]

[CRITICAL INSTRUCTIONS]
1. If you need information, use a tool tag like [[SEARCH_WEB: AI trends]].
2. Never narrate waiting states. Output the tool tag directly when you need a tool.
3. Once you get the observation, provide a final response to the user.
4. To remember something durable, include [SAVE_FACT: short fact] in a normal reply.
5. The system can chain tools sequentially when more than one capability is needed.
"""


def require_api_key() -> str:
    key = OPENROUTER_API_KEY or API_KEY
    if not key:
        raise RuntimeError(
            "OPENROUTER_API_KEY is not set. Copy .env.example to .env and add your key."
        )
    return key


class ZeusAgent:
    def __init__(self, client: OpenAI | None = None):
        self.memory = load_json(MEMORY_PATH, default_memory())
        if "facts" not in self.memory:
            self.memory["facts"] = []
        history = load_json(HISTORY_PATH, [])
        self.messages = [{"role": "system", "content": build_prompt(self.memory)}]
        for msg in history[-10:]:
            if isinstance(msg, dict) and msg.get("role") in ("user", "assistant"):
                self.messages.append(msg)

        self.model = OPENROUTER_MODEL or MODEL_ID
        self.client = client or OpenAI(
            api_key=require_api_key(),
            base_url=OPENROUTER_BASE_URL,
            default_headers={
                "HTTP-Referer": OPENROUTER_HTTP_REFERER,
                "X-Title": OPENROUTER_APP_TITLE,
            },
        )

    def _extract_tool_names(self, text: str) -> list[str]:
        return [match.group(1) for match in TOOL_RE.finditer(text) if match.group(1)]

    @staticmethod
    def render_markdown_table(table_text: str) -> str:
        lines = [line.strip() for line in table_text.splitlines() if line.strip() and "|" in line]
        if len(lines) < 3:
            return f'<div class="message-html"><p>{table_text}</p></div>'

        rows = [[cell.strip() for cell in line.strip().strip("|").split("|")] for line in lines]
        header = rows[0]
        body_rows = rows[2:] if len(rows) > 2 else []

        result = ['<div class="message-html"><table class="electric-cyan">', "<thead><tr>"]
        for cell in header:
            result.append(f"<th>{cell}</th>")
        result.append("</tr></thead><tbody>")

        for row in body_rows:
            result.append("<tr>")
            for cell in row:
                result.append(f"<td>{cell}</td>")
            result.append("</tr>")
        result.append("</tbody></table></div>")
        return "".join(result)

    def _complete(self) -> str:
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=self.messages,
            temperature=0.6,
            max_tokens=OPENROUTER_MAX_TOKENS,
        )
        content = completion.choices[0].message.content or ""
        return content.strip()

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
        fn = TOOLS.get(name)
        if fn is None:
            return f"Tool '{name}' is unavailable."
        if arg:
            return fn(arg)
        return fn()

    def run_turn(
        self,
        user_text: str,
        on_tool: Callable[[str], None] | None = None,
        approve_tool: Callable[[str, str | None], bool] | None = None,
        image_data: str | None = None,
        file_data: str | None = None,
    ) -> str:
        attached_text = ""
        if file_data:
            attached_text = (
                "\n\n[ATTACHED FILE CONTENT]\n"
                f"{file_data}\n"
                "[END ATTACHED FILE CONTENT]"
            )
        content = user_text + attached_text
        if image_data:
            content = [
                {"type": "text", "text": content},
                {"type": "image_url", "image_url": {"url": image_data}},
            ]
        self.messages.append({"role": "user", "content": content})
        response = self._complete()
        tool_matches = list(TOOL_RE.finditer(response))
        tool_names = [match.group(1) for match in tool_matches]

        if tool_names:
            observations = []
            for match in tool_matches:
                tool_name = match.group(1)
                if tool_name not in TOOLS:
                    continue
                if on_tool:
                    on_tool(tool_name)
                tool_arg = match.group(2).strip() if match.group(2) else None
                if approve_tool and not approve_tool(tool_name, tool_arg):
                    observations.append(f"[{tool_name}] Tool action cancelled by user.")
                    continue
                observation = self._run_tool(tool_name, tool_arg)
                observations.append(f"[{tool_name}] {observation}")

            self.messages.append({"role": "assistant", "content": response})
            self.messages.append({"role": "user", "content": "SYSTEM OBSERVATION: " + "\n".join(observations)})
            final = self._maybe_save_fact(self._complete())
            self.messages.append({"role": "assistant", "content": final})
            self._persist()
            return final

        clean = self._maybe_save_fact(response)
        self.messages.append({"role": "assistant", "content": clean})
        self._persist()
        return clean
