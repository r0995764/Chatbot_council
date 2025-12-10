"""
LLM Council - Flask Server
Serves the frontend and provides API/SSE endpoints for the council deliberation.
"""

import time
import json
from flask import Flask, render_template, request, Response, stream_with_context
from chat.council import query_llm, collect_votes, arbiter_eliminate, ensemble_result
from chat.config import COUNCIL_MEMBERS, ARBITER_MODEL

app = Flask(__name__)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/config")
def get_config():
    """Return council configuration."""
    return {"members": COUNCIL_MEMBERS, "arbiter": ARBITER_MODEL}


@app.route("/api/convene", methods=["POST"])
def convene():
    """
    Stream the council deliberation as Server-Sent Events.
    Each event is a JSON object describing what's happening.
    """
    data = request.json
    question = data.get("question", "")

    if not question:
        return {"error": "No question provided"}, 400

    def generate():
        active_members = COUNCIL_MEMBERS.copy()
        eliminated_answers = {}
        last_answers = {}
        round_num = 1

        # Start
        yield sse_event("start", {"question": question, "members": active_members})
        time.sleep(0.5)

        while len(active_members) > 1:
            # --- ROUND START ---
            yield sse_event(
                "round_start", {"round": round_num, "survivors": active_members}
            )
            time.sleep(0.3)

            # Phase: Answering / Re-evaluating
            phase_name = "answering" if round_num == 1 else "re-evaluating"
            yield sse_event("phase", {"phase": phase_name, "round": round_num})

            current_answers = {}
            for member in active_members:
                yield sse_event("member_thinking", {"member": member})

                if round_num == 1:
                    messages = [{"role": "user", "content": question}]
                else:
                    prev = last_answers.get(member, "No previous answer.")
                    messages = [
                        {"role": "user", "content": question},
                        {"role": "assistant", "content": prev},
                        {
                            "role": "user",
                            "content": (
                                "Review your previous answer. "
                                "Consider that other models might have offered different perspectives. "
                                "Refine your answer to be more accurate and concise."
                            ),
                        },
                    ]

                response = query_llm(member, messages)
                answer_text = response or "Failed to generate answer."
                current_answers[member] = answer_text

                yield sse_event(
                    "member_answered", {"member": member, "answer": answer_text}
                )
                time.sleep(0.2)

            # Store answers for next round context
            last_answers = current_answers.copy()

            # Special case: If only 2 members remain, skip voting/elimination
            # The Arbiter will synthesize the final result from here.
            if len(active_members) == 2:
                break

            # Phase: Voting
            yield sse_event("phase", {"phase": "voting", "round": round_num})
            votes, map_data, detailed_votes = collect_votes(question, current_answers)

            # Send individual votes
            for voter, vote_text in detailed_votes.items():
                yield sse_event("member_voted", {"member": voter, "vote": vote_text})
                time.sleep(0.2)

            yield sse_event("votes_collected", {"votes": votes})
            time.sleep(0.5)

            # Phase: Arbiter Elimination
            yield sse_event("phase", {"phase": "arbiter", "round": round_num})
            yield sse_event("arbiter_thinking", {})
            time.sleep(0.5)

            loser, reasoning = arbiter_eliminate(
                question, current_answers, votes, map_data
            )
            yield sse_event(
                "arbiter_decision", {"reasoning": reasoning, "round": round_num}
            )
            time.sleep(0.5)
            yield sse_event("elimination", {"eliminated": loser, "round": round_num})

            # Handle elimination
            if loser in active_members:
                # Archive the loser's last perspective
                eliminated_answers[loser] = current_answers[loser]
                active_members.remove(loser)

            time.sleep(1)
            round_num += 1

        # --- FINAL ---
        # The survivor synthesizes
        yield sse_event("phase", {"phase": "ensemble", "survivors": active_members})

        final_answers = {m: last_answers.get(m, "") for m in active_members}

        # Determine synthesizer: Survivor if 1 left, otherwise Arbiter
        if len(active_members) == 1:
            survivor = active_members[0]
            synthesizer = survivor
        else:
            survivor = None
            synthesizer = None  # Defaults to ARBITER_MODEL in ensemble_result

        # Call ensemble
        master_answer = ensemble_result(
            question,
            final_answers,
            eliminated_answers=eliminated_answers,
            synthesizer_id=synthesizer,
        )

        yield sse_event(
            "final_answer", {"answer": master_answer, "survivors": active_members}
        )
        yield sse_event("end", {})

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def sse_event(event_type, data):
    """Format a Server-Sent Event."""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


if __name__ == "__main__":
    app.run(debug=True, port=5000, threaded=True)
