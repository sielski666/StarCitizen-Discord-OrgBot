# ASTRID ENGINEERING POLICY (Project Baseline)

This policy is the primary workflow baseline for this repository.
It is applied within existing platform/system safety and governance constraints.

## Mission
Deliver correct, high-quality code changes with maximum efficiency, minimal token usage, and bounded execution time while preserving steady forward progress.

## Core Operating Principles
- Prioritize forward progress over exhaustive analysis.
- Prefer deterministic, surgical edits.
- Minimize latency, context size, and unnecessary tool calls.
- Never allow unbounded exploration loops.
- Preserve work and checkpoint frequently.

## Repository Access Rules
- Never ingest the entire repository into model context.
- Never perform full-project rereads unless explicitly instructed.
- Always operate file-by-file.
- Only open files directly required for the current objective.
- Prefer targeted search before opening any file.
- Limit active file context to the minimum necessary.
- Prefer local repository tools over remote GitHub API calls when possible.
- Cache discovered file locations for reuse within a task.

## Context Management
- Keep prompts as small as possible while preserving correctness.
- Maintain stable prompt scaffolding; append dynamic data at the end.
- Reuse prior conclusions instead of re-deriving them.
- Avoid repeated summarization of the same files.
- Never re-upload large unchanged content.

## Adaptive Effort Routing
Use the minimum capability required.

### Fast Path (default)
- Small refactors
- Targeted bug fixes
- Formatting/lint fixes
- Single-file edits
- Test-driven fixes

### Deep Path (escalate only when needed)
- Multi-file architectural changes
- Complex logic bugs
- Ambiguous requirements
- Cross-module refactors
- Fast Path failed twice

Rules:
- Do not start in deep mode by default.
- Escalate only with clear evidence.
- De-escalate after complex reasoning completes.

## Planning Behavior
- Produce one concise initial plan.
- Start execution immediately after planning.
- Replan only when blocked or tests fail.
- Maximum replans: 2.
- Prefer action over prolonged reasoning.
- Avoid speculative repository exploration.

## Editing Strategy
- Prefer minimal, surgical edits.
- Avoid full-file rewrites unless explicitly required.
- Batch coherent edits.
- Modify no more than 3–5 files per checkpoint cycle.
- Avoid reopening the same file repeatedly without cause.
- Complete one file cleanly before expanding scope.

## Step Loop Optimization
Each iteration must produce measurable progress:
- applied patch
- generated diff
- executed validation
- surfaced blocker

Rules:
- Avoid no-op reasoning cycles.
- Avoid repeated planning without action.
- Prefer fewer coherent steps over many micro-steps.
- If an iteration produces no repo change, next step must:
  - apply a patch, or
  - request clarification.

## Iteration Guardrails
- Maximum iterations per task: 25.
- Maximum replans: 2.
- If stalled for 3 consecutive steps, produce a checkpoint.
- Never enter open-ended improvement loops.
- If confidence is insufficient, ask one clear question.
- Bias toward usable partial results.

## Checkpoint Discipline
- After every 3 modified files, create a hard checkpoint.
- After successful validation, checkpoint immediately.
- If approaching limits, checkpoint early.
- Never risk losing accumulated progress.
- Prefer frequent safe checkpoints over large risky passes.

## Testing and Validation
- Prefer real tool-based validation (tests, lint, build).
- Never simulate test results when tools are available.
- When tests fail, pull only relevant failure context.
- Do not rerun full validation unnecessarily.
- Focus fixes on failing components.
- After validation success, checkpoint.

## Search Priority
- Use repository search before broad file reads.
- Prefer symbol/keyword-level search.
- Avoid directory-wide scans unless explicitly required.
- Limit concurrently open files.
- Reuse already identified relevant files.

## Performance Defaults
- Operate in file-scoped mode.
- Minimize context switches.
- Minimize token usage.
- Prefer local disk operations.
- Preserve steady progress toward checkpoint.
- Finish current objective before expanding scope.

## Failsafe Behavior
- Never loop indefinitely.
- If blocked, ask one clear clarification question.
- If limits approach, produce best partial checkpoint.
- Preserve current progress before stopping.
- Surface blockers early.

## Output Discipline
- Keep responses concise and structured.
- Prefer patches/diffs/actionable summaries.
- Avoid verbose narrative unless requested.
- Clearly report remaining risks/uncertainties.
- Make the next actionable step obvious.
