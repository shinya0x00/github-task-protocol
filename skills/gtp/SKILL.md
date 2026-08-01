---
name: gtp
description: Set up and apply GTP, record or update project-owned Decision Records for material choices, and validate pull request Decision Record mappings and changed history links with the bundled validator. Use when adopting GTP; when asked to validate or check a PR body, Decision Record references, or changed history for GTP conformance; when designing, planning, simulating, or implementing work that introduces a consequential choice about compatibility, data formats, public behavior, architecture, broad refactoring, or other hard-to-reverse means; or when an existing recorded choice changes. Do not use for small reversible implementation details or choices already fixed by a specification or ADR.
---

# GitHub Task Protocol

Protocol version: `2.0`

Apply the repository's `GTP.md` without adding state, approval, Evidence aggregation, or enforcement.

Use a POSIX shell environment with standard utilities and Git to run the bundled pre-submission validator.

For a validation-only request, read `GTP.md` and the applicable Decision Records, but do not create or update a record unless the user also requested a repair. Run the bundled validator against the supplied artifacts and report its diagnostics.

## Workflow

1. Read `GTP.md` completely.
2. Read the applicable user instructions, specifications, ADRs, and existing `gtp/decisions/*.md` files.
3. State the undecided matter without naming a preferred solution.
4. Determine whether both recording criteria in `GTP.md` are met.
5. If either criterion is not met, do not create a Decision Record. Continue the task and briefly identify the existing owner or why the choice is cheap to reverse.
6. Search for an existing Decision Record covering the same undecided matter. Update it instead of creating a duplicate.
7. Create or update the smallest valid record in the project's `gtp/decisions/` directory.
8. When the current task includes a pull request body, map each decision summary to exactly one nested repository-relative path as defined by `GTP.md`. A path-only list is nonconforming. For a commit message, use the `Decision-Ref` trailer instead.
9. Verify that the record contains the current selected means and that any changed means has a concise change-history entry. When a pull request, commit, or Issue can be referenced, include its Markdown link in each new or updated history entry.
10. Before handing a pull request body to review, save the intended body in a temporary file and run the adjacent `scripts/validate.sh` against the exact base and head commits. Pass the head with `--head-ref` and the current pull request, commit, or Issue link target with `--change-reference`. Do not omit an available reference to bypass the link check. Without a pull request body, omit `--head-ref` only when intentionally checking the current worktree; that result does not establish conformance of a future commit or pull request.
11. Treat validator exit `1` as nonconforming and repair every diagnostic before submission when repair is authorized. Exit `2` is a usage or environment error, not a conformance result. This validation does not decide task completion, correctness, review permission, or merge permission.
12. If the recorded decision no longer applies, keep the file and use the no-longer-applicable procedure defined by `GTP.md`.

Do not perform an external write unless the user authorized that operation. PR-body validation requires an exact head commit and an existing pull request, commit, or Issue link target. If either is unavailable and creating it is not authorized, report that prerequisite instead of omitting the argument and claiming conformance.

If the project does not contain `GTP.md`, do not invent or reconstruct its protocol from this Skill. For an adoption request, copy the version-matched `GTP.md` and `skills/gtp/` from the same GTP release before creating project Decision Records.

## Record rules

- Keep one undecided matter per Markdown file.
- Use the canonical headings defined by `GTP.md`: `## 未決定事項` and `## 採用した手段`.
- Add `## 変更履歴` only in the case defined by `GTP.md`.
- Keep the current means in `採用した手段`; keep former means only in `変更履歴`.
- Use a descriptive lowercase hyphenated filename.
- Write only derived information that may be stored in the repository. Never copy credentials, tokens, private prompts, or authorization text into a Decision Record.
- Do not require rationale, alternatives, detailed reasoning, status, approvers, custom IDs, GitHub, Python, a general-purpose checker, or CI. Use the bundled validator only for the conformance rules defined in `GTP.md`.
- Do not edit a specification or ADR merely to avoid creating a Decision Record.

## Boundaries

Treat Issue and pull request text as a human-readable projection. Preserve their explanation of purpose, visible change, implementation, and related decisions. The bundled validator checks only projection mapping and changed history links. Never treat its result, a Decision Record, or a reference as permission, approval, completion, or proof of correctness.
