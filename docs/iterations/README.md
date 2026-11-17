# How we iterate

Every version goes round the same loop, and every round leaves evidence in this folder.

```mermaid
flowchart LR
    A[Brief or finding] --> B[Build]
    B --> C[Tour on the emulator<br/>scripts/capture_tour.py]
    B --> D[Assistant evaluation<br/>backend/scripts/eval_assistant.py]
    C --> E[Critique: read every screen<br/>and every answer]
    D --> E
    E --> F[Findings, fixes, tests]
    F --> B
```

1. **Build** from the brief, or from the last round's findings.
2. **Tour.** `scripts/capture_tour.py <version>` drives the app on the emulator through the same steps every
   time (sign up and log in, join a class, check in, breathe, ask in English and Hindi, then the teacher's screens)
   and saves screenshots and two screen recordings to `docs/media/<version>/`. The same steps each time make
   versions comparable side by side.
3. **Evaluate the assistant.** `backend/scripts/eval_assistant.py` asks a fixed set of questions in English,
   Hindi and Marathi, runs coarse automatic checks, and writes every answer to `docs/evals/`. The checks only
   catch obvious failures; a person reads every answer.
4. **Critique.** Look at every screenshot and read every answer as a student would. Each problem becomes a finding
   with the image or answer that shows it.
5. **Fix and lock in.** Each fix gets a test where one is possible, so the same problem cannot quietly return
   (for example, every suggested question is tested in all three languages).

Nothing here is user research yet: all people, check-ins and comments in screenshots are **synthetic demo data**.
Testing with real students starts only with their consent (the app asks for it at sign-up).

## Versions

| Version | What changed | Evidence |
|---|---|---|
| [v0.1](v0.1.md) | First build from the brief | `docs/media/v0.1/` |
| [v0.2](v0.2.md) | Fixes from the first tour: log-in switch, Hindi retrieval, sources, time zones | `docs/media/v0.2/`, `docs/evals/assistant_v0.2.md`, `docs/media/figures/` |
| [v0.3](v0.3.md) | Assistant: Marathi answers checked by reading them, and the fixes that followed | `docs/evals/assistant_v0.3.md` and later |

## Who did what

The brief (`instructions.md`, kept private) came from Dhwani Mundra. The code, tours and evaluations in v0.1–v0.3
were produced with Claude Code, an AI coding agent. Product decisions are recorded
in [`../decisions.md`](../decisions.md).
