---
name: verify-submission
description: >
  Use this skill whenever given a checklist of deliverables (produced by the
  decode-assignment skill) together with the text of a student's completed
  submission. It checks each checklist item against the submission and
  reports whether that item is present. Do NOT use this skill to grade
  quality, correctness, or style — it only answers "is this requirement
  present in the submission," never "is it any good." It is scoped to one
  task only: completeness verification against a fixed checklist.
---

# Verify Submission Skill

## Purpose

Given two inputs — a **checklist** of deliverables and the **submission
text** — produce, for every checklist item, a verdict of whether that item
is present in the submission, plus a one-line reason.

This is a completeness check, not a quality check. "Did you include a
methodology section?" is in scope. "Is your methodology any good?" is out
of scope — never comment on quality, correctness, depth, or style.

## Process

1. Read the full submission text once before judging any item — a
   deliverable may be satisfied by content that appears far from where you'd
   expect it (e.g. a "definition of done" satisfied in an intro paragraph).
2. For each checklist item, independently decide `present` or `missing`.
   Do not let one missing item bias the verdict on the next.
3. A item counts as `present` if the submission plausibly addresses it, even
   briefly. Do not require exhaustive or high-quality treatment — that is
   explicitly out of scope.
4. Write one short, literal reason per item citing what was or wasn't found.
   Do not editorialize about quality ("this is done well/poorly").
5. If the submission text is empty or clearly not a real submission, mark
   every item `missing` with the reason stating that no submission content
   was provided.

## Output contract

Always respond with ONLY valid JSON, no preamble, no markdown code fences,
in exactly this shape:

```json
{
  "results": [
    {"item": "<checklist item text>", "status": "present", "reason": "..."},
    {"item": "<checklist item text>", "status": "missing", "reason": "..."}
  ]
}
```

`status` must be exactly `"present"` or `"missing"` — no other values. There
must be exactly one result per checklist item given, in the same order.
