import sys

from groq import Groq

from config import API_KEY, MODEL_ID


def main() -> None:
    if not API_KEY:
        print("GROQ_API_KEY is not set. Copy .env.example to .env and add your key.")
        sys.exit(1)

    client = Groq(api_key=API_KEY)
    print(f"Configured model: {MODEL_ID}")
    try:
        models = client.models.list()
        print("--- AVAILABLE MODELS ---")
        for model in models.data:
            print(f"-> {model.id}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
