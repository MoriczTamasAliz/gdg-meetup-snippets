"""PreToolUse hook: refuse tool calls that instructions alone cannot prevent.

A line in CLAUDE.md saying "never read secrets" is a suggestion to a
probabilistic system, and it sits in the same context window as whatever the
agent just read from an issue body or a dependency README. This is a rule: it
runs before the tool does, and exit code 2 stops the call.

The rules below mirror the kill chain in CVE-2025-66032, where a prompt
injected through a GitHub issue persuaded a coding agent in CI to dump its own
environment, and the extracted OIDC token was exchanged for write access.

Wire it up in .claude/settings.json:

    {"hooks": {"PreToolUse": [{"matcher": "Bash|Read|Edit|Write",
      "hooks": [{"type": "command",
                 "command": "python3 $CLAUDE_PROJECT_DIR/snippets/c-guardrails/guard.py"}]}]}}
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SECRET_FILENAMES = {".env", ".netrc", ".pgpass", "credentials", "id_rsa", "id_ed25519"}
SECRET_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".keystore"}

# Reading the process environment is step three of the CVE-2025-66032 chain.
ENVIRONMENT_DUMP = re.compile(
    r"/proc/(self|\d+)/environ|(^|[;&|`(\s])(env|printenv|set)(\s|$)", re.MULTILINE
)

CREDENTIAL_IN_COMMAND = re.compile(
    r"(AWS_SECRET|ANTHROPIC_API_KEY|GITHUB_TOKEN|GH_TOKEN|OPENAI_API_KEY"
    r"|PRIVATE_KEY|PASSWORD|SECRET_KEY)",
    re.IGNORECASE,
)

NETWORK_COMMAND = re.compile(r"(^|[;&|`(\s])(curl|wget|nc|ncat|scp|sftp|rsync)(\s|$)")
ALLOWED_HOSTS = {"pypi.org", "files.pythonhosted.org", "github.com", "api.github.com"}
HOST_IN_URL = re.compile(r"https?://([^/\s\"']+)")


def deny(reason: str) -> None:
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        },
        sys.stdout,
    )
    sys.stdout.write("\n")
    sys.exit(2)


def allow() -> None:
    sys.stdout.write("{}\n")
    sys.exit(0)


def looks_secret(path_text: str) -> bool:
    path = Path(path_text)
    if path.name in SECRET_FILENAMES or path.suffix in SECRET_SUFFIXES:
        return True
    return path.name.startswith(".env")


def check_file_access(tool_name: str, tool_input: dict, project_dir: Path) -> None:
    raw_path = tool_input.get("file_path") or tool_input.get("notebook_path")
    if not raw_path:
        return

    if looks_secret(raw_path):
        deny(f"{raw_path} looks like a credential file. Blocked by the project guardrail hook.")

    if tool_name in {"Edit", "Write", "NotebookEdit"}:
        try:
            resolved = Path(raw_path).resolve()
            resolved.relative_to(project_dir.resolve())
        except (ValueError, OSError):
            deny(
                f"Writing to {raw_path} would leave the project directory "
                f"({project_dir}). Blocked by the project guardrail hook."
            )


def check_command(command: str) -> None:
    if ENVIRONMENT_DUMP.search(command):
        deny(
            "This command reads the process environment, which is how a prompt "
            "injection exfiltrates credentials (see CVE-2025-66032). Blocked by "
            "the project guardrail hook."
        )

    if CREDENTIAL_IN_COMMAND.search(command):
        deny("This command references a credential variable by name. Blocked by the project guardrail hook.")

    for name in SECRET_FILENAMES:
        if re.search(rf"(^|[\s/'\"]){re.escape(name)}(\s|$|['\"])", command):
            deny(f"This command touches {name}. Blocked by the project guardrail hook.")

    if NETWORK_COMMAND.search(command):
        hosts = set(HOST_IN_URL.findall(command))
        disallowed = {h for h in hosts if h.split(":")[0] not in ALLOWED_HOSTS}
        if disallowed or not hosts:
            target = ", ".join(sorted(disallowed)) or "an unspecified host"
            deny(
                f"Outbound network call to {target}. Egress is limited to "
                f"{', '.join(sorted(ALLOWED_HOSTS))}. Blocked by the project guardrail hook."
            )


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        allow()

    tool_name = event.get("tool_name", "")
    tool_input = event.get("tool_input") or {}
    project_dir = Path(event.get("cwd") or ".")

    check_file_access(tool_name, tool_input, project_dir)

    if tool_name == "Bash":
        check_command(tool_input.get("command", ""))

    allow()


if __name__ == "__main__":
    main()
