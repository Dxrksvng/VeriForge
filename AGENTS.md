# VeriForge — Persistent working instructions

These instructions apply to this project directory and its descendants.

## Read at the start of each task

1. Read `docs/WORKING-AND-LEARNING-AGREEMENT.md` fully.
2. Read `docs/PROGRESS.md` fully for implementation status, learner progress, evidence, and the next action.
3. For building or teaching, read the applicable module in `docs/LEARNING-ROADMAP.md` and its prerequisites. Read the full roadmap when planning the overall project or when no module is selected.
4. Inspect actual files and relevant tools before assuming recorded state is current. The HTML/PDF blueprint provides architectural context; the current agreement and progress record govern the workflow. Explicit user instructions take precedence.

## User intent

- Latest user instruction (2026-09-21): finish the full authorized local v1 first, then teach from the completed system. Do not pause for lessons/exercises or stop after one module. Preserve learning documentation for later.

- Build VeriForge quickly while teaching the user the fundamentals and the complete system in Thai.
- The assistant performs most implementation; the user is not expected to type every line or approve routine implementation choices.
- Teach using working vertical slices, actual code paths, controlled failures, real tests, and evidence. Avoid a giant unexplained code dump.
- Explain critical functions with inputs, outputs, callers, side effects, invariants, permissions, concurrency, failure modes, and tests. Summarize routine framework boilerplate unless asked for detail.
- Learning exercises are optional and must not block independently authorized implementation. Never infer that the learner understands merely because a feature is implemented.
- Aim for free services or minimal predictable cost. Do not purchase services, expose private data, publish externally, use real money, or deploy to an external environment merely because this document exists. Follow the current request and existing specific authorization.

## Starting and resuming

- If the user asks to start/continue without repeating requirements, use `docs/PROGRESS.md` to select the next unfinished step; give a short Thai recap and proceed within the requested scope.
- If the user only asks a question or requests documentation, answer or document it; this file does not automatically authorize application implementation.
- Default first build slice: reproduce duplicate fees locally, implement a transaction-safe idempotent solution, run trusted tests, and produce a deterministic decision with evidence. Stage the slice into small runnable increments.
- First inspect available Python/Node/Docker versions and repository state. Do not start with cloud accounts, paid APIs, or large infrastructure.
- Ask only for genuinely missing decisions or permissions. Do not ask again for preferences already documented here.

## Evidence and safety boundaries

- Separate REAL_OPERATIONAL, PUBLIC_BENCHMARK, SYNTHETIC_REPLAY, and INJECTED_FAULT data. Record dataset origins and transformations.
- No fabricated metrics, passing statuses, confidence claims, or simulated operations presented as real execution.
- Missing mandatory evidence, scanner errors, timeouts, or invalid model output must not silently become PASS.
- Bind release evidence and approvals to the exact artifact and source revision. Builder cannot approve/deploy its own change or weaken trusted controls.
- Keep intentionally vulnerable examples and fault injection in isolated local/test environments. Do not execute untrusted proposals with production credentials or on the control-plane host.
- Never put secrets, private telemetry, or model reasoning traces into lesson notes. Store only necessary outputs and redacted evidence.

## Finish each implementation or teaching session

- Update `docs/PROGRESS.md`: what changed, exact verification commands/outcomes, unresolved issues, learner understanding only as demonstrated, and one concrete next action.
- Add or update the relevant lesson under `docs/lessons/` using the template. Keep links and example commands aligned with real files.
- Report the result in Thai: behavior changed, why, validation, a short learning point, and the next step. Clearly mark unrun commands and unimplemented features.
- Do not mark a module complete on the strength of documentation alone. Track engineering completion and learning completion separately.
