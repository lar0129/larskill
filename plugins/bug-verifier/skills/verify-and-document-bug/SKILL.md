---
name: verify-and-document-bug
description: "Judge whether a reported bug is a real defect, then write it up. Use whenever someone points at a bug document — a bug report, audit finding, static-analysis hit, LLM-generated finding, code-review comment, CTF-style claim — plus a source tree, and wants it verified, explained, or turned into an issue. Reads the claim, reads the accused code and the triggering test, traces whether the bad state is reachable from a public entry point with caller-controlled input, lands on one verdict (confirmed / latent / not a defect / undetermined), then produces two documents: an issue report a reviewer can act on without reading anything else, and an understanding guide that teaches the module's design and the concepts the defect sits on."
---

# Verify and Document a Bug

You get a bug document and a source tree. You return one judgment and two documents: an **issue report** a reviewer can act on alone, and an **understanding guide** that gives a reader everything they need to actually understand the defect.

The judgment comes first. Writing up a bug that isn't real costs the reviewer the same attention as a real one and returns nothing, so never skip ahead to the documents.

## Inputs

Ask for whatever is missing instead of guessing:

- **Bug document** — path to the report, finding, audit note, or message making the claim.
- **Source directory** — the tree the claim is about, plus the branch or commit if it matters.
- **Output directory** — where the two files go. Default to `./bug-docs/` and say so.

Write both documents in the language of the bug document, or the language the user is writing in. Match it, don't switch.

If the tree has a test suite you can run, find the command now — Step 3 needs it.

## Step 1 — Read the claim as written

Before opening any code, pull out in the claim's own terms:

- the component, file, and function it accuses
- the behavior it calls wrong, and the behavior it expects instead
- the input or call sequence it says triggers this
- what it offers as evidence: a test, a log, a stack trace, a diff, or nothing

Claims drift while you read code. You want the original version on record to compare against.

## Step 2 — Read the code yourself

Never trust the claim's snippets. Open the files.

- Find the accused function. Record the real path and the real line numbers of the lines that matter.
- Read the whole function, plus what its callers pass in and what they do with the result.
- Trace outward to the **public entry points** — syscall, ioctl, exported API, CLI flag, request handler, whatever this module's public surface is. You need the actual chain with `file:line` at each hop, or an honest statement that you could not find one. This is the step that separates real defects from constructed ones.
- Read the test the claim points at, and the neighbouring tests covering the same function. A passing test that asserts the accused behavior is a strong hint that the "bug" is the specification.
- Find the contract: doc comments, header docs, `Documentation/`, a standard (POSIX, an RFC, an ISA manual), asserted invariants, or what the existing tests demand. A defect is a gap between code and a contract. If you cannot name the contract, you cannot call it a defect yet.
- Run `git log -L` and `git blame` on those lines. Why the code looks like this is usually in the commit that wrote it, and the guide will need that history.

## Step 3 — Try to trigger it

Run the named test, or write the smallest one that exercises the path. Record the exact command and the exact output, including failure output.

If you cannot run anything — no toolchain, needs hardware, kernel needs a VM — say so plainly in both documents. "Reasoned from source, not executed" is a legitimate evidence level. Claiming you ran something you did not is not.

## Step 4 — Judge it

Read `references/genuine-bug-criteria.md` before deciding. It holds the four gates a report must pass and the disqualifier list that catches constructed bugs; that list is the point of this skill.

Land on exactly one verdict and put it in the first line of whatever you write:

- **Confirmed defect** — all four gates pass, backed by a reproduction or a complete entry-point path.
- **Latent defect** — the code is genuinely wrong, but nothing reachable today reaches it. Real, low priority. Say what would make it reachable.
- **Not a defect** — it needs state the public surface cannot produce, or the behavior is the documented behavior, or it is a style preference.
- **Undetermined** — name the single thing that would settle it.

For **not a defect**, skip the two-document package. Write one page: what was claimed, what you checked with `file:line`, which gate fails and why, and what would have to be true for the claim to hold. Do not soften it to "potential issue" to be polite. And do not go hunting for a different bug to justify the exercise — if you noticed one along the way, mention it in a line or two, clearly separate from the verdict.

## Step 5 — Write the two documents

Use `references/issue-report-template.md` and `references/understanding-guide-template.md`. Follow their section order. Drop a section only when it is genuinely empty, and then say it is empty rather than padding it.

The split: **the report is for deciding and fixing, the guide is for learning.** Mechanism, line numbers, reproduction, and fix options go in the report. Module purpose, design intent, unfamiliar concepts, and the walkthrough of correct behavior go in the guide. When in doubt the report stays short and the guide absorbs the background.

## Evidence rules

- Every code snippet is copied from the file with its real path and line numbers. Never paraphrase or reconstruct code.
- Label every claim about runtime behavior: executed, traced from source, or inferred.
- Line numbers drift, so pin the commit SHA you read.
- If you went looking for something and it was not there, that is a finding. Write it down.
- Keep a clear line between what the bug document asserted and what you verified.

## Style

The `talk-like-a-human` skill applies to both documents. The short version:

- Lead with the point. First line of the report says what breaks and how bad it is.
- Plain words. Define a term the first time you use it, or use one the reader already owns.
- One idea per sentence.
- Keep exact numbers, names, and conditions. Concise means cutting filler, not facts.
- Prose and short lists over heavy tables. Use a table only for a real grid.
- Say what you don't know, plainly.

## Before you hand it over

Reread both documents as the reviewer, not the writer:

- Does the first line of the report say what breaks?
- Could they find the code from the report alone?
- Could they reproduce it from the report alone?
- Is every snippet real and every line number checked against the file?
- Is everything unverified marked as unverified?
- Does the guide explain every term the report uses without explaining?
