# Security Policy

## Scope

This project processes browser login state and exports private Feishu Wiki
content to the local filesystem. The most important security boundary is the
handling of that local data.

The following paths can contain sensitive information and must remain local:

- `data/storage_state.json` — reusable authenticated browser state;
- `data/network_log.json` and `data/full_wiki_tree.json` — request metadata,
  Wiki URLs, and node metadata;
- `output/`, `output-rerun/`, and other export destinations — exported
  content, image resources, URLs, and failure logs.

The repository's `.gitignore` excludes `data/`, `output/`, `output-rerun/`,
and the documented acceptance-test output directories. Custom paths passed
to `--state-path` or `--output-dir` are not automatically excluded: keep
them outside this repository or add an appropriate ignore rule before use.
Git ignore rules do not remove data that has already been committed.

Do not commit, attach, or paste sensitive files or their contents into public
issues, pull requests, screenshots, or support discussions. Console output may
also include private Wiki URLs and page titles; redact it before sharing.

## Supported Version

Security fixes are considered for the current v1.x release line.

## Reporting a Vulnerability

Report suspected security vulnerabilities using [GitHub's private vulnerability
reporting form](https://github.com/zoegreenlab/feishu-wiki-exporter/security/advisories/new)
(the **Report a vulnerability** option on the repository's Security tab).

Do not report a suspected vulnerability in a public GitHub issue, and do not
include login state, tokens, private Wiki URLs, or exported content in any
report. Provide a sanitized reproduction instead.

If the private reporting form is inaccessible, you may open a public issue
requesting an alternative private contact method, but do not disclose the
vulnerability or any sensitive details there.

For non-sensitive usage questions and reproducible bugs, use the normal issue
tracker with all private data removed.

## Out of Scope

- Access to content that a user is already authorized to access in Feishu.
- Requests to bypass Feishu permissions or obtain credentials.
- Bugs reported only with private content, credentials, or browser state and no
  safely reproducible details.
