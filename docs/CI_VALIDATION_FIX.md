# CI browser-cache correction

Investigated: 12 October 2026. The reported [failed run](https://github.com/mahendraek/FabClean-SaaS/actions/runs/38234899176) is main `04a6d8e` (PR #8). Newer PR #9 runs also failed before this fix. Public GitHub job metadata is readable; detailed logs require sign-in and were supplied by the user.

The failed step had already exported the app, then Playwright could not find Chromium's headless shell under `/tmp/fabclean-cache/ms-playwright`. Installation used the runner's original cache; `scripts/validate_pr6.sh` subsequently changed `XDG_CACHE_HOME`. Local browser suites used the explicit system-Chromium override, which masked this CI installation-path mismatch. The Node 20 deprecation annotation was a warning, not the reported failure.

The workflow now sets job-wide `PLAYWRIGHT_BROWSERS_PATH` for installation and every browser launch. A new startup check uses the validation script's XDG-cache default immediately after installation, before the expensive gate. It launches the installed headless Chromium and closes it; no test assertions are disabled.

Local verification reproduced the old path drift using Playwright's real executable resolver and verified that the explicit browser path remains stable across XDG changes. A fresh disposable PostgreSQL run on the failed PR #8 tree passed all 100 backend tests, 26 frontend tests, TypeScript/export and all four browser suites with system Chromium. The targeted desktop/mobile context suite also passed with the new environment settings. Downloading Playwright's stock browser here was denied by the cloud's CDN allowlist; the hosted run previously installed it successfully, so the new GitHub run is the definitive check of that installed binary.

The fix is published through PR #9; main/Render are unchanged. Read [current workflow runs](https://github.com/mahendraek/FabClean-SaaS/actions?query=branch%3Aroadmap%2Flocation-taxes) for the exact published head. Historical failure emails and runs do not change after a fix. GitHub API access still returns Forbidden.
