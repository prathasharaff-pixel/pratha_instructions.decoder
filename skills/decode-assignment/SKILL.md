---
name: decode-assignment
description: >
  Use this skill whenever given the raw text of a confusing or underspecified
  assignment prompt. It turns that text into a concrete checklist of
  deliverables, a list of genuinely ambiguous requirements, and a plain-language
  definition of done. Do NOT use this skill for grading, writing the assignment
  itself, or summarizing unrelated documents — it is scoped to one task only:
  decoding assignment instructions.
---

# Decode Assignment Skill

## Purpose

Given the raw text of an assignment prompt, produce exactly three things:

1. **Deliverables** — a concrete checklist of every distinct requirement or
   action the student must complete. Each item must be something the student
   can literally check off (a single artifact, action, or file). Do not invent
   requirements that aren't implied by the text. Do not merge two distinct
   requirements into one checklist item.

2. **Ambiguities** — a list of genuinely ambiguous or underspecified points:
   places where a reasonable student could interpret the instructions two
   different ways, or where a concrete detail (format, length, deadline,
   submission method, tooling) is missing entirely. Do NOT flag something that
   is actually stated clearly just to pad the list. If there is truly nothing
   ambiguous, return an empty list — do not force an entry.

3. **Definition of done** — one to two sentences stating, in plain language,
   what "done" concretely looks like for this assignment. This should be
   specific enough that the student could self-check against it without
   re-reading the whole prompt.

## Process

1. Read the entire prompt once before extracting anything — some ambiguities
   only become visible by cross-referencing separate parts of the prompt
   (e.g. a section that mentions a deliverable another section never defines).
2. Extract deliverables first, as literal, checkable items.
3. Separately, extract ambiguities — do not conflate "not yet done" with
   "ambiguous." A missing/undecided detail is ambiguous; a straightforward
   task the student just hasn't started yet is not.
4. Write the definition of done last, after deliverables and ambiguities are
   both settled, so it reflects the full picture.

## Output contract

Always respond with ONLY valid JSON, no preamble, no markdown code fences,
in exactly this shape:

```json
{
  "deliverables": ["...", "..."],
  "ambiguities": ["...", "..."],
  "definition_of_done": "..."
}
```

If the input text is empty or not actually an assignment prompt, return:

```json
{
  "deliverables": [],
  "ambiguities": ["The input does not appear to contain assignment  instructions."],
  "definition_of_done": "N/A — no assignment text was provided."
}
```
