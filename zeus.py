from agent import ZeusAgent, require_api_key

def main() -> None:
    require_api_key()
    agent = ZeusAgent()
    print("--- ZEUS CORE v0.3.5 ONLINE ---")
    print("Type 'exit' or 'quit' to leave. Type 'reset' to clear history.")

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
            
        if not user_input: continue
        
        if user_input.lower() == "reset":
            agent.reset_memory() # Ensure your agent has this method
            print("--- [SYSTEM: Memory purged.] ---")
            continue
            
        if user_input.lower() in {"exit", "quit"}: break

        # TOKEN SAVER
        if len(agent.messages) > 7:
            agent.messages = [agent.messages[0]] + agent.messages[-6:]

        try:
            # The agent.run_turn now needs to be 'Tool Aware'
            reply = agent.run_turn(user_input)
            print(f"\nZEUS: {reply}")
        except Exception as e:
            print(f"[SYSTEM ERROR]: {e}")

if __name__ == "__main__":
    main()