# Understanding guide template

One reader, one job: someone competent but new to this module, who wants to *understand* the defect rather than just approve a patch. They should finish able to explain the bug to a colleague without looking anything up.

Save as `<output-dir>/<slug>-understanding.md`. Same slug as the issue report, and link the two documents to each other.

Length follows the subject. A one-line off-by-one in a self-contained helper needs a page. A defect in a scheduler, a page-cache writeback path, or a lock-ordering rule needs several, because the reader cannot judge it without the design around it.

## Structure

```markdown
# Understanding: <the defect, in plain words>

Companion to <issue report path>. Read that first for the verdict and the fix.

## The short version

Five sentences, no jargon: what this module does, what it was supposed to do here,
what it does instead, and why that matters. Someone who reads only this section should
get the shape of the bug right, even if they miss the detail.

## Vocabulary

Every term the reader needs, defined in one or two sentences each, in the order they
first appear later in this document. Include the ones that feel too basic to define —
the cost of over-explaining is a skipped line, the cost of under-explaining is a
reader who stops.

- **<term>** — <plain definition>. <Why it shows up in this bug.>

## What this module is for

Where the module sits in the system, what problem it solves, who calls it and who it
calls. One paragraph, then the map:

​```text
user process
  → syscall layer          <dir/>
    → this module          <dir/>
      → backing device     <dir/>
​```

Name the public surface explicitly: which functions, syscalls, or ioctls are the
outside world's way in. The defect's reachability argument rests on this list.

## The design, and why it is this way

The part that makes the bug make sense.

- **The state it keeps** — the structs and fields that matter here, what each one means.
- **The invariants** — the properties the code assumes hold at all times. Quote the
  assertions, comments, or locking rules that state them.
- **The design intent** — why this structure was chosen: performance, hardware
  constraints, compatibility, a standard's requirement. Cite the commit, doc, or spec
  where you found the reasoning. If you are inferring intent rather than reading it,
  say "inferred".
- **The tradeoffs** — what this design gives up. Bugs usually live in whatever the
  design decided not to handle.

## How it is supposed to work

Walk one correct execution end to end, in ordinary sentences, with `file:line` at each
step. The reader needs the working path in their head before the broken one means
anything.

## Where it goes wrong

Now the same walk with the triggering input. Show the exact point where the two walks
diverge, which invariant breaks first, and how the damage propagates from there to
the visible failure. Line numbers match the issue report.

## How the test exercises it

What the triggering test sets up, which entry point it calls, what it asserts, and why
that assertion is the right expectation. If the test is artificial in any way, say how
and whether that weakens the case.

## History

When the line was written and what the commit was solving (`git log -L`, `git blame`).
Often the defect is an edge case the original change did not need to handle, and saying
so is more useful than implying carelessness. Note related past fixes in the same area.

## Neighbouring concepts worth knowing

Adjacent things the reader will bump into and would otherwise have to look up: the
locking scheme around this path, the lifetime rules for these objects, the relevant
part of the standard. Short, and only what actually touches this bug.

## Check yourself

Three or four questions a reader should be able to answer after this document. Give
the answers, briefly — they double as a summary.

## Further reading

Specific pointers, not a reading list: `Documentation/<file>`, the spec section number,
the commit SHA, the source file to read next. Say what each one is good for.
```

## Rules that matter more than the structure

- **Explain, don't summarize the code.** A paraphrase of what the lines say adds nothing. Say why the lines are that way and what they are protecting.
- **No term used before it is defined.** Scan your own draft for the first appearance of each piece of jargon.
- **Mark inferred design intent as inferred.** Reading purpose out of code is guessing; a commit message or a doc is evidence. Keep them visibly apart.
- **Concrete over abstract.** Real values, real sizes, real struct names. "A 4096-byte page with 512-byte sectors" teaches; "the relevant granularity mismatch" does not.
- **Where the report and the guide overlap, keep the numbers identical.** Same lines, same commit, same values. A reader flipping between them should never have to reconcile two versions.
- **It is fine to be long here.** The report earns its keep by being short; the guide earns its keep by leaving no gaps.
