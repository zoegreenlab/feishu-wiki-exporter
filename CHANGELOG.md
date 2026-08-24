# Changelog

All notable changes to this project are documented in this file.

## [1.0.0] - 2026-08-24

### Added

- Stable browser-state workflow: `login`, `capture-network`, `build-tree`, and
  `export-all-browser`.
- Recursive collection and export of every discovered Wiki node, including
  parent and leaf nodes.
- Repository-local patched `feishu-docx` wheel used through the project
  virtual environment.
- Post-export checks for Markdown existence, non-empty content,
  `browser-asset://` placeholders, and local image references.
- Per-page retry, JSONL failure logging, continued batch processing, and a
  non-zero final exit status when any node fails.

### Documentation

- English primary README and synchronized Simplified Chinese README.
- Troubleshooting and security documentation for the v1.0 release.

### Known Limitations

- The project exports only content available to the signed-in account.
- Browser state, page permissions, and Feishu page changes can affect a run.
- The documented command layout targets macOS and Linux.
