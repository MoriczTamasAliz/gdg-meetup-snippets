# C — A rule, not a request

```bash
python -m pytest test_guard.py -q    # 10 tests
```

Already wired up in `.claude/settings.json`, so it is live in this repository.
Ask Claude to read `.env` and watch it refuse.

## The distinction

A line in `CLAUDE.md` saying "never read credentials" is a *suggestion* to a
probabilistic system — and it sits in the same context window as whatever the
agent just read from an issue body, a dependency README, or a web page. That is
precisely the channel an attacker uses.

A `PreToolUse` hook that exits 2 is a *rule*. It runs before the tool does, it is
deterministic, and nothing the model reads can talk it out of the decision.

## What it blocks, and why those things

The rules mirror a real kill chain. In January 2026 a CVE in the Claude Code
GitHub Action let an attacker open an issue on a public repository whose body
instructed the agent in CI to dump its own environment; the extracted OIDC token
was exchanged for a privileged installation token, which granted write access to
the action's own repository, which then ran in every downstream workflow pinned
to a floating tag. Anthropic fixed it in four days. The same research found
Gemini CLI and GitHub Copilot Agent also treat untrusted GitHub metadata as
authoritative prompt content, and in February the same pattern compromised
Cline's npm package for about eight hours.

| Rule | Step in that chain |
|---|---|
| `/proc/self/environ`, `env`, `printenv` | reading the process environment |
| credential variable names in commands | exfiltrating what was read |
| `.env`, `*.pem`, `id_rsa`, `.netrc` | reading secrets at rest |
| writes outside the project directory | persistence |
| egress to non-allowlisted hosts | getting the data out |

## Reading it on a slide

The contract is small. Deny by writing one JSON object and exiting 2:

```python
{"hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "...shown to the model..."}}
```

Exit 0 means "no opinion, carry on with the normal permission flow". Only exit 2
blocks.

## Things to get right

- **Fail open on malformed input.** A hook that crashes on unexpected JSON blocks
  all work. There is a test for this.
- **A timed-out `PreToolUse` hook does not block.** Keep it fast; this one is
  pure stdlib and has a 10-second timeout.
- **Say why in the reason.** It goes to the model, and a good reason lets the
  agent find a legitimate route instead of retrying the blocked one.
- **This is not a sandbox.** It is one layer. OS-level sandboxing, network egress
  filtering and not giving the agent credentials in the first place are the
  others — the CSA's own recommendation is to separate the reasoning layer from
  anything holding credentials.
- **You can measure it.** Every decision emits `claude_code.tool_decision` with
  `decision_source: hook`, which is the one directly instrumentable risk metric
  in GitLab's governance framework. See snippet F.
