"""The branch-to-merge join is the whole point of this snippet, so it is tested.

Building the fixture needs a git repository with a real merge commit and a
transcript whose working directory sits inside it — a combination that is
awkward to arrange live, so it is constructed here.
"""

import json
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCRIPT = Path(__file__).with_name("cost_per_pr.py")


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True, text=True, check=True,
        env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@e",
             "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@e", "PATH": "/usr/bin:/bin"},
    ).stdout


def build_repo(root: Path) -> Path:
    repo = root / "service"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    (repo / "app.py").write_text("x = 1\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "initial")

    git(repo, "checkout", "-q", "-b", "add-tax-rules")
    (repo / "app.py").write_text("x = 1\ny = 2\nz = 3\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "add tax rules")

    git(repo, "checkout", "-q", "main")
    git(repo, "merge", "--no-ff", "-q", "add-tax-rules",
        "-m", "Merge pull request #42 from acme/add-tax-rules")
    return repo


def build_transcript(projects: Path, repo: Path, branch: str, turns: int) -> None:
    project_dir = projects / "-service"
    project_dir.mkdir(parents=True)
    started = datetime.now(timezone.utc)
    lines = []
    for index in range(turns):
        lines.append(json.dumps({
            "type": "assistant",
            "cwd": str(repo),
            "gitBranch": branch,
            "timestamp": (started + timedelta(minutes=index)).isoformat().replace("+00:00", "Z"),
            "message": {
                "model": "claude-opus-5",
                "usage": {
                    "input_tokens": 100,
                    "output_tokens": 2_000,
                    "cache_read_input_tokens": 200_000,
                    "cache_creation": {"ephemeral_1h_input_tokens": 10_000,
                                       "ephemeral_5m_input_tokens": 0},
                },
            },
        }))
    (project_dir / "session-1.jsonl").write_text("\n".join(lines) + "\n")


def run(repo: Path, projects: Path, *extra: str) -> str:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--repo", str(repo), "--projects-dir", str(projects), *extra],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_joins_branch_spend_to_the_merge_commit():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        repo = build_repo(root)
        projects = root / "projects"
        build_transcript(projects, repo, "add-tax-rules", turns=10)

        output = run(repo, projects)

        assert "#42" in output, output
        assert "add-tax-rules" in output, output
        assert "1 merges, 1 with attributable agent spend" in output, output


def test_reports_unattributable_merges_honestly():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        repo = build_repo(root)
        projects = root / "projects"
        build_transcript(projects, repo, "some-other-branch", turns=3)

        output = run(repo, projects)

        assert "1 merges, 0 with attributable agent spend" in output, output
        assert "invisible here" in output, output


def test_branch_view_needs_no_merges():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        repo = build_repo(root)
        projects = root / "projects"
        build_transcript(projects, repo, "add-tax-rules", turns=5)

        output = run(repo, projects, "--by-branch")

        assert "add-tax-rules" in output
        assert "across 1 branches" in output


def test_counts_nested_subagent_transcripts():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        repo = build_repo(root)
        projects = root / "projects"
        build_transcript(projects, repo, "add-tax-rules", turns=2)

        nested = projects / "-service" / "session-1" / "subagents"
        nested.mkdir(parents=True)
        payload = (projects / "-service" / "session-1.jsonl").read_text()
        (nested / "agent-abc.jsonl").write_text(payload)

        output = run(repo, projects, "--by-branch")
        row = next(line for line in output.splitlines() if line.startswith("add-tax-rules"))
        _, cost, sessions, turns, _days = row.split()

        # Two main turns plus two subagent turns: nested transcripts must be counted.
        assert int(turns) == 4, row
        assert int(sessions) == 2, row
        assert float(cost) > 0, row
