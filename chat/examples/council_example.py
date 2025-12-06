import requests
from dotenv import load_dotenv
import os
import sys
from chat.config import COUNCIL_MEMBERS

load_dotenv()

HF_TOKEN = os.getenv("HF_TOKEN")
API_URL = os.getenv("API_URL")

headers = {
    "Authorization": f"Bearer {HF_TOKEN}",
    "Content-Type": "application/json"
}


def query(payload):
    try:
        response = requests.post(API_URL, headers=headers, json=payload)
        response.raise_for_status() # Raise error for bad status codes (4xx, 5xx)
        return response.json()
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}

def convene_council(user_prompt):
    print(f"\n🏛️  THE COUNCIL IS CONVENING")
    print(f"❓  Question: {user_prompt}\n")
    print("="*60)

    for model_id in COUNCIL_MEMBERS:
        print(f"👉  Asking: {model_id}...")
        
        response = query({
            "messages": [
                {
                    "role": "user",
                    "content": user_prompt
                }
            ],
            "model": model_id,
            "max_tokens": 100,
            "stream": False
        })

        # Check if we got a valid response or an error
        try:
            if "choices" in response:
                answer = response["choices"][0]["message"]["content"]
                print(f"\n💬  {model_id} SAYS:\n")
                print(answer.strip())
            else:
                print(f"\n⚠️  ERROR with {model_id}:")
                print(response)
        except Exception as e:
            print(f"\n❌ EXCEPTION while processing response from {model_id}: {e}")

        print("\n" + "-"*60 + "\n")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        # Get question from command line arguments
        question = " ".join(sys.argv[1:])
    else:
        # Prompt for input if no arguments provided
        question = input("Enter your question for the council: ")
    
    convene_council(question)