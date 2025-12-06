import requests
import os
import sys
import json
from dotenv import load_dotenv

from chat.config import COUNCIL_MEMBERS, ARBITER_MODEL


load_dotenv()

HF_TOKEN = os.getenv("HF_TOKEN")
API_URL = os.getenv("API_URL")
# We select the first member or a specific high-quality model to act as the Judge/Arbiter

headers = {
    "Authorization": f"Bearer {HF_TOKEN}",
    "Content-Type": "application/json"
}

# --- CORE API FUNCTION ---

def query_llm(model_id, messages, max_tokens=200):
    """
    Generic wrapper to send messages to the Inference API.
    Returns the content string or None if failed.
    """
    payload = {
        "model": model_id,
        "messages": messages,
        "max_tokens": max_tokens,
        "stream": False,
        "temperature": 0.7
    }
    
    try:
        response = requests.post(API_URL, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        
        if "choices" in data:
            return data["choices"][0]["message"]["content"].strip()
        else:
            print(f"⚠️  Unexpected format from {model_id}: {data}")
            return None
    except Exception as e:
        print(f"❌ Error querying {model_id}: {e}")
        return None

# --- STAGE 1: GET ANSWERS ---

def get_round_answers(question, active_members, round_num, previous_answers=None, previous_votes=None, eliminated_model=None):
    """
    Queries all active members. 
    If Round 2, includes context of ALL previous answers (including eliminated) ordered by votes.
    """
    print(f"\n📝  Collecting Answers (Round {round_num})...")
    current_answers = {}

    for member in active_members:
        print(f"   -> Asking {member}...")
        
        if round_num == 1:
            messages = [{"role": "user", "content": question}]
        else:
            # Round 2: Show ALL answers from R1, ordered by votes (worst first)
            prev_response = previous_answers.get(member, "No previous answer.")
            
            # Build context showing all R1 answers ordered by votes
            all_answers_text = "Here are ALL answers from Round 1 (ordered from worst to best based on voting):\n\n"
            
            # Count votes for each model
            vote_counts = {}
            for model_id in previous_answers.keys():
                vote_counts[model_id] = 0
            
            # Parse votes to count which models were voted as worst
            for vote in previous_votes:
                for model_id in previous_answers.keys():
                    if model_id in vote:
                        vote_counts[model_id] += 1
            
            # Sort by vote count (most votes = worst)
            sorted_models = sorted(vote_counts.items(), key=lambda x: x[1], reverse=True)
            
            for model_id, count in sorted_models:
                status = " (ELIMINATED)" if model_id == eliminated_model else ""
                all_answers_text += f"Model '{model_id}'{status} (received {count} votes as worst):\n{previous_answers[model_id]}\n\n"
            
            messages = [
                {"role": "user", "content": question},
                {"role": "assistant", "content": prev_response},
                {"role": "user", "content": f"{all_answers_text}Your previous answer is included above. Now, review ALL the answers, especially noting which one was eliminated. Refine your answer to be more accurate and concise, learning from the mistakes you see."}
            ]

        response = query_llm(member, messages)
        if response:
            current_answers[member] = response
            print(f"   ✅ Answer from {member}:\n   {response[:500]}..." if len(response) > 500 else f"   ✅ Answer from {member}:\n   {response}")
            print("-" * 30)
        else:
            current_answers[member] = "Failed to generate answer."
            
    return current_answers

# --- STAGE 2: PEER VOTING ---

def collect_votes(question, answers):
    """
    Each model sees all answers (anonymized) and votes for the WORST one.
    """
    print(f"\n🗳️   Council Voting on the WORST answer...")
    votes = [] # List of strings containing the reasoning and vote

    # Format answers for the prompt
    candidates_text = ""
    model_map = list(answers.keys()) # Map index to model_id
    
    for idx, model_id in enumerate(model_map):
        candidates_text += f"Answer #{idx+1}: {answers[model_id]}\n---\n"

    voting_prompt = (
        f"Question: {question}\n\n"
        f"Here are the proposed answers:\n{candidates_text}\n"
        f"Task: Identify the WORST answer. "
        f"Explain briefly why, and end your response with 'VOTE: Answer #X' where X is the number."
    )

    for voter in answers.keys():
        vote_response = query_llm(voter, [{"role": "user", "content": voting_prompt}], max_tokens=50)
        if vote_response:
            votes.append(f"{voter} voted: {vote_response}")
            print(f"   -> {voter} cast their vote: {vote_response}")
            print("-" * 20)
    
    return votes, model_map

# --- STAGE 3: ARBITER ELIMINATION ---

def arbiter_eliminate(question, answers, votes, model_map):
    """
    The Arbiter looks at answers and votes, then kills one model.
    """
    print(f"\n⚖️   The Arbiter ({ARBITER_MODEL}) is deciding who to eliminate...")
    
    # Format data for Arbiter
    context = f"Question: {question}\n\n"
    for idx, model_id in enumerate(model_map):
        context += f"Model ID '{model_id}' (Answer #{idx+1}): {answers[model_id]}\n"
    
    context += "\nVOICE OF THE COUNCIL (Votes):\n"
    for v in votes:
        context += f"- {v}\n"

    arbiter_prompt = (
        f"{context}\n\n"
        "You are the Grand Arbiter. Based on the answers and the peer votes, identify the single worst model. "
        "Return ONLY the exact Model ID of the model to eliminate. Do not write sentences, just the ID."
    )

    decision = query_llm(ARBITER_MODEL, [{"role": "user", "content": arbiter_prompt}], max_tokens=20)
    
    # Clean up decision to ensure it matches a key
    eliminated = None
    if decision:
        for model_id in answers.keys():
            if model_id in decision:
                eliminated = model_id
                break
    
    if not eliminated:
        # Fallback if arbiter fails: Eliminate the last one in list (simple fail-safe)
        eliminated = list(answers.keys())[-1]
        print("   (Arbiter response unclear, using fallback elimination)")

    print(f"💀  ELIMINATED: {eliminated}")
    return eliminated

# --- STAGE 4: FINAL ENSEMBLE ---

def ensemble_result(question, final_answers):
    """
    Combines the final 3 answers into one cohesive response.
    """
    print(f"\n🎼  Creating Final Ensemble...")
    
    combined_text = ""
    for model, ans in final_answers.items():
        combined_text += f"Perspective from {model}:\n{ans}\n\n"

    ensemble_prompt = (
        f"User Question: {question}\n\n"
        f"Here are the answers from the top 3 AI models:\n{combined_text}\n"
        f"Task: Synthesize these 3 answers into one perfect, comprehensive, and accurate master answer."
    )

    final_output = query_llm(ARBITER_MODEL, [{"role": "user", "content": ensemble_prompt}], max_tokens=500)
    return final_output

# --- MAIN CONTROLLER ---

def convene_council(user_prompt):
    print(f"\n🏛️  THE COUNCIL IS CONVENING")
    print(f"❓  Question: {user_prompt}")
    print("="*60)

    active_members = COUNCIL_MEMBERS.copy()
    if len(active_members) > 5: active_members = active_members[:5] # Ensure max 5 start
    
    # --- ROUND 1 ---
    print("\n--- 🔔 ROUND 1 ---")
    # Answer- >  vote -> arbiter eliminates
    answers_r1 = get_round_answers(user_prompt, active_members, 1)
    votes_r1, map_r1 = collect_votes(user_prompt, answers_r1)
    loser_r1 = arbiter_eliminate(user_prompt, answers_r1, votes_r1, map_r1)
    
    # we drop the loser
    if loser_r1 in active_members:
        active_members.remove(loser_r1)

    # --- ROUND 2 ---
    print("\n--- 🔔 ROUND 2 (Re-evaluation) ---")
    # we repeat, but now models see ALL R1 answers including the eliminated one
    answers_r2 = get_round_answers(user_prompt, active_members, 2, previous_answers=answers_r1, previous_votes=votes_r1, eliminated_model=loser_r1)
    votes_r2, map_r2 = collect_votes(user_prompt, answers_r2)
    loser_r2 = arbiter_eliminate(user_prompt, answers_r2, votes_r2, map_r2)

    if loser_r2 in active_members:
        active_members.remove(loser_r2)

    # --- FINAL ENSEMBLE ---
    print("\n--- 🏁 FINAL DELIBERATION ---")
    print(f"Top 3 Survivors: {active_members}")
    
    # Get fresh final answers from survivors (or use R2 answers)
    final_responses = {k:v for k,v in answers_r2.items() if k in active_members}
    
    master_answer = ensemble_result(user_prompt, final_responses)

    print("\n" + "="*60)
    print("🌟  THE COUNCIL HAS SPOKEN:")
    print("="*60 + "\n")
    print(master_answer)
    print("\n" + "="*60)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        question = " ".join(sys.argv[1:])
    else:
        question = input("Enter your question for the council: ")
    
    convene_council(question)