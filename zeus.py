from groq import Groq

# 1. SETUP
# Make sure your API key is correct here
client = Groq(api_key="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")

# 2. PERSONALITY (The Core Instructions)
ZEUS_PROMPT = """
You are ZEUS (Zero Effort Universal Sidekick). 
You are a sharp, modular, and highly intelligent digital companion. 
It is August 2026. You are the brain of a centralized assistant system.
"""

# 3. MEMORY (Short-term conversation history)
messages = [
    {"role": "system", "content": ZEUS_PROMPT}
]

def main():
    print("--- ZEUS SYSTEM ONLINE (2026 GPT-OSS ENGINE) ---")
    print("(Type 'exit' to shut down)")

    # Choosing the most powerful model from your list
    MODEL_ID = "openai/gpt-oss-120b"

    while True:
        user_input = input("\nYou: ")
        
        if user_input.lower() in ["exit", "quit"]:
            print("ZEUS: Shutting down. Systems offline.")
            break

        # Add your message to the history
        messages.append({"role": "user", "content": user_input})

        try:
            # Generate the response
            completion = client.chat.completions.create(
                model=MODEL_ID,
                messages=messages,
            )

            zeus_response = completion.choices[0].message.content
            
            print(f"\nZEUS: {zeus_response}")

            # Add ZEUS's response to memory
            messages.append({"role": "assistant", "content": zeus_response})

        except Exception as e:
            # If the 120b model is too busy, try the 'groq/compound' model as a backup
            print(f"\n[SYSTEM ERROR]: {e}")
            print("Tip: If you see a 'Rate Limit' error, we can switch to 'groq/compound'.")

if __name__ == "__main__":
    main()