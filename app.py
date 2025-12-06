"""
LLM Council - Flask Server
Serves the frontend and provides API/SSE endpoints for the council deliberation.
"""
import time
import json
from flask import Flask, render_template, request, Response, stream_with_context
from chat.council import query_llm, get_round_answers, collect_votes, arbiter_eliminate, ensemble_result
from chat.config import COUNCIL_MEMBERS, ARBITER_MODEL

app = Flask(__name__)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/config")
def get_config():
    """Return council configuration."""
    return {
        "members": COUNCIL_MEMBERS,
        "arbiter": ARBITER_MODEL
    }

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
        
        # Start
        yield sse_event("start", {"question": question, "members": active_members})
        time.sleep(0.5)
        
        # --- ROUND 1 ---
        yield sse_event("round_start", {"round": 1})
        time.sleep(0.3)
        
        # Collect answers
        yield sse_event("phase", {"phase": "answering", "round": 1})
        answers_r1 = {}
        for member in active_members:
            yield sse_event("member_thinking", {"member": member})
            response = query_llm(member, [{"role": "user", "content": question}])
            answers_r1[member] = response or "Failed to generate answer."
            yield sse_event("member_answered", {"member": member, "answer": answers_r1[member]})
            time.sleep(0.2)
        
        # Voting
        yield sse_event("phase", {"phase": "voting", "round": 1})
        votes_r1, map_r1, detailed_votes_r1 = collect_votes(question, answers_r1)

        # Send individual votes to show in speech bubbles
        for voter, vote_text in detailed_votes_r1.items():
            yield sse_event("member_voted", {"member": voter, "vote": vote_text})
            time.sleep(0.2)

        yield sse_event("votes_collected", {"votes": votes_r1})
        time.sleep(0.5)

        # Arbiter decides
        yield sse_event("phase", {"phase": "arbiter", "round": 1})
        yield sse_event("arbiter_thinking", {})
        time.sleep(0.5)
        loser_r1, reasoning_r1 = arbiter_eliminate(question, answers_r1, votes_r1, map_r1)
        yield sse_event("arbiter_decision", {"reasoning": reasoning_r1, "round": 1})
        time.sleep(0.5)
        yield sse_event("elimination", {"eliminated": loser_r1, "round": 1})
        
        if loser_r1 in active_members:
            active_members.remove(loser_r1)
        time.sleep(1)
        
        # --- ROUND 2 ---
        yield sse_event("round_start", {"round": 2, "survivors": active_members})
        time.sleep(0.3)
        
        yield sse_event("phase", {"phase": "re-evaluating", "round": 2})
        answers_r2 = {}
        for member in active_members:
            yield sse_event("member_thinking", {"member": member})
            prev = answers_r1.get(member, "No previous answer.")
            messages = [
                {"role": "user", "content": question},
                {"role": "assistant", "content": prev},
                {"role": "user", "content": "Review your previous answer. Refine it to be more accurate and concise."}
            ]
            response = query_llm(member, messages)
            answers_r2[member] = response or "Failed to generate answer."
            yield sse_event("member_answered", {"member": member, "answer": answers_r2[member]})
            time.sleep(0.2)
        
        # Voting round 2
        yield sse_event("phase", {"phase": "voting", "round": 2})
        votes_r2, map_r2, detailed_votes_r2 = collect_votes(question, answers_r2)

        # Send individual votes to show in speech bubbles
        for voter, vote_text in detailed_votes_r2.items():
            yield sse_event("member_voted", {"member": voter, "vote": vote_text})
            time.sleep(0.2)

        yield sse_event("votes_collected", {"votes": votes_r2})
        time.sleep(0.5)

        # Arbiter round 2
        yield sse_event("phase", {"phase": "arbiter", "round": 2})
        yield sse_event("arbiter_thinking", {})
        time.sleep(0.5)
        loser_r2, reasoning_r2 = arbiter_eliminate(question, answers_r2, votes_r2, map_r2)
        yield sse_event("arbiter_decision", {"reasoning": reasoning_r2, "round": 2})
        time.sleep(0.5)
        yield sse_event("elimination", {"eliminated": loser_r2, "round": 2})
        
        if loser_r2 in active_members:
            active_members.remove(loser_r2)
        time.sleep(1)
        
        # --- FINAL ---
        yield sse_event("phase", {"phase": "ensemble", "survivors": active_members})
        final_answers = {k: v for k, v in answers_r2.items() if k in active_members}
        
        master_answer = ensemble_result(question, final_answers)
        yield sse_event("final_answer", {"answer": master_answer, "survivors": active_members})
        
        yield sse_event("end", {})
    
    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )

def sse_event(event_type, data):
    """Format a Server-Sent Event."""
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"

if __name__ == "__main__":
    app.run(debug=True, port=5000, threaded=True)
