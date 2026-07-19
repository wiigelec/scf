"""Required repository artifact and narrow bootstrap-record validation."""

from __future__ import annotations

from ..context import InputProblem, ValidationContext
from ..diagnostics import Diagnostic, Severity
from .common import from_problem

REQUIRED_ARTIFACTS = (
    "README.md",
    "VERSION",
    "authority/core/SCF-CORE.json",
    "authority/core/SCF-CORE.sha256",
    "authority/core/manifest.json",
    "authority/README.md",
    "authority/level-0/README.md",
    "authority/level-0/SCF-LEVEL-0.json",
    "authority/level-0/SCF-LEVEL-0.schema.json",
    "authority/level-0/SCF-LEVEL-0.sha256",
    "authority/level-0/SCF-LEVEL-0.schema.sha256",
    "authority/level-0/manifest.json",
    "bootstrap/BOOTSTRAP-SCOPE.json",
    "bootstrap/INITIAL-DEVELOPMENT-PROCESS.md",
    "bootstrap/README.md",
    ".github/ISSUE_TEMPLATE/governed-work.md",
    "docs/GOVERNED-ISSUE-PLANNING.md",
    "docs/templates/GOVERNED-DETAILED-SCOPE.md",
    "docs/templates/GOVERNED-WORK-BREAKDOWN.md",
    "planning/README.md",
    "planning/BOOTSTRAP-TO-DEVELOPMENT-ROADMAP.md",
)
BOOTSTRAP_PATH = "bootstrap/BOOTSTRAP-SCOPE.json"


def check_repository(context: ValidationContext) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for repository_path in REQUIRED_ARTIFACTS:
        try:
            target = context.safe_path(repository_path)
        except InputProblem as problem:
            diagnostics.append(from_problem(problem))
            continue
        if not target.is_file():
            diagnostics.append(
                Diagnostic(
                    "SCF-REPO-MISSING",
                    Severity.ERROR,
                    "required current artifact is missing",
                    repository_path,
                )
            )

    try:
        bootstrap = context.parse_json(BOOTSTRAP_PATH)
    except InputProblem as problem:
        diagnostics.append(from_problem(problem))
        return diagnostics
    if not isinstance(bootstrap, dict):
        diagnostics.append(
            Diagnostic(
                "SCF-BOOTSTRAP-TOPLEVEL",
                Severity.ERROR,
                "bootstrap record must be a JSON object",
                BOOTSTRAP_PATH,
            )
        )
        return diagnostics

    if bootstrap.get("status") != "consumed-by-bootstrap-commit":
        diagnostics.append(
            Diagnostic(
                "SCF-BOOTSTRAP-STATUS",
                Severity.ERROR,
                "bootstrap status must be 'consumed-by-bootstrap-commit'",
                BOOTSTRAP_PATH,
                "status",
            )
        )
    expires = bootstrap.get("expires_after")
    if not isinstance(expires, str) or not expires.strip():
        diagnostics.append(
            Diagnostic(
                "SCF-BOOTSTRAP-EXPIRATION",
                Severity.ERROR,
                "bootstrap expiration statement is missing",
                BOOTSTRAP_PATH,
                "expires_after",
            )
        )

    outputs = bootstrap.get("allowed_outputs")
    if isinstance(outputs, list):
        for index, output in enumerate(outputs):
            if not isinstance(output, str):
                diagnostics.append(
                    Diagnostic(
                        "SCF-BOOTSTRAP-OUTPUT",
                        Severity.ERROR,
                        "historical output path must be a string",
                        BOOTSTRAP_PATH,
                        f"allowed_outputs[{index}]",
                    )
                )
                continue
            try:
                target = context.safe_path(output)
            except InputProblem as problem:
                diagnostics.append(from_problem(problem))
                continue
            if not target.exists():
                diagnostics.append(
                    Diagnostic(
                        "SCF-BOOTSTRAP-OUTPUT",
                        Severity.ERROR,
                        "historical bootstrap output is missing",
                        output,
                    )
                )
    return diagnostics
