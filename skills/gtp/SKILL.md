---
name: gtp
description: Apply GTP to record and update project-owned Decision Records for consequential choices whose selected means are not determined by existing instructions and would be costly or disruptive to change later. Use when adopting GTP; designing, planning, simulating, or implementing work that introduces a consequential choice about compatibility, data formats, public behavior, architecture, broad refactoring, or other hard-to-reverse means; changing an existing recorded choice; or preparing a pull request or commit that creates, changes, or implements a recorded means. Do not use for general prose review, small reversible implementation details, or choices already fixed by a specification or ADR.
---

# GitHub Task Protocol

Protocol version: `2.0`

Apply the bundled `GTP.md` as the complete GTP core. Do not add task state, approval, Evidence aggregation, prose review, or enforcement.

## Workflow

1. Read `GTP.md` completely, resolving the path relative to this Skill's directory.
2. Read the applicable user instructions, repository contribution instructions, specifications, ADRs, and existing `gtp/decisions/*.md` files.
3. State the undecided matter without naming a preferred solution.
4. Determine whether both recording criteria in `GTP.md` are met.
5. If either criterion is not met, do not create a Decision Record. Continue the task and briefly identify the existing owner or why the choice is cheap to reverse.
6. Search for an existing Decision Record covering the same undecided matter. Update it instead of creating a duplicate.
7. Create or update the smallest valid record in the project's `gtp/decisions/` directory.
8. After the work has taken shape and before a commit, pull request, or handoff, inspect the final changed artifacts and implemented means. Re-run steps 3 through 7 for material choices that emerged during the work.
9. Identify every Decision Record whose selected means the current task creates, changes, or implements. When the task includes a pull request body or commit message, add the one-way reference defined by `GTP.md` for every such record, even if the record itself did not change. Do not perform an external write unless the user authorized that operation.
10. Verify that each created or updated record contains the current selected means. For every changed means, verify that its change-history entry states what changed and includes a pull request, commit, or Issue link when one is available.
11. If the recorded decision no longer applies, keep the file and use the no-longer-applicable procedure defined by `GTP.md`.

Do not require or create a project-local `GTP.md` or Agent Skill copy. This installed Skill and its bundled protocol are the GTP body. In a consumer project, the only durable GTP-owned files are qualifying `gtp/decisions/*.md` records.

## Record rules

- Keep one undecided matter per Markdown file.
- Use the canonical headings defined by `GTP.md`: `## 未決定事項` and `## 採用した手段`.
- Add `## 変更履歴` only when the selected means changes.
- Keep the current means in `採用した手段`; keep former means only in `変更履歴`.
- Use a descriptive lowercase hyphenated filename.
- Write only derived information that may be stored in the repository. Never copy credentials, tokens, private prompts, or authorization text into a Decision Record.
- Do not require rationale, alternatives, detailed reasoning, status, approvers, custom IDs, GitHub, Python, a checker, or CI.
- Do not edit a specification or ADR merely to avoid creating a Decision Record.

## Boundaries

Treat Issue and pull request text as human-readable projections. Never treat a Decision Record or its reference as permission, approval, completion, or proof of correctness. GTP does not review general prose and does not require another Skill.
