# What makes a defect real

## The vocabulary, because it decides the argument

Testing practice separates three things, and mixing them up is how fake bugs get filed:

- **Error** — a human mistake: a misread spec, a wrong assumption.
- **Defect (fault, "bug")** — the resulting flaw sitting in the code. ISTQB: *an imperfection or deficiency in a work product where it does not meet its requirements or specifications*.
- **Failure** — the observable deviation when that flaw executes: wrong output, crash, hang, corrupted state.

So a defect is a **gap between the code and a contract**, and a failure is that gap showing up at runtime. A report that names neither a contract nor a failure is not describing a defect — it is describing code someone dislikes.

The industry version of this same line: theoretical findings and static-analysis output with no demonstrated runtime impact do not qualify as defects. Deciding *not a bug* is a real claim too, and it carries a burden: you have to establish the bad state is unreachable in the context being analyzed, not just that reaching it looks awkward.

## The four gates

A report is a real defect only if all four hold. Check them in order and stop at the first failure.

### 1. A named contract

Point at the thing the code violates. One of:

- documentation, doc comment, or header describing intended behavior
- an external standard: POSIX, an RFC, an ISA or hardware manual, a file-format spec
- an invariant the code itself asserts or obviously relies on ("`refcount > 0` while the page is mapped")
- an existing test that encodes the expected behavior
- a safety property no one writes down but everyone assumes: no memory corruption, no unprivileged panic, no lost durable write, no privilege escalation

If the only argument is "this looks wrong to me," you have not cleared gate 1. If the current behavior *is* the documented behavior, the report is at most a design complaint — and in a kernel, changing user-visible behavior is itself the thing maintainers refuse, because the public interface is the contract.

### 2. Reachable from a public entry point, with caller-controlled input

Write the call chain from the public surface to the faulty line, `file:line` at each hop:

```
sys_write() fs/read_write.c:652
  -> vfs_write() fs/read_write.c:578
    -> ext4_file_write_iter() fs/ext4/file.c:700
      -> the faulty branch fs/ext4/file.c:742
```

"Public entry point" means whatever a real caller can actually invoke from outside the module: syscall, ioctl, exported symbol, network handler, CLI argument, config file. And the values that steer execution into the bad branch have to be ones that caller can choose, directly or through a chain of ordinary calls.

This gate is where constructed bugs die. Reachability is what turns a suspicious line into a defect; without it you have a line, not a bug.

### 3. An observable bad outcome

Name what goes wrong in terms someone outside the code can see: wrong return value or errno, corrupted or lost data, panic or `BUG_ON`, deadlock or livelock, leaked memory or descriptors, unbounded growth, a permission check skipped, a measurable performance cliff.

"The code is confusing" and "this could be refactored" are not outcomes. Neither is "an internal variable holds a surprising value" unless you carry that value forward to something visible.

### 4. Stated trigger conditions

Spell out the preconditions and the sequence: argument values, prior state and how the caller reaches it legitimately, configuration, concurrency. Reproduction steps must be minimal and deterministic — no extra steps, same result every run.

If it is a race, name the interleaving: which two paths, which shared object, which lock is missing or dropped, and which order produces the failure. "Sometimes crashes under load" has not cleared this gate.

## Disqualifiers — how a constructed bug gives itself away

Any one of these makes it *not a defect*, or at best latent:

- **Reached only by calling an internal helper directly.** The test invokes a `static`/private/unexported function with arguments no public caller would produce.
- **Hand-built impossible state.** The setup assigns struct fields, pokes memory, or mocks a neighbour into a state the public API never constructs. If the state is unreachable, so is the bug.
- **Documented preconditions violated.** The function says "caller must hold the lock" or "`len` must be nonzero" and the trigger ignores that. That is a bug in the caller the test wrote, not in the function.
- **The code had to be modified to trigger it.** A patch, an injected fault, or a compiler flag nobody uses is part of the reproduction.
- **Trusted-caller boundary.** The input is already validated upstream, or only a privileged component supplies it, and the threat model says that component is trusted. Say which boundary and where the validation lives.
- **The test asserts the bug's premise.** The "expected" value in the new test comes from the reporter's intuition, while the existing suite and the docs agree with the current behavior.
- **Unreachable defensive check.** An assertion on a condition genuinely impossible to produce from outside. Note the flip side: if it *is* reachable from an unprivileged caller, an assertion that kills the process is a real defect. Kernel `BUG_ON`s get removed for exactly this reason when userspace can trip them through an ioctl.
- **Behavior-preserving nit.** Naming, formatting, dead code, a redundant check. Worth a cleanup patch, not an issue report.
- **Symptom filed at the wrong place.** Real failure, but the accused line only manifests it; the defect lives elsewhere. Report it where the fix goes.

## Gray zones, named honestly

- **Latent defect** — the code is wrong and would fail if reached, but no current path reaches it. Say "latent", say what would expose it (a new caller, a config, a future refactor). Do not inflate it to confirmed; do not dismiss it as fake.
- **Missing feature vs defect** — behavior absent from the code but promised by requirements is a defect; behavior nobody promised is a feature request.
- **Spec is wrong** — code matches the docs, docs contradict the standard. Real problem, but the fix is a decision, not a patch. File it as a spec question with both sides quoted.
- **Reachable but harmless** — the path exists and the value is odd, yet nothing downstream is affected. Gate 3 fails. Say so.

## Evidence ladder

Rank your own evidence, and print the rank in the report:

1. **Executed** — you ran a test or program and captured the failure output. Strongest.
2. **Traced** — complete entry-point-to-fault path read from source, with every hop cited, but nothing run.
3. **Inferred** — plausible reasoning with a gap you could not close. Say where the gap is.

Never present level 3 as level 1. A report that says "traced, not executed" stays useful; one that overclaims and collapses under the reviewer's first check costs you every future report.

## Sources

- [ISTQB defect definition and bug anatomy](https://yrkan.com/blog/bug-anatomy/)
- [Anatomy of a bug report — deviation between specification and implementation](https://ariya.io/2016/09/anatomy-of-a-bug-report)
- [Bug vs defect vs failure](https://thelinuxcode.com/defect-vs-bug-vs-failure-how-i-draw-the-lines-in-real-software-work/)
- [Defects in software testing](https://testsigma.com/blog/defects-in-software-testing/)
- [containerd security triage guide — theoretical findings do not qualify](https://containerd.io/docs/main/security/triage_guide/)
- [The Hitchhiker's Guide to Program Analysis, Part III — the burden of a no-bug decision](https://arxiv.org/html/2606.15122)
- [Reachability vs exploitability](https://konvu.com/blog/reachability-vs-exploitability)
- [Reachability is not enough without context and trust boundaries](https://checkmarx.com/blog/ai-llm-tools-in-application-security/reachability-was-a-breakthrough-but-now-its-not-enough/)
- [Minimal, deterministic reproduction steps](https://blog.cxgenie.ai/reproduction-steps-for-bugs-a-5-part-template-and-real-examples)
- [Kernel BUG_ON reachable from unprivileged userspace, treated as a defect](https://windowsforum.com/threads/cve-2026-46220-amdgpu-linux-fix-bug_on-kernel-panic-in-sdma-4-0.420661/)
- [Linux policy: the syscall interface is the contract](https://unix.stackexchange.com/q/235335/86440)
