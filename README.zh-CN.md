# Feishu Wiki Course Exporter

[English](README.md) | [简体中文](README.zh-CN.md)

一个面向个人使用的命令行工具，用于导出当前已登录账号有权限访问的飞书 Wiki 内容。工具会重建完整的 Wiki 节点树，并将每个发现到的节点导出为 Markdown 与本地图片资源。

本项目与飞书或字节跳动不存在隶属或官方合作关系。

## 项目概述

导出器使用本地浏览器登录态，捕获重建 Wiki 目录树所需的请求，再调用仓库内置的 patched `feishu-docx` 完成页面转换。

稳定流程：

```text
login -> capture-network -> build-tree -> export-all-browser
```

## 工作原理

Feishu Wiki Exporter 会将飞书 Wiki 页面转换为本地 Markdown 文件，并保留嵌入的图片。

![导出流程](docs/images/export-workflow.png)

导出器使用当前登录状态访问可用 Wiki 节点，并将页面内容和图片保存为可复用的本地 Markdown 知识文件。

## 功能

- 导出所有发现到的 Wiki 节点，包括父节点和叶子节点。
- 在输出目录中保留 Wiki 层级。
- 输出 Markdown 与本地图片资源。
- 在节点计为成功前，校验 Markdown 已生成且非空、本地图片引用完整，并且不存在 `browser-asset://` 占位符。
- 单页失败后继续处理其余节点，并将最终失败写入本地 JSONL 日志。

## 安全、隐私与权限

- 只能导出你有权限访问并允许保存的内容。
- 本项目不绕过飞书权限，也不使用飞书开放平台凭据。
- `data/storage_state.json` 含可复用的浏览器登录态，必须保持私密，不应分享。
- 不要提交 `data/` 或 `output/`；其中可能包含页面 URL、Token、导出内容、图片和失败日志。

敏感数据和安全问题报告说明见 [SECURITY.md](SECURITY.md)。

## 环境要求

- Python 3.11 或更高版本。
- macOS 或 Linux。本文档使用项目内 `.venv/bin/` 布局；尚未提供或验证 Windows 使用方式。
- 对目标 Wiki 有访问权限的飞书账号。

## 安装

在仓库根目录执行：

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/playwright install chromium
```

`requirements.txt` 会安装仓库内的 patched wheel：
`vendor/feishu_docx-0.2.7-1patched-py3-none-any.whl`。导出器固定使用 `.venv/bin/feishu-docx`，不依赖 shell 的 `PATH` 顺序；文件不存在或不可执行时，程序会明确报错。

安装后可验证项目内 CLI：

```bash
.venv/bin/feishu-docx --version
```

## 首次登录

使用当前账号可访问的 Wiki 首页：

```bash
.venv/bin/python exporter.py login "https://your-domain.feishu.cn/wiki/<wiki_token>"
```

在浏览器窗口中完成登录后回到终端。浏览器状态会保存到 `data/storage_state.json`。

## 导出 Wiki

按顺序执行完整流程：

```bash
.venv/bin/python exporter.py login "https://your-domain.feishu.cn/wiki/<wiki_token>"
.venv/bin/python exporter.py capture-network "https://your-domain.feishu.cn/wiki/<wiki_token>"
.venv/bin/python exporter.py build-tree
.venv/bin/python exporter.py export-all-browser --output-dir output
```

导出器会在登录、构建 Wiki 树、页面导出和输出校验期间显示可见进度。

![导出进度](docs/images/export-progress.png)

判断导出是否正常运行：

- `[n/total]` 表示当前导出进度。
- `Completed` 表示当前页面导出成功。
- 校验结果中的 missing references 和 browser placeholders 应为 `0`。
- 命令正常结束并返回状态码 `0` 表示导出成功。

`capture-network` 会在本地记录响应元数据。`build-tree` 使用这些元数据和已保存的登录态重建完整 Wiki 树。`export-all-browser` 会导出树中的每个节点。

## 导出输出

导出器会生成 Markdown 页面和本地图片资源，可复用于基于 Markdown 的知识系统。

![导出文件](docs/images/exported-files.png)

## 输出与成功条件

输出会保留页面层级。每个页面的 Markdown 文件与本地图片目录会同时写入，例如：

```text
output/
├── 页面.md
└── 页面/
    ├── image.png
    └── image-1.png
```

节点仅在以下条件同时满足时计为成功：Markdown 文件存在、文件非空、不含 `browser-asset://`，且 Markdown 中的每个本地图片引用都在磁盘上存在。

单页首次失败时，导出器会重试一次；随后继续处理其他节点。最终失败记录写入：

```text
output/export_failures_browser.jsonl
```

只有全部节点均通过导出和后置校验时，命令才以状态码 `0` 结束。任何页面失败都会使最终状态码非零。

## 限制

- 导出范围仅限当前已登录账号可发现的节点。
- 浏览器登录态可能过期；页面级权限或飞书页面变化可能导致个别页面失败。
- 本项目仅提供本地 CLI，不提供 GUI、云服务、数据库、同步能力或绕过权限的能力。
- 既有输出属于敏感本地数据；需要保留不同运行结果时，应使用新的输出目录。

## 文档

- [英文 README](README.md)
- [故障排查](TROUBLESHOOTING.md)
- [安全策略](SECURITY.md)
- [更新日志](CHANGELOG.md)
- [历史审计记录](docs/audits/成功版本能力差异审计报告.md)

## 来源与致谢

本项目基于 [feishu-docx](https://github.com/leemysw/feishu-docx)，原作者为
[leemysw](https://github.com/leemysw)。上游项目提供底层飞书/Lark 文档转换、
浏览器导出、本地资源处理以及 `feishu-docx` 包和 CLI 能力。

本仓库在此基础上增加了面向 Wiki 全量导出的工作流，包括浏览器登录态登录、
网络捕获、递归重建 Wiki 树、父节点和叶子节点导出、固定使用项目内 patched
CLI、导出后校验、失败日志和批处理退出码处理。

## 验收快照

当前验收快照记录：

- Wiki 节点：68；
- 成功导出：68；
- 失败数量：0；
- 图片资源：187；
- Markdown 图片引用缺失：0。

这是一轮验收运行的快照，不构成对所有飞书租户、账号或未来页面结构的保证。

## 法律与负责任使用

- 仅导出你有权访问并获准保存的飞书内容。
- 你负责所导出内容的版权、隐私、保密、数据保护和商业使用合规。
- 不得使用本项目绕过访问控制、传播受保护内容或暴露他人的私人数据。
- 开发者和维护者不对用户滥用工具或处理导出内容所产生的后果负责。

## 许可证

项目以 [MIT License](LICENSE) 发布。
