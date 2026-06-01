"""Target-site adapter: apply fix artifacts to the audited site, gated.

The executor (``execute.py``) generates fix artifacts in propose mode. This
module is the last mile: applying them to the actual website. SEOMATE does not
own the audited site's repo, so applying is gated on the caller supplying:
  - the target site's GitHub repo (owner/name)
  - a token with write access to it

**Safety model (deliberate, layered):**
1. The adapter is only constructed when a caller passes an explicit target +
   token. There is no implicit/default target.
2. It opens a **draft pull request**, never commits to the default branch and
   never auto-merges. A human reviews + merges.
3. It defaults to ``dry_run=True`` , it computes exactly what it would do
   (branch name, files, PR body) and returns it without calling GitHub. A real
   PR is only opened when the caller passes ``dry_run=False``.
4. It only auto-writes ``file``-kind artifacts (a whole file dropped at a path,
   e.g. ``llms.txt``). ``snippet``/``map``/``plan`` artifacts need site-specific
   template/build integration, so they go into the PR body as a structured
   checklist for the site developer , honest about what is and isn't automated.

This keeps "modify someone's production content" a reviewed, opt-in action.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass, field
from typing import Any

import httpx

_GH = "https://api.github.com"

# which artifact kinds can be dropped into a repo as-is vs need a human to integrate
_AUTO_APPLY_KINDS = {"file"}


@dataclass
class TargetResult:
    dry_run: bool
    repo: str
    branch: str
    files_written: list[str]
    manual_checklist: list[dict[str, Any]]
    pr_url: str | None = None
    pr_title: str = ""
    pr_body: str = ""
    note: str = ""
    errors: list[str] = field(default_factory=list)


def _artifact_path(apply_to: str) -> str | None:
    """Map a 'file' artifact's apply_to to a repo path. Only handles the cases
    we can place unambiguously; returns None when the location is site-specific."""
    a = apply_to.lower()
    if "/llms.txt" in a:
        return "public/llms.txt"  # common static-root convention; reviewer can move it
    if a.endswith("robots.txt") or "/robots.txt" in a:
        return "public/robots.txt"
    return None


class GitHubPRTarget:
    """Opens a draft PR against the audited site's repo with the auto-applyable
    artifacts, and lists the rest as a review checklist. Gated + dry-run-first."""

    def __init__(self, repo: str, token: str, *, base_branch: str = "main", dry_run: bool = True):
        if not repo or "/" not in repo:
            raise ValueError("repo must be 'owner/name'")
        if not token:
            raise ValueError("a GitHub token with write access is required to apply")
        self.repo = repo
        self._token = token
        self.base_branch = base_branch
        self.dry_run = dry_run

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}", "Accept": "application/vnd.github+json"}

    def _plan(self, manifest: dict[str, Any], branch: str) -> tuple[dict[str, str], list[dict], str, str]:
        """Compute (files_to_write, manual_checklist, pr_title, pr_body) without calling GitHub."""
        files: dict[str, str] = {}
        manual: list[dict] = []
        for art in manifest.get("generated", []):
            kind = art.get("artifact_kind")
            path = _artifact_path(art.get("apply_to", "")) if kind in _AUTO_APPLY_KINDS else None
            if kind in _AUTO_APPLY_KINDS and path and isinstance(art.get("content"), str):
                files[path] = art["content"]
            else:
                manual.append({
                    "variable_id": art["variable_id"],
                    "apply_to": art.get("apply_to"),
                    "artifact_kind": kind,
                    "verify": art.get("verify"),
                    "why_manual": "needs site-specific template/build integration" if kind != "file" else "ambiguous file location , reviewer to place",
                })
        # manual work orders from the executor (human/owner/budget) carry through too
        for m in manifest.get("manual", []):
            manual.append({"variable_id": m["variable_id"], "fix_class": m.get("fix_class"), "verify": m.get("verify")})

        domain = manifest.get("site_domain", "site")
        title = f"SEOMATE fixes for {domain} ({len(files)} auto + {len(manual)} to review)"
        body_lines = [
            f"Automated SEO fixes from the SEOMATE audit `{manifest.get('audit_id', '')}`.",
            "",
            f"## Auto-applied in this PR ({len(files)} file(s))",
        ]
        for p in files:
            body_lines.append(f"- `{p}` , review and merge to apply")
        body_lines += ["", f"## Needs your integration ({len(manual)})"]
        for m in manual:
            vid = m.get("variable_id", "?")
            tgt = m.get("apply_to") or m.get("fix_class") or ""
            body_lines.append(f"- **{vid}** , {tgt}. Verify: {m.get('verify', '')}")
        body_lines += ["", "_Draft PR. Review each change; merge to apply. Then re-audit to confirm each variable flips to passed._"]
        return files, manual, title, "\n".join(body_lines)

    async def apply(self, manifest: dict[str, Any]) -> TargetResult:
        """Open a draft PR (or, in dry-run, compute exactly what it would do)."""
        # deterministic branch name (no Date.now / random , derive from audit id)
        branch = f"seomate/fixes-{str(manifest.get('audit_id', 'audit'))[:8]}"
        files, manual, title, body = self._plan(manifest, branch)

        if self.dry_run:
            return TargetResult(
                dry_run=True, repo=self.repo, branch=branch,
                files_written=list(files), manual_checklist=manual,
                pr_title=title, pr_body=body,
                note="DRY RUN , no PR opened. Re-run with dry_run=False (and a write token) to open a draft PR.",
            )

        errors: list[str] = []
        async with httpx.AsyncClient(headers=self._headers(), base_url=_GH, timeout=30) as c:
            try:
                # 1. base branch head sha
                ref = await c.get(f"/repos/{self.repo}/git/ref/heads/{self.base_branch}")
                ref.raise_for_status()
                base_sha = ref.json()["object"]["sha"]
                # 2. create the fix branch (idempotent-ish: ignore 'already exists')
                cr = await c.post(f"/repos/{self.repo}/git/refs", json={"ref": f"refs/heads/{branch}", "sha": base_sha})
                if cr.status_code not in (201, 422):
                    cr.raise_for_status()
                # 3. write each file on the branch (Contents API)
                written = []
                for path, content in files.items():
                    # get existing sha if the file is already there (update vs create)
                    ex = await c.get(f"/repos/{self.repo}/contents/{path}", params={"ref": branch})
                    sha = ex.json().get("sha") if ex.status_code == 200 else None
                    payload = {
                        "message": f"SEOMATE: add/update {path}",
                        "content": base64.b64encode(content.encode()).decode(),
                        "branch": branch,
                    }
                    if sha:
                        payload["sha"] = sha
                    put = await c.put(f"/repos/{self.repo}/contents/{path}", json=payload)
                    put.raise_for_status()
                    written.append(path)
                # 4. open a DRAFT PR
                pr = await c.post(
                    f"/repos/{self.repo}/pulls",
                    json={"title": title, "head": branch, "base": self.base_branch, "body": body, "draft": True},
                )
                pr.raise_for_status()
                return TargetResult(
                    dry_run=False, repo=self.repo, branch=branch, files_written=written,
                    manual_checklist=manual, pr_url=pr.json().get("html_url"),
                    pr_title=title, pr_body=body, note="Draft PR opened. Review + merge to apply, then re-audit.",
                )
            except httpx.HTTPStatusError as e:
                errors.append(f"{e.response.status_code} {e.request.method} {e.request.url.path}: {e.response.text[:120]}")
            except Exception as e:  # noqa: BLE001
                errors.append(str(e)[:160])
        return TargetResult(
            dry_run=False, repo=self.repo, branch=branch, files_written=[],
            manual_checklist=manual, pr_title=title, pr_body=body, errors=errors,
            note="apply failed , see errors. No partial PR is left in a usable state; review the repo.",
        )
