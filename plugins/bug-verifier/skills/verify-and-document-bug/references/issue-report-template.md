# Issue report template

One reader, one job: a reviewer who has not seen the bug document and will not read the source tree before deciding. They must finish this page knowing what breaks, where, how to reproduce it, and what fixing it costs.

Save as `<output-dir>/<slug>-issue.md`. The slug is `component-symptom`, e.g. `ext4-writeback-lost-flush`.

Keep it to about a page and a half. Background belongs in the understanding guide — link to it, don't inline it.

## Structure

```markdown
# <Component>: <symptom> when <condition>

**Verdict:** Confirmed defect | Latent defect | Undetermined
**Evidence:** Executed | Traced from source | Inferred
**Severity:** <crash / data loss / wrong result / resource leak / hang> — <who is affected>
**Source:** <repo> @ <commit SHA>
**Understanding guide:** <relative path>

## Summary

Two or three sentences. What breaks, under what condition, and what the consequence is.
A reader who stops here should be able to repeat the bug back correctly.

## Where the defect is

`path/to/file.c:120-136` — `function_name()`

​```c
120  static int do_thing(struct ctx *c, size_t len)
121  {
122          /* copied verbatim from the file, real line numbers */
...
136  }
​```

One or two sentences naming the exact line that is wrong and what it does wrong.

## Root cause

Three to six sentences on the mechanism: which value is wrong, how it gets that way,
which invariant or contract it breaks, and how that turns into the visible failure.
State the contract explicitly and cite it — doc comment, standard, invariant, or test.

## How it is reached

The chain from the public entry point to the faulty line. Every hop cited.

1. `sys_entry()` — `path/file.c:652` — caller passes `len = 0`
2. `middle_layer()` — `path/file.c:578` — no length check here
3. `do_thing()` — `path/file.c:130` — subtraction underflows

Note which inputs the caller controls, and any precondition the caller reaches legitimately
(no patched code, no hand-built state, no internal-only entry).

## Reproduction

Test: `tests/test_thing.c:84` — `test_zero_length_write()`

​```bash
make test TESTS=test_thing
​```

Output:

​```text
<exact captured output, trimmed to the relevant lines>
​```

If nothing was run, say so here in one line and state what blocked it.

## Expected vs actual

**Expected:** `do_thing()` returns `-EINVAL` for `len == 0`, per the doc comment at `path/file.c:112`.
**Actual:** `len - 1` wraps to `SIZE_MAX`, the loop at `:131` reads past the buffer, and the process takes a SIGSEGV.

## Impact

Who hits it and how badly. Reachable by an unprivileged caller? Does it corrupt persistent
state? Does a crash take down more than the caller? Name the worst realistic case, not the
worst imaginable one.

## Suggested fixes

**Option A — <one line>.** `path/file.c:130`. What to change, and the tradeoff.
**Option B — <one line>.** Where and why you would prefer or reject it.

Say which you would pick and why. If the right fix is a design decision rather than a patch,
say that instead of inventing one.

## Open questions

What you could not verify, and the one check that would settle each item. Write "none" if
there is nothing open — an empty section reads as an oversight.
```

## Rules that matter more than the structure

- **Title carries the bug.** `"ext4: zero-length write underflows length and reads past the buffer"` beats `"bug in ext4 write path"`. A reviewer scanning a list decides from the title alone.
- **Snippets are copied, never retyped.** Real path, real line numbers, real commit.
- **Expected vs actual both come with a source.** Expected cites the contract. Actual cites the run or the traced path.
- **No hedging on the verdict.** You already decided in Step 4. "Possible issue" makes the reviewer redo your work.
- **No background dumps.** Design history, concept explanations, and module tours go in the guide. If the report needs a term the reviewer may not have, define it in six words or link.
- **Separate what you were told from what you checked.** If the original bug document claimed something you could not confirm, say "the report claims X; I could not confirm X" instead of quietly repeating it.
