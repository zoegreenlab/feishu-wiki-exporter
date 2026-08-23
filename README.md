# Feishu Wiki Course Exporter

Unofficial personal-use tool for exporting Feishu Wiki pages that your account
can access. It is not affiliated with Feishu or ByteDance.

The tool reuses local browser login state, rebuilds a Wiki directory tree, and
delegates each leaf-page export to the external feishu-docx CLI.

## Privacy and permission boundary

- Export only content you are authorized to access and save.
- This tool does not bypass Feishu permissions or use Feishu Open Platform credentials.
- data/storage_state.json contains reusable browser login state. Keep it local.
- Never commit data/ or output/; they can contain URLs, tokens, content, and logs.

## Requirements

- Python 3;
- Playwright and its Chromium runtime;
- feishu-docx available in the terminal;
- read access to the target Feishu Wiki.

Install Python dependencies:

~~~bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/playwright install chromium
~~~

Install feishu-docx separately, then check:

~~~bash
feishu-docx --help
~~~

## Stable workflow

~~~text
login → capture-network → build-tree → export-all-browser
~~~

Run these commands from the repository root. Use your own Wiki homepage URL.

~~~bash
.venv/bin/python exporter.py login "https://your-domain.feishu.cn/wiki/<wiki_token>"
.venv/bin/python exporter.py capture-network "https://your-domain.feishu.cn/wiki/<wiki_token>"
.venv/bin/python exporter.py build-tree
.venv/bin/python exporter.py export-all-browser --output-dir output
~~~

The output directory is generic. The exporter keeps local page hierarchy and
writes per-page failures to output/export_failures_browser.jsonl without
stopping the whole batch.

## Scope

This repository contains only the stable workflow. It intentionally excludes
personal data, exported content, experimental API probes, custom Markdown
rendering, a GUI, cloud services, and a database.

See docs/使用说明.md for operational details.
