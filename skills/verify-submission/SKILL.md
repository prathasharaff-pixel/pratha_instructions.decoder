---
name: verify-submission
description: >
  Use this skill when given (1) a checklist of deliverables from a decoded
  assignment prompt, and (2) the text of a student's completed submission.
  It checks, item by item, whether each checklist item is PRESENT in the
  submission. Do NOT use this skill to judge quality, correctness, or grade
  the work - only whether each required item appears to be there at all.
---

# Verify Submission Skill

## Purpose

Given a list of deliverables (from the decode-assignment skill) and the raw
text of a student's submission, determine for each deliverable whether it
appears to be present in the submission.

This is a COMPLETENESS check, not a QUALITY check. "Did you include a
methodology section?" is in scope. "Is your methodology any good?" is not.

## Process

1. Read the full submission text once before checking anything.
2. For each deliverable in the checklist, look for direct evidence in the
   submission that it exists (a section, a sentence, a file reference, etc.).
3. Mark each item as one of: "present", "missing", or "unclear" (unclear =
   there's a hint of it but not enough to confidently say either way).
4. For every "missing" or "unclear" item, give a one-sentence reason citing
   what you did or didn't find.
5. Do not infer effort, correctness, or quality. A poorly-written methodology
   section is still "present."

## Output contract

Respond with ONLY valid JSON, no preamble, no markdown fences, in this shape:

```json
{
  "results": [
    {"item": "...", "status": "present", "note": ""},
    {"item": "...", "status": "missing", "note": "No mention of ... found anywhere in the submission."}
  ]
}
```

status must be exactly one of: "present", "missing", "unclear".
