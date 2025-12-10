# Council Logic Flow

The core of the application lies in the `convene` function in `app.py` and the helper functions in `chat/council.py`. Here is the step-by-step lifecycle of a user query:

## 1. Convene (Initialization)
-   **Trigger**: User sends a POST request to `/api/convene` with a `question`.
-   **State**: The server initializes `active_members` from the config and sets `round_num = 1`.

## 2. The Round Loop
The process enters a `while` loop that continues as long as there are more than 2 survivors (or until a specific condition is met).

### Phase A: Answering / Refinement
-   **Action**: Every active member is queried.
-   **Context**:
    -   **Round 1**: Models see only the user question.
    -   **Round 2+**: Models see the user question, their *previous* answer, and a prompt to "Refine your answer" considering others might have different perspectives.
-   **Output**: A map of `{member_id: answer_text}`.

### Phase B: Voting (Peer Review)
-   **Action**: Each member is shown *all* current answers (anonymized or with IDs) and asked to identify the **worst** answer.
-   **Output**: A collection of votes and reasoning from each member.

### Phase C: Arbiter Decision
-   **Role**: The "Arbiter" (a powerful model defined in config, e.g., `google/gemma-3-27b-it`) acts as the judge.
-   **Input**: The Arbiter receives:
    1.  The original question.
    2.  All current answers.
    3.  The votes from the council members ("Voice of the Council").
-   **Task**: "Identify the single worst model."
-   **Output**: The ID of the eliminated model and a reason.

### Phase D: Elimination
-   The eliminated model is removed from `active_members`.
-   Their last answer is archived in `eliminated_answers` for future reference (to preserve unique insights).

## 3. The Endgame (Ensemble)
-   **Trigger**: When only 1 member remains (or 2, depending on the stop condition).
-   **Synthesizer**: The survivor (or the Arbiter if multiple survive) is tasked with creating the final answer.
-   **Prompt**: "Synthesize your own winning answer along with valid points from the eliminated models into one perfect, comprehensive, and accurate master answer."
-   **Result**: The final "Master Answer" is streamed to the user.

