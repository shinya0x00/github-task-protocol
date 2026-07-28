---
name: gtp
description: Set up GTP or record and update project-owned Decision Records for material choices that are not determined by existing instructions and would be costly or disruptive to change later. Use when adopting GTP; when designing, planning, simulating, or implementing work that introduces a consequential choice about compatibility, data formats, public behavior, architecture, broad refactoring, or other hard-to-reverse means; or when an existing recorded choice changes. Do not use for small reversible implementation details or choices already fixed by a specification or ADR.
---

# GitHub Task Protocol

Protocol version: `2.0`

Apply the repository's `GTP.md` without adding state, approval, Evidence aggregation, or enforcement.

## Workflow

1. Read `GTP.md` completely.
2. Read the applicable user instructions, specifications, ADRs, and existing `gtp/decisions/*.md` files.
3. State the undecided matter without naming a preferred solution.
4. Determine whether both recording criteria in `GTP.md` are met.
5. If either criterion is not met, do not create a Decision Record. Continue the task and briefly identify the existing owner or why the choice is cheap to reverse.
6. Search for an existing Decision Record covering the same undecided matter. Update it instead of creating a duplicate.
7. Create or update the smallest valid record in the project's `gtp/decisions/` directory.
8. When the current task includes a pull request body or commit message, add the one-way reference defined by `GTP.md`. Do not perform an external write unless the user authorized that operation.
9. Verify that the record contains the current selected means and that any changed means has a concise change-history entry.
10. If the recorded decision no longer applies, keep the file and use the no-longer-applicable procedure defined by `GTP.md`.

If the project does not contain `GTP.md`, do not invent or reconstruct its protocol from this Skill. For an adoption request, copy the version-matched `GTP.md` and `skills/gtp/` from the same GTP release before creating project Decision Records.

## Record rules

- Keep one undecided matter per Markdown file.
- Use the canonical headings defined by `GTP.md`: `## 未決定事項` and `## 採用した手段`.
- Add `## 変更履歴` only in the case defined by `GTP.md`.
- Keep the current means in `採用した手段`; keep former means only in `変更履歴`.
- Use a descriptive lowercase hyphenated filename.
- Write only derived information that may be stored in the repository. Never copy credentials, tokens, private prompts, or authorization text into a Decision Record.
- Do not require rationale, alternatives, detailed reasoning, status, approvers, custom IDs, GitHub, Python, a checker, or CI.
- Do not edit a specification or ADR merely to avoid creating a Decision Record.

## Boundaries

Treat Issue and pull request text as a human-readable projection. Preserve their explanation of purpose, visible change, implementation, and related decisions. Never treat a Decision Record or its reference as permission, approval, completion, or proof of correctness.
