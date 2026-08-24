# Security Policy

## Scope

This project processes browser login state and exports private Feishu Wiki
content to the local filesystem. The most important security boundary is the
handling of that local data.

The following paths can contain sensitive information and must remain local:

- `data/storage_state.json` — reusable authenticated browser state;
- `data/network_log.json` and `data/full_wiki_tree.json` — request metadata,
  Wiki URLs, and node metadata;
- `output/` and export failure logs — exported content, image resources, URLs,
  and error details.

These paths are ignored by Git. Do not commit, attach, or paste their contents
into public issues, pull requests, screenshots, or support discussions.

## Supported Version

Security fixes are considered for the current v1.x release line.

## Reporting a Vulnerability

Do not report a suspected vulnerability in a public GitHub issue, and do not
include login state, tokens, private Wiki URLs, or exported content in any
report.

Before publishing v1.0.0, the maintainer must enable GitHub private
vulnerability reporting or publish a private security contact in this section.
Until that channel is available, public disclosure is not an appropriate way to
report a security issue.

For non-sensitive usage questions and reproducible bugs, use the normal issue
tracker with all private data removed.

## Out of Scope

- Access to content that a user is already authorized to access in Feishu.
- Requests to bypass Feishu permissions or obtain credentials.
- Bugs reported only with private content, credentials, or browser state and no
  safely reproducible details.
