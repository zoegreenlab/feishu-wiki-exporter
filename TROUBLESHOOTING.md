# Troubleshooting

Use the commands below from the repository root and through the project-local
virtual environment.

## Login State Is Missing or Expired

Symptom: a command reports that `data/storage_state.json` is missing, or a
previously working export can no longer access the Wiki.

Run `login` again with a Wiki homepage that your account can access:

```bash
.venv/bin/python exporter.py login "https://your-domain.feishu.cn/wiki/<wiki_token>"
```

Complete login in the browser and return to the terminal. Do not reuse or share
another person's `storage_state.json`.

## `build-tree` Cannot Find a Directory Request

Symptom: `build-tree` reports that it cannot find the
`/space/api/wiki/v2/tree/get_info/` request.

Capture a fresh network log for the target Wiki homepage, then rebuild the
tree:

```bash
.venv/bin/python exporter.py capture-network "https://your-domain.feishu.cn/wiki/<wiki_token>"
.venv/bin/python exporter.py build-tree
```

Confirm that the browser state is valid and that the target page is accessible
before retrying.

## Project `feishu-docx` CLI Is Missing

Symptom: `export-all-browser` reports that the project `feishu-docx` CLI is
missing or not executable.

Recreate the project environment and install the repository requirements:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/playwright install chromium
.venv/bin/feishu-docx --version
```

Do not use `which feishu-docx` or a globally installed CLI as a substitute. The
exporter requires `.venv/bin/feishu-docx` from this repository.

## A Page Fails During Batch Export

The exporter retries a failed page once and continues with the remaining nodes.
Review the final failure log:

```text
output/export_failures_browser.jsonl
```

The process exits with a non-zero status if any node fails. Treat a non-zero
status as an incomplete export even when most pages were written successfully.

Failure logs can contain private page URLs and must remain local.

## Markdown or Image Validation Fails

A page is marked failed if its Markdown file is missing or empty, contains a
`browser-asset://` placeholder, or references a local image file that does not
exist.

Use a new output directory for a clean rerun:

```bash
.venv/bin/python exporter.py export-all-browser --output-dir output-rerun
```

Then inspect the affected Markdown file and its same-name image directory. Do
not mix a partial previous run with a new run if you need a reliable validation
result.

## Playwright or Chromium Is Unavailable

Run the browser installation step again inside the project environment:

```bash
.venv/bin/playwright install chromium
```

If browser launch still fails, verify that you are using Python 3.11 or later
and a supported macOS or Linux environment.

## Getting Help Safely

For a reproducible bug report, include the command name, non-sensitive error
text, Python version, and whether the failure occurred during login, tree
construction, or export. Remove Wiki URLs, tokens, browser state, exported
content, and failure-log records before sharing.

See [SECURITY.md](SECURITY.md) for sensitive-data and vulnerability-reporting
guidance.
