# Plan: Assignment Instructions Decoder

## Problem

Assignment instructions are often ambiguous or underspecified, and students lose points
not because they didn't do the work, but because they misread what was actually required.
This tool takes a raw assignment prompt and turns it into a concrete, checkable list of
deliverables, flags anything genuinely ambiguous instead of letting the student silently
guess, and states what "done" looks like.

## MVP scope (what ships for this assessment)

- Single text box: paste assignment instructions.
- One backend endpoint (`POST /api/decode`) that calls Claude once and returns:
  - a checklist of concrete deliverables
  - a list of flagged ambiguities (empty list if genuinely none)
  - a one-to-two sentence definition of done
- Minimal single-page frontend (no framework) that renders the three sections.
- No accounts, no database, no persistence between sessions.
- No auth beyond a local `ANTHROPIC_API_KEY` environment variable.

## Final goals (stretch, not required for MVP)

- Let the user paste a rubric alongside the instructions and cross-check their own
  draft against both.
- Save past decoded assignments locally so a student can revisit them.
- Export the checklist as a markdown or PDF file.
- Support pasting a syllabus and batching multiple assignments at once.

MVP intentionally excludes all of the above — the goal for this assessment is one
correct, well-reasoned decode flow, not a feature-complete product.

## AI-Involvement Level: High

I'm targeting a **high** AI-involvement level for this build: Claude generates the
majority of the implementation (backend routes, prompt design, frontend) from a plan
and stack decisions I make explicitly, and I review, test, and adjust before committing.

Reasoning: the interesting, hard part of this project is the **prompt design** —
correctly separating "concrete deliverable" from "genuinely ambiguous requirement"
without over- or under-flagging. That's a reasoning/judgment problem I want to spend
my own time evaluating and iterating on. The surrounding code (FastAPI boilerplate,
a static HTML page, request/response models) is not where the learning value is, so
it makes sense to let Claude produce that quickly and put my attention on whether the
outputs are actually good.

## Architecture

- **Backend:** FastAPI, single `/api/decode` route, Pydantic request/response models.
- **Prompt:** one system prompt instructing Claude to return structured JSON
  (deliverables, ambiguities, definition_of_done) — no markdown fences, no preamble.
- **Frontend:** static HTML + vanilla JS, single page, fetches the API route.
- **No database.** State lives only in the browser for the current session.
