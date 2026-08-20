from agent import ZeusAgent, require_api_key


def main() -> None:
    require_api_key()
    agent = ZeusAgent()
    print("--- ZEUS CORE ONLINE ---")
    print("Type 'exit' or 'quit' to leave.")

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit"}:
            break
        try:
            reply = agent.run_turn(
                user_input,
                on_tool=lambda name: print(f"--- [AGENT ACTION: {name}] ---"),
            )
            print(f"\nZEUS: {reply}")
        except Exception as e:
            print(f"[SYSTEM ERROR]: {e}")


if __name__ == "__main__":
    main()
