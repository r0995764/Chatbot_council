# LLM Council Overview

## What is this?
The **LLM Council** is a multi-agent debate system where a group of Large Language Models (LLMs) convene to answer a user's question. Instead of getting a single answer from one model, the "Council" engages in a process of:
1.  **Drafting Answers**: Each member proposes an answer.
2.  **Peer Review**: Members review each other's answers.
3.  **Voting**: Members vote on the "worst" answer in the current set.
4.  **Elimination**: An independent "Arbiter" model reviews the votes and eliminates the weakest link.
5.  **Refinement**: Surviving members refine their answers based on previous rounds.
6.  **Synthesis**: The final survivor (or a small group) synthesizes a "Master Answer" incorporating the best insights from the entire session.

## Purpose
The goal is to improve answer quality, accuracy, and nuance by:
-   Leveraging the "wisdom of the crowd" (ensemble method).
-   forcing models to critique and refine their outputs.
-   Removing hallucinations or poor reasoning through peer voting and arbiter judgment.

## Key Features
-   **Visual Interface**: A "Council Chamber" UI showing models sitting at a round table.
-   **Real-time Deliberation**: Users watch the debate unfold step-by-step via Server-Sent Events (SSE).
-   **Model Agnostic**: Can be configured to use any models available via the Hugging Face Inference API.

