"""Fail-closed deterministic publication gate with opt-in independent reviews."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Literal, Protocol, cast

import yaml
from jsonschema import Draft202012Validator

from cmp.tools.documentation_impact import git_changed_paths, verify_documentation_impact
from cmp.tools.user_guide import verify_user_guide

ReviewKind = Literal["code", "visual"]
CommandKind = Literal["ordinary", "commit", "publish", "commit-and-publish"]

_CODE_PROMPT = "docs/14-testing/review-prompts/code-review.md"
_VISUAL_PROMPT = "docs/14-testing/review-prompts/visual-review.md"
_CODE_SCHEMA = "contracts/review/code-review.schema.json"
_VISUAL_SCHEMA = "contracts/review/visual-review.schema.json"
_SCREENSHOT_MANIFEST = "docs/user-guide/screenshot-manifest.yaml"
_CURRENT_IMAGE_PREFIX = "docs/user-guide/images/current/"
_CACHE_VERSION = 2
_ROUTINE_CODE_TIMEOUT_SECONDS = 120
_FINAL_CODE_TIMEOUT_SECONDS = 300
_VISUAL_TIMEOUT_SECONDS = 300
_ROUTINE_CODE_MAX_TOKENS = 50_000
_FINAL_CODE_MAX_TOKENS = 50_000
_VISUAL_MAX_TOKENS = 40_000
_MAX_EMBEDDED_REVIEW_BYTES = 400_000
_TOKEN_USAGE = re.compile(r"tokens used\s+([\d,]+)", re.IGNORECASE)
_TEST_DECLARATION = re.compile(
    r"^\s*(?:async\s+)?def\s+(test_[A-Za-z0-9_]+)|"
    r"^\s*(?:it|test)\(\s*[\"'`]([^\"'`]+)"
)

_SHELL_VALUE = r'(?:"[^\"]*"|\'[^\']*\'|\S+)'
_GIT_EXECUTABLE = (
    r'(?:"(?:[^\"]*[\\/])?git(?:\.exe)?"|'
    r"'(?:[^']*[\\/])?git(?:\.exe)?'|(?:\S*[\\/])?git(?:\.exe)?)"
)
_GH_EXECUTABLE = (
    r'(?:"(?:[^\"]*[\\/])?gh(?:\.exe)?"|'
    r"'(?:[^']*[\\/])?gh(?:\.exe)?'|(?:\S*[\\/])?gh(?:\.exe)?)"
)
_GIT_FLAG = (
    rf"(?:(?:-C|-c)(?:{_SHELL_VALUE}|\s+{_SHELL_VALUE})|"
    rf"(?:--git-dir|--work-tree|--namespace|--config-env)\s+{_SHELL_VALUE}|"
    rf"(?:--git-dir|--work-tree|--namespace|--config-env|--exec-path)={_SHELL_VALUE}|"
    r"-p|-P|--paginate|--no-pager|--no-replace-objects|--bare|--literal-pathspecs|"
    r"--glob-pathspecs|--noglob-pathspecs|--icase-pathspecs|--no-optional-locks|"
    r"--no-lazy-fetch)"
)
_GH_FLAG = (
    rf"(?:(?:--repo|-R|--hostname)\s+{_SHELL_VALUE}|"
    rf"(?:--repo|--hostname)={_SHELL_VALUE})"
)
_GIT = rf"{_GIT_EXECUTABLE}(?:\s+{_GIT_FLAG})*"
_GH = rf"{_GH_EXECUTABLE}(?:\s+{_GH_FLAG})*"
_GH_PR = rf"{_GH}\s+pr(?:\s+{_GH_FLAG})*"
_ASSIGNMENT = rf"[A-Za-z_][A-Za-z0-9_]*={_SHELL_VALUE}"
_ENV_WRAPPER = (
    rf"env(?:\s+(?:{_ASSIGNMENT}|-i|--ignore-environment|-u\s+{_SHELL_VALUE}|"
    rf"--unset={_SHELL_VALUE}))*\s+"
)
_SUDO_WRAPPER = (
    rf"sudo(?:\s+(?:-E|-H|-n|-S|-k|-K|-b|--non-interactive|"
    rf"--preserve-env(?:={_SHELL_VALUE})?|-u\s+{_SHELL_VALUE}|"
    rf"--user={_SHELL_VALUE}))*\s+"
)
_COMMAND_PREFIX = (
    rf"(?:{_ASSIGNMENT}\s+)*(?:(?:{_ENV_WRAPPER}|command(?:\s+--)?\s+|{_SUDO_WRAPPER}))*"
)
_COMMAND_BOUNDARY = r"(?:^[ \t]*|[;&|(){}\r\n]\s*)"
_COMMAND_START = rf"{_COMMAND_BOUNDARY}{_COMMAND_PREFIX}"
_COMMIT = re.compile(rf"{_COMMAND_START}{_GIT}\s+commit\b", re.IGNORECASE)
_PUBLISH = re.compile(
    rf"{_COMMAND_START}(?:{_GIT}\s+push\b|"
    rf"{_GH_PR}\s+(?:create|ready|merge)\b)",
    re.IGNORECASE,
)
_PR_OPERATION = re.compile(
    rf"{_COMMAND_START}(?P<cli>{_GH_PR})\s+"
    r"(?P<action>create|ready|merge)\b(?P<arguments>[^;&|\r\n]*)",
    re.IGNORECASE,
)
_GIT_PUSH_OPERATION = re.compile(
    rf"{_COMMAND_START}(?P<cli>{_GIT})\s+push\b(?P<arguments>[^;&|\r\n]*)",
    re.IGNORECASE,
)
_NESTED_LAUNCHER = re.compile(
    r"(?:^|[;&|(){}\r\n]\s*)(?:bash|sh|zsh|cmd(?:\.exe)?|powershell(?:\.exe)?|"
    r"pwsh(?:\.exe)?|Start-Process)\b",
    re.IGNORECASE,
)
_LOOSE_COMMIT = re.compile(r"\bgit(?:\.exe)?\b.*\bcommit\b", re.IGNORECASE | re.DOTALL)
_LOOSE_PUBLISH = re.compile(
    r"(?:\bgit(?:\.exe)?\b.*\bpush\b|"
    r"\bgh(?:\.exe)?\b.*\bpr\b.*\b(?:create|ready|merge)\b)",
    re.IGNORECASE | re.DOTALL,
)

_VISUAL_REVIEW_INPUTS = (
    "AGENTS.md",
    "docs/01-product/desktop-engineering-ui-product-spec.md",
    "docs/01-product/desktop-engineering-ui-tooling.md",
    "docs/01-product/visual-acceptance-matrix.md",
    "docs/00-research/ux-reference-gallery/README.md",
    "docs/00-research/images/gui-reference/README.md",
)
_HARD_GATE_CRITERIA = {
    "V-01",
    "V-02",
    "V-03",
    "V-04",
    "V-06",
    "V-08",
    "V-09",
    "V-10",
    "V-12",
    "V-13",
    "V-15",
    "V-16",
}


class PrePublishError(RuntimeError):
    """Raised when the pre-publish command must be blocked."""

    def __init__(self, message: str, detail_path: Path | None = None) -> None:
        super().__init__(message)
        self.detail_path = detail_path


@dataclass(frozen=True, slots=True)
class ChangeSet:
    base_ref: str
    base_sha: str
    merge_base_sha: str
    head_sha: str
    diff_hash: str
    changed_files: tuple[str, ...]
    ui_impact_files: tuple[str, ...]
    current_images: tuple[Path, ...]
    deleted_current_images: tuple[str, ...]
    image_hashes: Mapping[str, str]
    reference_images: tuple[Path, ...]
    reference_image_hashes: Mapping[str, str]

    @property
    def requires_visual_review(self) -> bool:
        return bool(self.ui_impact_files)


@dataclass(frozen=True, slots=True)
class PublicationTarget:
    action: str
    selector: str
    hostname: str
    repository: str
    head_sha: str
    base_sha: str
    base_ref: str


@dataclass(frozen=True, slots=True)
class ReviewProfile:
    name: str
    model: str
    reasoning_effort: str
    timeout_seconds: int
    max_tokens: int


_ROUTINE_CODE_PROFILE = ReviewProfile(
    name="routine-code",
    model="gpt-5.6-terra",
    reasoning_effort="medium",
    timeout_seconds=_ROUTINE_CODE_TIMEOUT_SECONDS,
    max_tokens=_ROUTINE_CODE_MAX_TOKENS,
)
_FINAL_CODE_PROFILE = ReviewProfile(
    name="final-code",
    model="gpt-5.6-sol",
    reasoning_effort="high",
    timeout_seconds=_FINAL_CODE_TIMEOUT_SECONDS,
    max_tokens=_FINAL_CODE_MAX_TOKENS,
)
_VISUAL_PROFILE = ReviewProfile(
    name="visual",
    model="gpt-5.6-sol",
    reasoning_effort="high",
    timeout_seconds=_VISUAL_TIMEOUT_SECONDS,
    max_tokens=_VISUAL_MAX_TOKENS,
)


@dataclass(frozen=True, slots=True)
class ReviewRequest:
    kind: ReviewKind
    project: Path
    prompt: str
    schema_path: Path
    result_path: Path
    log_path: Path
    images: tuple[Path, ...] = ()
    profile: ReviewProfile = _ROUTINE_CODE_PROFILE


class ReviewerRunner(Protocol):
    @property
    def settings(self) -> Mapping[str, object]: ...

    def run(self, request: ReviewRequest) -> None: ...


ProcessRunner = Callable[..., subprocess.CompletedProcess[str]]
DocumentCheck = Callable[[Path], None]
DeterministicCheck = Callable[[Path, ChangeSet], None]
WhitespaceCheck = Callable[[Path, ChangeSet], None]
ChangeCollector = Callable[[Path], ChangeSet]
WorktreeReader = Callable[[Path], bytes]
Emitter = Callable[[str], None]


def classify_command(command: str) -> CommandKind:
    """Classify the shell command without running review for unrelated commands."""

    commit = bool(_COMMIT.search(command))
    publish = bool(_PUBLISH.search(command))
    if _has_nested_shell_context(command):
        commit = commit or bool(_LOOSE_COMMIT.search(command))
        publish = publish or bool(_LOOSE_PUBLISH.search(command))
    if commit and publish:
        return "commit-and-publish"
    if publish:
        return "publish"
    if commit:
        return "commit"
    return "ordinary"


def _has_nested_shell_context(command: str) -> bool:
    return bool(_NESTED_LAUNCHER.search(command)) or "`" in command


def _pr_selector(arguments: str) -> str:
    try:
        tokens = shlex.split(arguments, posix=True)
    except ValueError as error:
        raise PrePublishError(f"cannot parse GitHub PR command: {error}") from error
    options_with_values = {
        "--author-email",
        "--body",
        "--body-file",
        "--match-head-commit",
        "--repo",
        "--subject",
        "--title",
        "-F",
        "-R",
        "-b",
        "-t",
    }
    skip_value = False
    for token in tokens:
        if skip_value:
            skip_value = False
            continue
        if token in options_with_values:
            skip_value = True
            continue
        if token.startswith("-"):
            continue
        return token
    return ""


def _pr_repository(cli: str) -> str:
    try:
        tokens = shlex.split(cli, posix=True)
    except ValueError as error:
        raise PrePublishError(f"cannot parse GitHub CLI options: {error}") from error
    for index, token in enumerate(tokens):
        if token in {"--repo", "-R"}:
            if index + 1 >= len(tokens):
                raise PrePublishError("GitHub --repo option has no value")
            return tokens[index + 1]
        if token.startswith("--repo="):
            return token.split("=", 1)[1]
    return ""


def _option_value(command: str, names: set[str]) -> str | None:
    try:
        tokens = shlex.split(command, posix=True)
    except ValueError as error:
        raise PrePublishError(f"cannot parse GitHub CLI options: {error}") from error
    for index, token in enumerate(tokens):
        if token in names:
            if index + 1 >= len(tokens):
                raise PrePublishError(f"GitHub {token} option has no value")
            return tokens[index + 1]
        for name in names:
            if name.startswith("--") and token.startswith(name + "="):
                return token.split("=", 1)[1]
    return None


def _origin_repository(project: Path) -> str:
    remote = _git_text(project, ("remote", "get-url", "origin"))
    match = re.search(r"github\.com[/:]([^/]+)/([^/]+?)(?:\.git)?$", remote, re.IGNORECASE)
    if match is None:
        raise PrePublishError("origin is not a supported GitHub repository URL")
    return f"{match.group(1)}/{match.group(2)}"


def _publication_snapshot(project: Path) -> tuple[str, str, str, str]:
    repository = _origin_repository(project)
    base_sha = _git_text(project, ("rev-parse", "--verify", "origin/main"))
    remote_main = _git_text(
        project,
        ("ls-remote", "--exit-code", "origin", "refs/heads/main"),
    ).split()[0]
    if remote_main != base_sha:
        raise PrePublishError(
            "origin/main is stale relative to GitHub; fetch main before publication"
        )
    head_sha = _git_text(project, ("rev-parse", "--verify", "HEAD"))
    return repository, base_sha, head_sha, "github.com"


def _resolve_create_target(project: Path, match: re.Match[str]) -> PublicationTarget:
    operation = match.group(0)
    explicit_head = _option_value(operation, {"--head", "-H"})
    if explicit_head is not None:
        raise PrePublishError(
            "gh pr create with --head/-H is not allowed; check out the intended head and create "
            "the PR without an explicit head"
        )
    explicit_base = _option_value(operation, {"--base", "-B"})
    if explicit_base is None:
        raise PrePublishError("gh pr create must explicitly specify --base main")
    if explicit_base != "main":
        raise PrePublishError("gh pr create base must be main")
    repository = _pr_repository(operation)
    current_repository, base_sha, head_sha, hostname = _publication_snapshot(project)
    if repository and repository.lower() != current_repository.lower():
        raise PrePublishError("gh pr create --repo must name the current origin repository")
    return PublicationTarget(
        action="create",
        selector="current-branch",
        hostname=hostname,
        repository=current_repository,
        head_sha=head_sha,
        base_sha=base_sha,
        base_ref="main",
    )


def _resolve_git_push_target(
    project: Path, command: str, match: re.Match[str]
) -> PublicationTarget:
    if re.search(r"\b(?:cd|Set-Location|Push-Location)\b", command, re.IGNORECASE):
        raise PrePublishError("directory-changing wrappers are not allowed around git push")
    if re.search(
        r"(?:^|\s)(?:(?:-C|-c)(?:\S*|$)|"
        r"(?:--git-dir|--work-tree|--namespace|--config-env|--exec-path|--bare)"
        r"(?:\s|=|$))",
        match.group("cli"),
        re.IGNORECASE,
    ) or re.search(r"\bGIT_[A-Za-z0-9_]*\s*=", command, re.IGNORECASE):
        raise PrePublishError(
            "git push repository-selection options are not allowed; run from the reviewed root"
        )
    try:
        tokens = shlex.split(match.group("arguments"), posix=True)
    except ValueError as error:
        raise PrePublishError(f"cannot parse git push arguments: {error}") from error
    allowed_flags = {"-u", "--set-upstream", "--porcelain", "--progress"}
    positional: list[str] = []
    for token in tokens:
        if token in allowed_flags:
            continue
        if token.startswith("-"):
            raise PrePublishError(f"unsupported git push option for exact binding: {token}")
        positional.append(token)
    branch = _git_text(project, ("symbolic-ref", "--quiet", "--short", "HEAD"))
    if len(positional) != 2 or positional[0] != "origin":
        raise PrePublishError(
            "git push must explicitly name exactly `origin` and the checked-out branch"
        )
    allowed_refspecs = {
        branch,
        f"refs/heads/{branch}",
        f"{branch}:{branch}",
        f"HEAD:{branch}",
        f"HEAD:refs/heads/{branch}",
    }
    if positional[1] not in allowed_refspecs:
        raise PrePublishError("git push refspec does not identify the reviewed checked-out branch")
    repository, base_sha, head_sha, hostname = _publication_snapshot(project)
    return PublicationTarget(
        action="push",
        selector=branch,
        hostname=hostname,
        repository=repository,
        head_sha=head_sha,
        base_sha=base_sha,
        base_ref="main",
    )


def resolve_publication_target(
    project: Path,
    command: str,
    *,
    process_runner: ProcessRunner = subprocess.run,
) -> PublicationTarget | None:
    """Resolve a ready/merge target so an unrelated local HEAD cannot authorize it."""

    if _has_nested_shell_context(command) and _LOOSE_PUBLISH.search(command):
        raise PrePublishError(
            "nested shell/process publication commands are not allowed; run the protected "
            "git or gh command directly"
        )
    pr_matches = list(_PR_OPERATION.finditer(command))
    push_matches = list(_GIT_PUSH_OPERATION.finditer(command))
    if not pr_matches and not push_matches:
        return None
    if len(pr_matches) + len(push_matches) != 1:
        raise PrePublishError("run one publication operation at a time")
    if push_matches:
        return _resolve_git_push_target(project, command, push_matches[0])
    if re.search(r"(?:GH_REPO|GH_HOST)\s*=", command, re.IGNORECASE):
        raise PrePublishError(
            "command-local GH_REPO/GH_HOST overrides are not allowed for PR publication"
        )
    if os.environ.get("GH_REPO") or os.environ.get("GH_HOST"):
        raise PrePublishError("ambient GH_REPO/GH_HOST must be unset before PR publication")
    match = pr_matches[0]
    if match.group("action").lower() == "create":
        return _resolve_create_target(project, match)
    selector = _pr_selector(match.group("arguments"))
    repository = _pr_repository(match.group(0))
    current_repository = _origin_repository(project)
    if repository and repository.lower() != current_repository.lower():
        raise PrePublishError("target PR repository must match the current origin repository")
    hostname = _option_value(match.group(0), {"--hostname"})
    if hostname is not None and hostname.lower() != "github.com":
        raise PrePublishError("target PR hostname must match the current origin hostname")
    repository = current_repository
    invocation = ["gh", "pr", "view"]
    if selector:
        invocation.append(selector)
    invocation.extend(("--repo", repository))
    invocation.extend(("--json", "headRefOid,baseRefOid,baseRefName,url"))
    try:
        completed = process_runner(
            invocation,
            cwd=project,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise PrePublishError(f"cannot resolve GitHub PR publication target: {error}") from error
    if completed.returncode != 0:
        detail = (completed.stderr or "").strip().splitlines()
        raise PrePublishError(
            "cannot resolve GitHub PR publication target" + (f": {detail[-1]}" if detail else "")
        )
    try:
        payload = json.loads(completed.stdout or "")
        head_sha = payload["headRefOid"]
        base_sha = payload["baseRefOid"]
        base_ref = payload["baseRefName"]
        url = payload["url"]
    except (json.JSONDecodeError, KeyError, TypeError) as error:
        raise PrePublishError("GitHub PR target result is missing required SHAs") from error
    if not all(isinstance(value, str) and value for value in (head_sha, base_sha, base_ref, url)):
        raise PrePublishError("GitHub PR target result contains invalid SHAs")
    expected_url = f"https://github.com/{repository}/pull/"
    if not url.lower().startswith(expected_url.lower()):
        raise PrePublishError("target PR URL does not match the current origin repository")
    return PublicationTarget(
        action=match.group("action").lower(),
        selector=selector or "current-branch",
        hostname="github.com",
        repository=repository,
        head_sha=head_sha,
        base_sha=base_sha,
        base_ref=base_ref,
    )


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git(
    project: Path,
    arguments: Sequence[str],
    *,
    text: bool = False,
    check: bool = True,
) -> subprocess.CompletedProcess[Any]:
    try:
        return subprocess.run(
            ["git", *arguments],
            cwd=project,
            check=check,
            capture_output=True,
            text=text,
        )
    except (OSError, subprocess.CalledProcessError) as error:
        stderr = getattr(error, "stderr", b"")
        if isinstance(stderr, bytes):
            detail = stderr.decode("utf-8", errors="replace").strip()
        else:
            detail = str(stderr).strip()
        raise PrePublishError(
            f"git {' '.join(arguments)} failed" + (f": {detail}" if detail else "")
        ) from error


def _git_text(project: Path, arguments: Sequence[str]) -> str:
    return str(_git(project, arguments, text=True).stdout).strip()


def _git_bytes(project: Path, arguments: Sequence[str]) -> bytes:
    return bytes(_git(project, arguments).stdout)


def _repository_root(seed: Path) -> Path:
    return Path(_git_text(seed.resolve(), ("rev-parse", "--show-toplevel"))).resolve()


def _worktree_state(project: Path) -> bytes:
    return _git_bytes(
        project,
        ("status", "--porcelain=v1", "-z", "--untracked-files=all"),
    )


def _is_ui_impact(path: str) -> bool:
    pure = PurePosixPath(path)
    suffix = pure.suffix.lower()
    name = pure.name.lower()
    if ".test." in name or ".spec." in name or "__tests__" in pure.parts:
        return False
    if path.startswith("apps/web/") and suffix in {".tsx", ".css"}:
        return True
    return suffix in {".ts", ".tsx", ".css"} and (
        path.startswith("apps/web/src/design/") or path.startswith("apps/web/src/components/")
    )


def _manifest_capture_index(project: Path) -> dict[Path, tuple[int, int]]:
    manifest_path = project / _SCREENSHOT_MANIFEST
    try:
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise PrePublishError(f"cannot read current screenshot manifest: {error}") from error
    if not isinstance(manifest, dict) or not isinstance(manifest.get("captures"), list):
        raise PrePublishError("current screenshot manifest has no captures list")
    captures: dict[Path, tuple[int, int]] = {}
    for entry in manifest["captures"]:
        if (
            not isinstance(entry, dict)
            or not isinstance(entry.get("image"), str)
            or not isinstance(entry.get("width"), int)
            or not isinstance(entry.get("height"), int)
        ):
            raise PrePublishError("current screenshot manifest contains an invalid image entry")
        image = (manifest_path.parent / entry["image"]).resolve()
        try:
            image.relative_to(project)
        except ValueError as error:
            raise PrePublishError(f"screenshot escapes the repository: {image}") from error
        if image in captures:
            raise PrePublishError(f"current screenshot manifest repeats an image: {image}")
        captures[image] = (entry["width"], entry["height"])
    return captures


def _manifest_current_images(project: Path) -> tuple[Path, ...]:
    return tuple(sorted(_manifest_capture_index(project)))


def _reference_images(project: Path, current_images: Sequence[Path]) -> tuple[Path, ...]:
    names = " ".join(path.name.lower() for path in current_images)
    reference_root = project / "docs/00-research/images/gui-reference"
    selected: set[Path] = set()
    if any(token in names for token in ("material", "browse", "administration")):
        selected.update(reference_root.glob("granta-*.png"))
    if "modeling" in names:
        selected.update(reference_root.glob("modeler-*.png"))
    if "activity" in names:
        selected.add(reference_root / "granta-list-results.png")
    if not selected:
        selected.update(reference_root.glob("*.png"))
    return tuple(sorted(path.resolve() for path in selected if path.is_file()))


def collect_change_set(project: Path) -> ChangeSet:
    """Collect the exact committed origin/main...HEAD review input."""

    root = _repository_root(project)
    dirty = _worktree_state(root)
    if dirty:
        rendered = dirty.replace(b"\0", b"\n").decode("utf-8", errors="replace").strip()
        raise PrePublishError(
            "pre-publish review requires a clean worktree so the reviewer sees committed bytes: "
            f"{rendered}"
        )
    base_ref = "origin/main"
    base_sha = _git_text(root, ("rev-parse", "--verify", base_ref))
    head_sha = _git_text(root, ("rev-parse", "--verify", "HEAD"))
    merge_base_sha = _git_text(root, ("merge-base", base_ref, "HEAD"))
    diff = _git_bytes(root, ("diff", "--binary", "--full-index", f"{base_ref}...HEAD"))
    if not diff:
        raise PrePublishError(f"there is no committed diff to review against {base_ref}")
    changed = tuple(sorted(git_changed_paths(root, [f"{base_ref}...HEAD"])))
    ui_files = tuple(path for path in changed if _is_ui_impact(path))
    changed_current_paths = tuple(
        path
        for path in changed
        if path.startswith(_CURRENT_IMAGE_PREFIX) and path.lower().endswith(".png")
    )
    changed_current = tuple(
        (root / path).resolve() for path in changed_current_paths if (root / path).is_file()
    )
    deleted_current = tuple(path for path in changed_current_paths if not (root / path).is_file())
    current_images = changed_current
    if ui_files and not current_images:
        current_images = _manifest_current_images(root)
    for image in current_images:
        if not image.is_file():
            raise PrePublishError(f"visual review image is missing: {image.relative_to(root)}")
    references = _reference_images(root, current_images) if ui_files else ()
    image_hashes = {
        image.relative_to(root).as_posix(): _sha256_file(image) for image in current_images
    }
    reference_hashes = {
        image.relative_to(root).as_posix(): _sha256_file(image) for image in references
    }
    return ChangeSet(
        base_ref=base_ref,
        base_sha=base_sha,
        merge_base_sha=merge_base_sha,
        head_sha=head_sha,
        diff_hash=_sha256_bytes(diff),
        changed_files=changed,
        ui_impact_files=ui_files,
        current_images=current_images,
        deleted_current_images=deleted_current,
        image_hashes=image_hashes,
        reference_images=references,
        reference_image_hashes=reference_hashes,
    )


def _default_documentation_check(project: Path) -> None:
    verify_documentation_impact(project, "range")


def _default_whitespace_check(project: Path, change: ChangeSet) -> None:
    """Reject committed whitespace errors without changing repository state."""

    diff_check = _git(
        project,
        ("diff", "--check", f"{change.base_ref}...HEAD"),
        text=True,
        check=False,
    )
    if diff_check.returncode != 0:
        raise PrePublishError(f"git diff --check failed: {str(diff_check.stdout).strip()}")


def _default_deterministic_check(project: Path, _change: ChangeSet) -> None:
    verify_user_guide(project)


def _asset_hashes(asset_root: Path) -> dict[str, str]:
    assets = (_CODE_PROMPT, _VISUAL_PROMPT, _CODE_SCHEMA, _VISUAL_SCHEMA)
    hashes: dict[str, str] = {}
    for relative in assets:
        path = asset_root / relative
        if not path.is_file():
            raise PrePublishError(f"review asset is missing: {relative}")
        hashes[relative] = _sha256_file(path)
    return hashes


def _fingerprint_inputs(
    change: ChangeSet,
    asset_hashes: Mapping[str, str],
    reviewer_settings: Mapping[str, object],
    publication_target: PublicationTarget | None = None,
) -> dict[str, object]:
    target = None
    if publication_target is not None:
        target = {
            "hostname": publication_target.hostname,
            "repository": publication_target.repository,
            "head_sha": publication_target.head_sha,
            "base_sha": publication_target.base_sha,
            "base_ref": publication_target.base_ref,
        }
    return {
        "cache_version": _CACHE_VERSION,
        "base_ref": change.base_ref,
        "base_sha": change.base_sha,
        "merge_base_sha": change.merge_base_sha,
        "head_sha": change.head_sha,
        "diff_hash": change.diff_hash,
        "changed_files": list(change.changed_files),
        "ui_impact_files": list(change.ui_impact_files),
        "review_assets": dict(sorted(asset_hashes.items())),
        "current_screenshot_hashes": dict(sorted(change.image_hashes.items())),
        "deleted_current_images": list(change.deleted_current_images),
        "reference_image_hashes": dict(sorted(change.reference_image_hashes.items())),
        "reviewer_settings": dict(sorted(reviewer_settings.items())),
        "publication_target": target,
    }


def _fingerprint(inputs: Mapping[str, object]) -> str:
    encoded = json.dumps(inputs, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return _sha256_bytes(encoded.encode("utf-8"))


def _load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PrePublishError(f"review result is missing or invalid JSON: {error}", path) from error


def _validate_result(kind: ReviewKind, result_path: Path, schema_path: Path) -> dict[str, Any]:
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise PrePublishError(f"review schema is unreadable: {error}", schema_path) from error
    result = _load_json(result_path)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(result),
        key=lambda error: tuple(str(part) for part in error.absolute_path),
    )
    if errors:
        rendered = "; ".join(error.message for error in errors[:5])
        raise PrePublishError(f"{kind} review result violates its schema: {rendered}", result_path)
    document = cast(dict[str, Any], result)
    if document["verdict"] == "NEEDS_CHANGES":
        has_required_finding = bool(document["findings"])
        if kind == "visual":
            has_required_finding = has_required_finding or bool(document["hard_gate_violations"])
        if not has_required_finding:
            raise PrePublishError(
                f"{kind} review returned NEEDS_CHANGES without a concrete finding", result_path
            )
    if document["verdict"] == "PASS" and any(
        finding["severity"] in {"blocking", "high"} for finding in document["findings"]
    ):
        raise PrePublishError(
            f"{kind} review returned PASS with a blocking/high finding", result_path
        )
    if kind == "visual" and document["verdict"] == "PASS":
        for screen in document["screens"]:
            criterion_ids = [item["id"] for item in screen["criteria"]]
            expected_ids = [f"V-{index:02d}" for index in range(1, 17)]
            score_total = sum(item["score"] for item in screen["criteria"])
            if sorted(criterion_ids) != expected_ids or score_total != screen["total_score"]:
                raise PrePublishError(
                    "visual review returned incomplete or inconsistent V-01 through V-16 scores",
                    result_path,
                )
            if screen["total_score"] < 28 or not screen["hard_gate_pass"]:
                raise PrePublishError(
                    "visual review returned PASS below the authoritative 28/32 hard-gate threshold",
                    result_path,
                )
            scores = {item["id"]: item["score"] for item in screen["criteria"]}
            if any(scores[criterion] == 0 for criterion in _HARD_GATE_CRITERIA):
                raise PrePublishError(
                    "visual review returned PASS with a zero authoritative hard-gate score",
                    result_path,
                )
        if document["hard_gate_violations"]:
            raise PrePublishError(
                "visual review returned PASS with hard-gate violations", result_path
            )
    return document


def _atomic_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def _cached_pass(
    review_dir: Path,
    fingerprint: str,
    inputs: Mapping[str, object],
    asset_root: Path,
    visual_required: bool,
) -> bool:
    marker = review_dir / "pass.json"
    metadata = review_dir / "inputs.json"
    if not marker.is_file() or not metadata.is_file():
        return False
    try:
        if _load_json(metadata) != inputs:
            return False
        marker_data = _load_json(marker)
        if not isinstance(marker_data, dict) or marker_data.get("fingerprint") != fingerprint:
            return False
        code = _validate_result("code", review_dir / "code-result.json", asset_root / _CODE_SCHEMA)
        if code.get("verdict") != "PASS":
            return False
        if visual_required:
            visual = _validate_result(
                "visual", review_dir / "visual-result.json", asset_root / _VISUAL_SCHEMA
            )
            if visual.get("verdict") != "PASS":
                return False
    except PrePublishError:
        return False
    return True


def _context(change: ChangeSet) -> dict[str, object]:
    return {
        "base_ref": change.base_ref,
        "base_sha": change.base_sha,
        "merge_base_sha": change.merge_base_sha,
        "head_sha": change.head_sha,
        "diff_hash": change.diff_hash,
        "changed_files": list(change.changed_files),
        "ui_impact_files": list(change.ui_impact_files),
        "current_images": list(change.image_hashes),
        "deleted_current_images": list(change.deleted_current_images),
        "reference_images": list(change.reference_image_hashes),
    }


def _embedded_review_materials(
    project: Path,
    kind: ReviewKind,
    change: ChangeSet,
) -> str:
    if kind == "code":
        diff = _git_bytes(
            project,
            (
                "diff",
                "--no-ext-diff",
                "--no-textconv",
                "--unified=0",
                f"{change.base_ref}...HEAD",
                "--",
                ".",
                ":(exclude)**/*.md",
                ":(exclude)**/*.png",
                ":(exclude)**/*.jpg",
                ":(exclude)**/*.jpeg",
                ":(exclude)tests/**",
                ":(exclude)backend/tests/**",
                ":(exclude)contracts/examples/**",
                ":(exclude)generated/**",
                ":(exclude)scripts/capture*.py",
                ":(exclude)scripts/seed_full_demo.py",
                ":(exclude)**/*.test.ts",
                ":(exclude)**/*.test.tsx",
                ":(exclude)**/*.spec.ts",
                ":(exclude)**/*.spec.tsx",
            ),
        ).decode("utf-8", errors="replace")
        test_inventory: list[str] = []
        for relative in change.changed_files:
            path = PurePosixPath(relative)
            is_verification_asset = (
                relative.startswith("tests/")
                or relative.startswith("backend/tests/")
                or relative.startswith("contracts/examples/")
                or relative.startswith("generated/")
                or relative.startswith("scripts/capture")
                or relative == "scripts/seed_full_demo.py"
                or ".test." in path.name
                or ".spec." in path.name
            )
            candidate = project / relative
            if not is_verification_asset or not candidate.is_file():
                continue
            value = candidate.read_bytes()
            test_inventory.append(
                f"{relative}: bytes={len(value)} sha256={hashlib.sha256(value).hexdigest()}"
            )
            for line_number, line in enumerate(
                value.decode("utf-8", errors="replace").splitlines(),
                start=1,
            ):
                match = _TEST_DECLARATION.match(line)
                if match is not None:
                    test_inventory.append(
                        f"{relative}:{line_number}: {match.group(1) or match.group(2)}"
                    )
        materials = (
            "### AGENTS.md\n\n"
            + (project / "AGENTS.md").read_text(encoding="utf-8")
            + "\n\n### Exact unified diff\n\n"
            + diff
            + "\n\n### Changed-test inventory\n\n"
            + ("\n".join(test_inventory) if test_inventory else "(none)")
        )
    else:
        sections = []
        for relative in _VISUAL_REVIEW_INPUTS:
            sections.append(
                f"### {relative}\n\n"
                + (project / relative).read_text(encoding="utf-8")
            )
        manifest = _manifest_capture_index(project)
        selected_captures = []
        manifest_root = (project / _SCREENSHOT_MANIFEST).parent
        for image in change.current_images:
            viewport = manifest.get(image)
            if viewport is None:
                raise PrePublishError(
                    f"visual review image is not registered in the screenshot manifest: {image}"
                )
            relative = image.relative_to(manifest_root).as_posix()
            repository_relative = image.relative_to(project).as_posix()
            selected_captures.append(
                {
                    "image": relative,
                    "width": viewport[0],
                    "height": viewport[1],
                    "sha256": change.image_hashes[repository_relative],
                }
            )
        sections.append(
            f"### {_SCREENSHOT_MANIFEST}\n\n"
            + yaml.safe_dump(
                {"captures": selected_captures},
                allow_unicode=True,
                sort_keys=False,
            )
        )
        materials = "\n\n".join(sections)
    size = len(materials.encode("utf-8"))
    if size > _MAX_EMBEDDED_REVIEW_BYTES:
        raise PrePublishError(
            f"{kind} review input is {size} bytes; split the change below "
            f"{_MAX_EMBEDDED_REVIEW_BYTES} bytes before publication"
        )
    return materials


def _prompt(
    project: Path,
    asset_root: Path,
    relative: str,
    kind: ReviewKind,
    change: ChangeSet,
) -> str:
    source = (asset_root / relative).read_text(encoding="utf-8")
    return (
        source
        + "\n\n## Exact review input\n\n```json\n"
        + json.dumps(_context(change), ensure_ascii=False, indent=2)
        + "\n```\n\n## Embedded authoritative review materials\n\n"
        + _embedded_review_materials(project, kind, change)
    )


def _base_images(project: Path, change: ChangeSet, output: Path) -> tuple[Path, ...]:
    images: list[Path] = []
    relatives = {
        *(current.relative_to(project).as_posix() for current in change.current_images),
        *change.deleted_current_images,
    }
    for relative in sorted(relatives):
        result = _git(project, ("show", f"{change.base_ref}:{relative}"), check=False)
        if result.returncode != 0:
            continue
        target = output / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(bytes(result.stdout))
        images.append(target)
    return tuple(images)


def _run_one_review(
    *,
    kind: ReviewKind,
    project: Path,
    asset_root: Path,
    review_dir: Path,
    change: ChangeSet,
    runner: ReviewerRunner,
    worktree_reader: WorktreeReader,
    profile: ReviewProfile,
) -> dict[str, Any]:
    schema_relative = _CODE_SCHEMA if kind == "code" else _VISUAL_SCHEMA
    prompt_relative = _CODE_PROMPT if kind == "code" else _VISUAL_PROMPT
    result_path = review_dir / f"{kind}-result.json"
    log_path = review_dir / f"{kind}.log"
    images: tuple[Path, ...] = ()
    if kind == "visual":
        base = _base_images(project, change, review_dir / "base-images")
        images = (*change.current_images, *base, *change.reference_images)
        if not images:
            raise PrePublishError("visual review has no readable screenshot inputs", log_path)
    before = worktree_reader(project)
    runner.run(
        ReviewRequest(
            kind=kind,
            project=project,
            prompt=_prompt(project, asset_root, prompt_relative, kind, change),
            schema_path=asset_root / schema_relative,
            result_path=result_path,
            log_path=log_path,
            images=images,
            profile=profile,
        )
    )
    after = worktree_reader(project)
    if after != before:
        raise PrePublishError(
            f"{kind} reviewer changed the worktree despite read-only execution", log_path
        )
    result = _validate_result(kind, result_path, asset_root / schema_relative)
    if kind == "visual":
        manifest = _manifest_capture_index(project)
        expected: dict[str, tuple[int, int]] = {}
        for image in change.current_images:
            viewport = manifest.get(image)
            if viewport is None:
                raise PrePublishError(
                    f"visual review image is not registered in the current manifest: {image}",
                    result_path,
                )
            expected[image.relative_to(project).as_posix()] = viewport
        actual: dict[str, tuple[int, int]] = {}
        for screen in result["screens"]:
            image = screen["image"]
            viewport = (screen["viewport"]["width"], screen["viewport"]["height"])
            if image in actual:
                raise PrePublishError(
                    f"visual review repeats a current screenshot result: {image}", result_path
                )
            actual[image] = viewport
        if actual != expected:
            raise PrePublishError(
                "visual review screens do not exactly match the current manifest paths and "
                "viewports supplied for review",
                result_path,
            )
    if result["verdict"] != "PASS":
        summary = str(result.get("summary", "review requested changes"))
        raise PrePublishError(f"{kind} review NEEDS_CHANGES: {summary}", result_path)
    return result


def _validate_publication_target(change: ChangeSet, target: PublicationTarget | None) -> None:
    if target is None:
        return
    if target.base_ref != "main":
        raise PrePublishError(
            f"target PR base is {target.base_ref}, but this gate reviews origin/main only"
        )
    if target.head_sha != change.head_sha or target.base_sha != change.base_sha:
        raise PrePublishError(
            "target PR head/base does not match the reviewed local HEAD and origin/main; "
            "check out and update the PR branch before publication"
        )


def _revalidate_change(
    project: Path,
    expected: ChangeSet,
    target: PublicationTarget | None,
    collector: ChangeCollector,
) -> None:
    current = collector(project)
    if current != expected:
        raise PrePublishError(
            "repository refs, diff, paths, or screenshot inputs changed during review; rerun the "
            "pre-publish gate"
        )
    _validate_publication_target(current, target)


def run_pre_publish_pipeline(
    project: Path,
    *,
    independent_reviews: bool = False,
    runner: ReviewerRunner | None = None,
    cache_root: Path | None = None,
    asset_root: Path | None = None,
    documentation_check: DocumentCheck = _default_documentation_check,
    whitespace_check: WhitespaceCheck = _default_whitespace_check,
    deterministic_check: DeterministicCheck = _default_deterministic_check,
    change_collector: ChangeCollector = collect_change_set,
    change_revalidator: ChangeCollector | None = None,
    worktree_reader: WorktreeReader = _worktree_state,
    emit: Emitter = print,
    publication_target: PublicationTarget | None = None,
) -> str:
    """Run deterministic checks and optional independent reviews.

    Independent model execution is deliberately opt-in. Automatic Git and Codex
    publication hooks must use the default deterministic-only mode.
    """

    root = _repository_root(project)
    if os.environ.get("CMP_CODEX_REVIEW_ACTIVE") == "1":
        raise PrePublishError("recursive pre-publish review invocation was blocked")
    step_total = 6 if independent_reviews else 4
    emit(f"pre-publish 1/{step_total}: committed diff and fingerprint inputs")
    change = change_collector(root)
    _validate_publication_target(change, publication_target)
    emit(f"pre-publish 2/{step_total}: whitespace checks")
    whitespace_check(root, change)
    emit(f"pre-publish 3/{step_total}: documentation impact")
    documentation_check(root)
    emit(f"pre-publish 4/{step_total}: deterministic repository checks")
    deterministic_check(root, change)
    if not independent_reviews:
        inputs = _fingerprint_inputs(
            change,
            {},
            {"mode": "deterministic-only", "independent_reviews": False},
            publication_target,
        )
        _revalidate_change(
            root,
            change,
            publication_target,
            change_revalidator or change_collector,
        )
        fingerprint = _fingerprint(inputs)
        emit(f"pre-publish deterministic PASS: {fingerprint}")
        return fingerprint

    assets = (asset_root or root).resolve()
    actual_runner = runner or CodexExecRunner.discover(root)
    code_profile = (
        _FINAL_CODE_PROFILE
        if publication_target is not None
        and publication_target.action in {"create", "ready", "merge"}
        else _ROUTINE_CODE_PROFILE
    )
    review_settings = dict(actual_runner.settings)
    review_settings["code_profile"] = {
        "name": code_profile.name,
        "model": code_profile.model,
        "reasoning_effort": code_profile.reasoning_effort,
        "timeout_seconds": code_profile.timeout_seconds,
        "max_tokens": code_profile.max_tokens,
    }
    if change.requires_visual_review:
        review_settings["visual_profile"] = {
            "name": _VISUAL_PROFILE.name,
            "model": _VISUAL_PROFILE.model,
            "reasoning_effort": _VISUAL_PROFILE.reasoning_effort,
            "timeout_seconds": _VISUAL_PROFILE.timeout_seconds,
            "max_tokens": _VISUAL_PROFILE.max_tokens,
        }
    cache_target = publication_target or PublicationTarget(
        action="review",
        selector="checked-out-branch",
        hostname="github.com",
        repository=_origin_repository(root),
        head_sha=change.head_sha,
        base_sha=change.base_sha,
        base_ref="main",
    )
    inputs = _fingerprint_inputs(
        change,
        _asset_hashes(assets),
        review_settings,
        cache_target,
    )
    fingerprint = _fingerprint(inputs)
    cache = (cache_root or root / ".cache/codex-review").resolve()
    review_dir = cache / fingerprint
    if _cached_pass(review_dir, fingerprint, inputs, assets, change.requires_visual_review):
        _revalidate_change(
            root,
            change,
            publication_target,
            change_revalidator or change_collector,
        )
        emit(f"pre-publish PASS cache hit: {fingerprint}")
        return fingerprint
    review_dir.mkdir(parents=True, exist_ok=True)
    _atomic_json(review_dir / "inputs.json", inputs)
    emit(
        "pre-publish 5/6: independent read-only "
        f"{code_profile.name} review ({code_profile.model}, {code_profile.reasoning_effort})"
    )
    _run_one_review(
        kind="code",
        project=root,
        asset_root=assets,
        review_dir=review_dir,
        change=change,
        runner=actual_runner,
        worktree_reader=worktree_reader,
        profile=code_profile,
    )
    if change.requires_visual_review:
        emit("pre-publish 6/6: independent read-only visual review")
        _run_one_review(
            kind="visual",
            project=root,
            asset_root=assets,
            review_dir=review_dir,
            change=change,
            runner=actual_runner,
            worktree_reader=worktree_reader,
            profile=_VISUAL_PROFILE,
        )
    else:
        emit("pre-publish 6/6: visual review not required")
    _revalidate_change(
        root,
        change,
        publication_target,
        change_revalidator or change_collector,
    )
    _atomic_json(
        review_dir / "pass.json",
        {"fingerprint": fingerprint, "verdict": "PASS"},
    )
    emit(f"pre-publish PASS: {fingerprint}")
    return fingerprint


class CodexExecRunner:
    """Invoke a separate ephemeral Codex session with a read-only sandbox."""

    def __init__(
        self,
        executable: Path,
        executable_identity: str,
        *,
        timeout_seconds: int | None = None,
        process_runner: ProcessRunner = subprocess.run,
    ) -> None:
        self._executable = executable
        self._executable_identity = executable_identity
        self._timeout_seconds = timeout_seconds
        self._process_runner = process_runner

    @classmethod
    def discover(cls, project: Path) -> CodexExecRunner:
        configured = os.environ.get("CMP_CODEX_EXECUTABLE")
        resolved = Path(configured).expanduser() if configured else None
        if resolved is None:
            found = shutil.which("codex")
            if found is None:
                raise PrePublishError(
                    "codex CLI is not installed or not on PATH; authenticate/install it before "
                    "publish"
                )
            resolved = Path(found)
        resolved = resolved.resolve()
        if not resolved.is_file():
            raise PrePublishError(f"codex executable does not exist: {resolved}")
        identity = _sha256_file(resolved)
        executable = resolved
        if os.name == "nt" and "windowsapps" in str(resolved).lower():
            local_app_data = os.environ.get("LOCALAPPDATA")
            runtime_root = Path(local_app_data) / "OpenAI/Codex/bin" if local_app_data else Path()
            required_siblings = (
                "codex-command-runner.exe",
                "codex-windows-sandbox-setup.exe",
            )
            matches = [
                candidate
                for candidate in runtime_root.glob("*/codex.exe")
                if candidate.is_file()
                and _sha256_file(candidate) == identity
                and all((candidate.parent / sibling).is_file() for sibling in required_siblings)
            ]
            if not matches:
                raise PrePublishError(
                    "WindowsApps Codex has no SHA-matching local runtime with its read-only "
                    "sandbox helpers; repair/restart Codex before publication"
                )
            executable = max(matches, key=lambda candidate: candidate.stat().st_mtime_ns)
        return cls(executable, identity)

    @property
    def settings(self) -> Mapping[str, object]:
        return {
            "cli_sha256": self._executable_identity,
            "ephemeral": True,
            "hooks": False,
            "sandbox": "read-only",
        }

    def run(self, request: ReviewRequest) -> None:
        request.result_path.parent.mkdir(parents=True, exist_ok=True)
        request.result_path.unlink(missing_ok=True)
        command = [
            str(self._executable),
            "exec",
            "--ephemeral",
            "--ignore-user-config",
            "--sandbox",
            "read-only",
            "-c",
            "features.hooks=false",
            "--model",
            request.profile.model,
            "-c",
            f'model_reasoning_effort="{request.profile.reasoning_effort}"',
            "--output-schema",
            str(request.schema_path),
            "--output-last-message",
            str(request.result_path),
            "--cd",
            str(request.project),
        ]
        for image in request.images:
            command.extend(("--image", str(image)))
        command.append("-")
        environment = os.environ.copy()
        environment["CMP_CODEX_REVIEW_ACTIVE"] = "1"
        timeout_seconds = self._timeout_seconds or request.profile.timeout_seconds
        try:
            completed = self._process_runner(
                command,
                cwd=request.project,
                input=request.prompt,
                text=True,
                capture_output=True,
                timeout=timeout_seconds,
                env=environment,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            request.log_path.write_text(
                f"Codex review timed out after {timeout_seconds}s\n", encoding="utf-8"
            )
            raise PrePublishError(
                f"{request.kind} review timed out after {timeout_seconds}s",
                request.log_path,
            ) from error
        except OSError as error:
            request.log_path.write_text(f"{error}\n", encoding="utf-8")
            raise PrePublishError(
                f"{request.kind} review CLI/auth startup failed: {error}", request.log_path
            ) from error
        stdout = completed.stdout or ""
        stderr = completed.stderr or ""
        request.log_path.write_text(
            f"returncode={completed.returncode}\n--- stdout ---\n{stdout}\n"
            f"--- stderr ---\n{stderr}\n",
            encoding="utf-8",
        )
        if completed.returncode != 0:
            summary = stderr.strip().splitlines()[-1] if stderr.strip() else "no stderr"
            raise PrePublishError(
                f"{request.kind} review CLI/auth failed ({completed.returncode}): {summary}",
                request.log_path,
            )
        if not request.result_path.is_file():
            raise PrePublishError(
                f"{request.kind} review did not create its required result file", request.log_path
            )
        usage = _TOKEN_USAGE.search(stderr)
        if usage is None:
            raise PrePublishError(
                f"{request.kind} review did not report token usage", request.log_path
            )
        token_count = int(usage.group(1).replace(",", ""))
        if token_count > request.profile.max_tokens:
            raise PrePublishError(
                f"{request.kind} review used {token_count} tokens, exceeding the "
                f"{request.profile.max_tokens} token limit",
                request.log_path,
            )


def validate_pre_push_input(
    project: Path,
    value: str,
    *,
    remote_name: str | None,
    remote_location: str | None,
) -> None:
    """Bind one current-branch update to the configured origin push target."""

    root = _repository_root(project)
    if not remote_name or not remote_location:
        raise PrePublishError("pre-push hook did not supply its actual remote target")
    origin_location = _git_text(root, ("remote", "get-url", "--push", "origin"))
    if remote_name != "origin" or remote_location != origin_location:
        raise PrePublishError(
            "pre-push target must be the configured origin remote reviewed by this gate"
        )

    lines = [line for line in value.splitlines() if line.strip()]
    if len(lines) != 1:
        raise PrePublishError(
            "pre-push gate requires exactly one current branch ref; push branches separately"
        )
    fields = lines[0].split()
    if len(fields) != 4:
        raise PrePublishError("pre-push hook input is malformed")
    local_ref, local_sha, remote_ref, _remote_sha = fields
    branch = _git_text(root, ("symbolic-ref", "--quiet", "--short", "HEAD"))
    expected_ref = f"refs/heads/{branch}"
    if local_ref != expected_ref or remote_ref != expected_ref:
        raise PrePublishError("pre-push refs must both identify the reviewed checked-out branch")
    head_sha = _git_text(root, ("rev-parse", "HEAD"))
    if local_sha != head_sha:
        raise PrePublishError(
            "pushed ref is not the reviewed HEAD; check out that branch and push it separately"
        )


def pre_push_publication_target(
    project: Path,
    value: str,
    *,
    remote_name: str | None,
    remote_location: str | None,
) -> PublicationTarget:
    """Bind the hook input to a fresh remote-main publication snapshot."""

    root = _repository_root(project)
    validate_pre_push_input(
        root,
        value,
        remote_name=remote_name,
        remote_location=remote_location,
    )
    branch = _git_text(root, ("symbolic-ref", "--quiet", "--short", "HEAD"))
    repository, base_sha, head_sha, hostname = _publication_snapshot(root)
    return PublicationTarget(
        action="push",
        selector=branch,
        hostname=hostname,
        repository=repository,
        head_sha=head_sha,
        base_sha=base_sha,
        base_ref="main",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--trigger",
        choices=("manual", "git-pre-push", "codex-hook"),
        default="manual",
    )
    parser.add_argument("--remote-name")
    parser.add_argument("--remote-location")
    parser.add_argument(
        "--independent-review",
        action="store_true",
        help=(
            "explicitly opt in to paid Codex code/visual review; automatic hooks never set this"
        ),
    )
    args = parser.parse_args()
    try:
        pre_push_input: str | None = None
        publication_target: PublicationTarget | None = None
        if args.trigger == "git-pre-push":
            pre_push_input = sys.stdin.read()
            publication_target = pre_push_publication_target(
                args.root,
                pre_push_input,
                remote_name=args.remote_name,
                remote_location=args.remote_location,
            )
        fingerprint = run_pre_publish_pipeline(
            args.root,
            independent_reviews=args.independent_review,
            publication_target=publication_target,
        )
        if pre_push_input is not None:
            validate_pre_push_input(
                args.root,
                pre_push_input,
                remote_name=args.remote_name,
                remote_location=args.remote_location,
            )
    except Exception as error:
        detail = getattr(error, "detail_path", None)
        suffix = f" Details: {detail}" if detail else ""
        parser.exit(1, f"pre-publish gate failed: {error}.{suffix}\n")
    print(f"pre-publish gate passed ({args.trigger}): {fingerprint}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
