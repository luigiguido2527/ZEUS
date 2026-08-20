import json
import os
import re
from groq import Groq
from tools import system_tools, research_tools

# --- 1. PERSISTENCE ---
def load_json(filename, default):
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
                return json.load(f)
        except: return default
    return default

def save_json(filename, data):
    with open(filename, "w") as f:
        json.dump(data, f, indent=4)

memory_data = load_json("zeus_memory.json", {"user_name": "User", "facts": []})
chat_history = load_json("zeus_history.json", [])

# --- 2. REGISTRY ---
TOOLS = {
    "GET_TIME": system_tools.get_time,
    "GET_SYSTEM_STATUS": system_tools.get_system_status,
    "LIST_FILES": system_tools.list_files,
    "READ_FILE": system_tools.read_file,
    "SEARCH_WEB": research_tools.search_web
}

# --- 3. THE OG BRAIN ---
client = Groq(api_key="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")
MODEL_ID = "openai/gpt-oss-120b" 

ZEUS_PROMPT = f"""
You are ZEUS (Zero Effort Universal Sidekick). 
User: {memory_data.get('user_name')} | Context: {memory_data.get('facts')}

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
"""

messages = [{"role": "system", "content": ZEUS_PROMPT}]
for msg in chat_history[-10:]:
    messages.append(msg)

def main():
    print(f"--- ZEUS CORE v0.3.5 ONLINE ---")
    
    while True:
        user_input = input("\nYou: ")
        if user_input.lower() in ["exit", "quit"]: break
        messages.append({"role": "user", "content": user_input})

        try:
            # PHASE 1: REASONING
            completion = client.chat.completions.create(model=MODEL_ID, messages=messages)
            response = completion.choices[0].message.content
            
            # PHASE 2: TOOL DETECTION
            match = re.search(r"\[\[\s*([A-Z_]+)(?::\s*(.*?))?\s*\]\]", response)
            
            if match:
                tool_name = match.group(1)
                tool_arg = match.group(2).strip() if match.group(2) else None
                
                if tool_name in TOOLS:
                    print(f"--- [AGENT ACTION: {tool_name}] ---")
                    
                    # Execute
                    observation = TOOLS[tool_name](tool_arg) if tool_arg else TOOLS[tool_name]()
                    print(f"--- [OBSERVATION: {observation[:100]}...] ---") # Print first 100 chars
                    
                    # Feed back to Brain
                    messages.append({"role": "assistant", "content": response})
                    messages.append({"role": "user", "content": f"SYSTEM OBSERVATION: {observation}"})
                    
                    # PHASE 3: FINAL RESPONSE
                    final_comp = client.chat.completions.create(model=MODEL_ID, messages=messages)
                    final_res = final_comp.choices[0].message.content
                    print(f"\nZEUS: {final_res}")
                    messages.append({"role": "assistant", "content": final_res})
                else:
                    print(f"\nZEUS: {response}")
            else:
                # Normal chat and fact saving
                clean_response = response
                fact_match = re.search(r"\[SAVE_FACT:\s*(.*?)\]", response)
                if fact_match:
                    new_fact = fact_match.group(1)
                    if new_fact not in memory_data["facts"]:
                        memory_data["facts"].append(new_fact)
                        save_json("zeus_memory.json", memory_data)
                        print(f"--- [SYSTEM: Memory Updated] ---")
                    clean_response = response.replace(fact_match.group(0), "")
                
                print(f"\nZEUS: {clean_response.strip()}")
                messages.append({"role": "assistant", "content": response})

            # Save History
            save_json("zeus_history.json", [m for m in messages if m["role"] != "system"][-20:])

        except Exception as e:
            print(f"[SYSTEM ERROR]: {e}")

if __name__ == "__main__":
    main()