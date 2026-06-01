"""Tests for the gated target-site adapter (GitHubPRTarget).

Trust-critical: (1) construction is gated (bad repo / no token rejected),
(2) dry-run computes the plan and calls GitHub ZERO times, (3) only 'file'
artifacts auto-apply; snippet/map/plan go to the manual checklist, (4) the live
path opens a DRAFT PR on a fix branch (never the base branch), mocked via respx.
"""
from __future__ import annotations

import httpx
import pytest
import respx

from seomate.agent.target import GitHubPRTarget

MANIFEST = {
    "site_domain": "abcd.com",
    "audit_id": "deadbeef-0000-0000-0000-000000000000",
    "generated": [
        {"variable_id": "P6-18", "apply_to": "https://abcd.com/llms.txt", "artifact_kind": "file", "content": "# abcd.com\n", "verify": "GET /llms.txt 2xx"},
        {"variable_id": "P6-19", "apply_to": "global template <head>", "artifact_kind": "snippet", "content": "<script>...</script>", "verify": "Org schema present"},
        {"variable_id": "P2-42", "apply_to": "sitemap", "artifact_kind": "map", "content": {"x": 1}, "verify": "priority varies"},
    ],
    "manual": [
        {"variable_id": "P4-11", "fix_class": "human", "verify": "original research present"},
    ],
}


def test_construction_is_gated():
    with pytest.raises(ValueError):
        GitHubPRTarget("no-slash", "tok")
    with pytest.raises(ValueError):
        GitHubPRTarget("owner/name", "")


@pytest.mark.asyncio
async def test_dry_run_calls_github_zero_times():
    # respx with assert_all_mocked would raise if ANY request were made; we make
    # no routes and rely on dry-run not hitting the network.
    with respx.mock(assert_all_called=False) as mock:
        tgt = GitHubPRTarget("owner/site", "tok", dry_run=True)
        res = await tgt.apply(MANIFEST)
        assert mock.calls.call_count == 0          # ZERO GitHub calls in dry run
    assert res.dry_run is True
    assert res.pr_url is None
    assert res.branch == "seomate/fixes-deadbeef"  # deterministic from audit id
    # only the 'file' artifact is auto-applied; snippet+map+manual -> checklist
    assert res.files_written == ["public/llms.txt"]
    manual_ids = {m["variable_id"] for m in res.manual_checklist}
    assert {"P6-19", "P2-42", "P4-11"} <= manual_ids
    assert "DRY RUN" in res.note


@respx.mock
@pytest.mark.asyncio
async def test_live_opens_draft_pr_on_fix_branch():
    repo = "owner/site"
    respx.get(f"https://api.github.com/repos/{repo}/git/ref/heads/main").mock(
        return_value=httpx.Response(200, json={"object": {"sha": "base123"}}))
    create_ref = respx.post(f"https://api.github.com/repos/{repo}/git/refs").mock(
        return_value=httpx.Response(201, json={"ref": "refs/heads/seomate/fixes-deadbeef"}))
    respx.get(f"https://api.github.com/repos/{repo}/contents/public/llms.txt").mock(
        return_value=httpx.Response(404))
    put_file = respx.put(f"https://api.github.com/repos/{repo}/contents/public/llms.txt").mock(
        return_value=httpx.Response(201, json={"content": {"path": "public/llms.txt"}}))
    open_pr = respx.post(f"https://api.github.com/repos/{repo}/pulls").mock(
        return_value=httpx.Response(201, json={"html_url": f"https://github.com/{repo}/pull/1"}))

    tgt = GitHubPRTarget(repo, "tok", dry_run=False)
    res = await tgt.apply(MANIFEST)

    assert res.dry_run is False
    assert create_ref.called and put_file.called and open_pr.called
    # the PR is opened as a DRAFT, on the fix branch, against base main
    pr_body = open_pr.calls.last.request.content.decode()
    assert '"draft": true' in pr_body.replace(" ", "").replace("\n", "").lower() or '"draft":true' in pr_body.replace(" ", "")
    assert '"base": "main"' in pr_body or '"base":"main"' in pr_body.replace(" ", "")
    assert res.pr_url == f"https://github.com/{repo}/pull/1"
    assert res.files_written == ["public/llms.txt"]


@respx.mock
@pytest.mark.asyncio
async def test_live_surfaces_errors_without_partial_state():
    repo = "owner/site"
    respx.get(f"https://api.github.com/repos/{repo}/git/ref/heads/main").mock(
        return_value=httpx.Response(404, json={"message": "Not Found"}))
    tgt = GitHubPRTarget(repo, "tok", dry_run=False)
    res = await tgt.apply(MANIFEST)
    assert res.pr_url is None
    assert res.errors  # error surfaced, not swallowed
    assert res.files_written == []
