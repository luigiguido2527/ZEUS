from groq import Groq

client = Groq(api_key="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")

try:
    models = client.models.list()
    print("--- AVAILABLE MODELS ---")
    for model in models.data:
        print(f"-> {model.id}")
except Exception as e:
    print(f"Error: {e}")