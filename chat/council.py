# chat/council.py
# Core council logic - adapted from your original backend

import requests
import os
from dotenv import load_dotenv

load_dotenv()

HF_TOKEN = os.getenv("HF_TOKEN")
if not HF_TOKEN:
    print(
        "⚠️  WARNING: HF_TOKEN is not set. API calls to Hugging Face will likely fail (401 Unauthorized)."
    )
    print("   Please create a .env file with HF_TOKEN=your_token_here")

API_URL = os.getenv("API_URL", "https://router.huggingface.co/v1/chat/completions")

headers = {"Authorization": f"Bearer {HF_TOKEN}", "Content-Type": "application/json"}


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
        "temperature": 0.7,
    }

    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=30)

        # Log the response status
        print(f"🔍 {model_id} - Status: {response.status_code}")

        if response.status_code != 200:
            error_text = response.text[:500]  # First 500 chars of error
            print(f"❌ {model_id} failed with {response.status_code}: {error_text}")
            return None

        response.raise_for_status()
        data = response.json()

        if "choices" in data:
            content = data["choices"][0]["message"]["content"].strip()
            preview = content[:150] + "..." if len(content) > 150 else content
            print(f"✅ {model_id} responded successfully")
            print(f"   📄 Response preview: {preview}")
            return content
        else:
            print(f"⚠️  Unexpected format from {model_id}: {data}")
            return None
    except requests.exceptions.Timeout:
        print(f"⏱️  Timeout querying {model_id} after 30 seconds")
        return None
    except requests.exceptions.RequestException as e:
        print(f"❌ Network error querying {model_id}: {e}")
        if hasattr(e, "response") and e.response is not None:
            print(f"   Response body: {e.response.text[:500]}")
        return None
    except Exception as e:
        print(f"❌ Unexpected error querying {model_id}: {type(e).__name__}: {e}")
        return None


def get_round_answers(question, active_members, round_num, previous_answers=None):
    """
    Queries all active members.
    If Round 2+, includes context of previous answers for re-evaluation.
    """
    print(
        f"\n📝 Round {round_num}: Collecting answers from {len(active_members)} members"
    )
    print(f"   Active members: {', '.join(active_members)}")
    current_answers = {}

    for idx, member in enumerate(active_members, 1):
        print(f"\n   [{idx}/{len(active_members)}] Querying {member}...")
        if round_num == 1:
            messages = [{"role": "user", "content": question}]
        else:
            prev_response = previous_answers.get(member, "No previous answer.")
            messages = [
                {"role": "user", "content": question},
                {"role": "assistant", "content": prev_response},
                {
                    "role": "user",
                    "content": (
                        "Review your previous answer. Consider that other models might have "
                        "offered different perspectives. Refine your answer to be more accurate and concise."
                    ),
                },
            ]

        response = query_llm(member, messages)
        if response:
            current_answers[member] = response
            answer_preview = response[:200] + "..." if len(response) > 200 else response
            print(f"   ✅ Got answer from {member}:")
            print(f"      {answer_preview}")
        else:
            current_answers[member] = "Failed to generate answer."
            print(f"   ❌ Failed to get answer from {member}")

    print(
        f"\n✅ Round {round_num} complete: "
        f"{len([a for a in current_answers.values() if a != 'Failed to generate answer.'])}/"
        f"{len(active_members)} successful answers"
    )
    return current_answers


def collect_votes(question, answers):
    """
    Each model sees all answers (anonymized) and votes for the WORST one.
    Returns: (votes_summary, model_map, detailed_votes)
    """
    print(f"\n🗳️  Starting voting phase with {len(answers)} members")
    votes_summary = []
    detailed_votes = {}  # {voter_id: vote_response}

    # Format answers for the prompt
    candidates_text = ""
    model_map = list(answers.keys())

    for idx, model_id in enumerate(model_map):
        candidates_text += f"Answer #{idx+1}: {answers[model_id]}\n---\n"

    voting_prompt = (
        f"Question: {question}\n\n"
        f"Here are the proposed answers:\n{candidates_text}\n"
        f"Task: Identify the WORST answer. "
        f"Explain briefly why, and end your response with 'VOTE: Answer #X' where X is the number."
    )

    for idx, voter in enumerate(answers.keys(), 1):
        print(f"\n   [{idx}/{len(answers)}] {voter} is voting...")
        vote_response = query_llm(
            voter, [{"role": "user", "content": voting_prompt}], max_tokens=100
        )
        if vote_response:
            votes_summary.append(f"{voter} voted: {vote_response}")
            detailed_votes[voter] = vote_response
            print(f"   ✅ {voter} voted:")
            print(f"      {vote_response}")
        else:
            detailed_votes[voter] = "Failed to vote"
            print(f"   ❌ {voter} failed to vote")

    print(
        f"\n✅ Voting complete: "
        f"{len([v for v in detailed_votes.values() if v != 'Failed to vote'])}/"
        f"{len(answers)} successful votes"
    )
    return votes_summary, model_map, detailed_votes


def arbiter_eliminate(question, answers, votes, model_map):
    """
    The Arbiter looks at answers and votes, then kills one model.
    Returns: (eliminated_model, reasoning)
    """
    from chat.config import ARBITER_MODEL

    print(f"\n⚖️  Arbiter ({ARBITER_MODEL}) is deliberating...")

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
        "First explain your reasoning in 1-2 sentences, then end with 'ELIMINATE: [exact Model ID]' on a new line."
    )

    decision = query_llm(
        ARBITER_MODEL, [{"role": "user", "content": arbiter_prompt}], max_tokens=150
    )

    # Parse the decision
    eliminated = None
    reasoning = decision if decision else "Failed to get arbiter decision"

    if decision:
        print("\n   📜 Arbiter's full decision:")
        print(f"      {decision}")
        # Try to extract the model ID
        for model_id in answers.keys():
            if model_id in decision:
                eliminated = model_id
                print(f"\n   🎯 Parsed elimination target: {eliminated}")
                break

    if not eliminated:
        # Fallback if arbiter fails
        eliminated = list(answers.keys())[-1]
        reasoning = f"Arbiter failed to decide. Fallback elimination: {eliminated}"
        print(f"\n   ⚠️  Could not parse decision, using fallback: {eliminated}")

    print(f"\n💀 ELIMINATED: {eliminated}")
    return eliminated, reasoning


def ensemble_result(
    question, final_answers, eliminated_answers=None, synthesizer_id=None
):
    """
    Combines the final answer (survivor) and eliminated answers into one cohesive response.
    synthesizer_id: The model ID of the survivor who will generate the final answer.
    """
    from chat.config import ARBITER_MODEL

    # Use synthesizer_id if provided, else default to Arbiter
    target_model = synthesizer_id if synthesizer_id else ARBITER_MODEL

    print(f"\n🎼 Creating final ensemble with {target_model}...")

    combined_text = ""
    # Survivor's answer
    for model, ans in final_answers.items():
        combined_text += f"SURVIVOR ({model}):\n{ans}\n\n"

    # Eliminated answers
    if eliminated_answers:
        combined_text += "PREVIOUS PERSPECTIVES (ELIMINATED):\n"
        for model, ans in eliminated_answers.items():
            combined_text += f"From {model}:\n{ans}\n\n"

    if target_model == ARBITER_MODEL:
        task_prompt = (
            "Task: You are the Council Arbiter. "
            "Synthesize these perspectives into one perfect, comprehensive, and accurate master answer."
        )
    else:
        task_prompt = (
            "Task: You are the sole survivor of the Council. "
            "Synthesize your own winning answer along with valid points from the eliminated models into one perfect, "
            "comprehensive, and accurate master answer."
        )

    ensemble_prompt = (
        f"User Question: {question}\n\n"
        f"Here are the perspectives:\n{combined_text}\n"
        f"{task_prompt}"
    )

    print(f"\n   Synthesizing with {target_model}...")
    final_output = query_llm(
        target_model, [{"role": "user", "content": ensemble_prompt}], max_tokens=500
    )

    if final_output:
        print(f"\n✨ Final answer generated successfully ({len(final_output)} chars)")
    else:
        print("\n❌ Failed to generate final answer")

    return final_output
