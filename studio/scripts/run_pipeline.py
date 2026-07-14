"""Runs the full Phase 1 pipeline for one video, end to end, pausing for a
real human decision at Quality Review's interrupt if the auto-pass
threshold isn't met.

Needs every API key from Days 2-6 configured (Anthropic, Tavily, Voyage,
ElevenLabs, Kling, Deepgram, Gemini) to actually complete a live run — none
of those are in this project's own .env, so this script is correct but
untested end-to-end in this environment. It's still the real operator
entry point once those keys exist.

The human-in-the-loop resume only works within this single process
(InMemorySaver — see graph.py's compiled() docstring), which is exactly why
this script both starts the run AND handles its own interrupt/resume in one
continuous execution, rather than being a separate "resume later" CLI that
a durable checkpointer (Phase 2+ work) would actually support.

Usage:
    python scripts/run_pipeline.py
"""

from uuid import uuid4

from langgraph.types import Command

from studio.graph import compiled


def main() -> None:
    app = compiled()
    thread_id = str(uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    result = app.invoke({}, config=config)

    while "__interrupt__" in result:
        payload = result["__interrupt__"][0].value
        print(f"\n--- Quality Review needs a decision (thread {thread_id}) ---")
        print(f"Video: {payload['assembled_video_path']}")
        print(f"Scores: {payload['scores']}")
        if payload["issues"]:
            print(f"Issues: {payload['issues']}")
        decision = input("Approve for Compliance review? [approve/reject]: ").strip().lower()
        notes = input("Notes (optional): ").strip()
        result = app.invoke(Command(resume={"decision": decision, "notes": notes}), config=config)

    print("\n--- Run finished ---")
    print(f"case: {result.get('case_id')}")
    print(f"quality_verdict: {result.get('quality_verdict')}")
    print(f"compliance_verdict: {result.get('compliance_verdict')}")


if __name__ == "__main__":
    main()
