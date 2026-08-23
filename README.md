# Feishu Wiki Course Exporter

## Project introduction

一个面向个人使用的飞书 Wiki 完整迁移工具。它只导出当前账号有权限访问的内容，不绕过飞书权限，也不代表飞书或字节跳动。

工具使用本地浏览器登录态，重建 Wiki 节点树，再通过项目环境中的 patched `feishu-docx` 将每个节点导出为 Markdown 和本地资源。

## Features

- 导出当前账号权限范围内可发现的 Wiki 节点，包括父节点和叶子节点；
- 保留 Wiki 页面层级；
- 输出 Markdown 文件；
- 下载页面中的图片资源；
- 保持 Markdown 与本地图片之间的引用关系；
- 支持使用浏览器登录态访问页面。

## Privacy and permission boundary

- Export only content you are authorized to access and save.
- This tool does not bypass Feishu permissions or use Feishu Open Platform credentials.
- data/storage_state.json contains reusable browser login state. Keep it local.
- Never commit data/ or output/; they can contain URLs, tokens, content, and logs.

## Installation

在仓库根目录执行以下步骤。项目使用 Python 3 虚拟环境，`feishu-docx` 不需要安装到用户级 uv tool 或系统环境。

### Python environment

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/playwright install chromium
```

`requirements.txt` 包含项目内的 patched `feishu-docx` wheel：`vendor/feishu_docx-0.2.7-1patched-py3-none-any.whl`。安装完成后，确认命令来自项目虚拟环境：

```bash
source .venv/bin/activate
which feishu-docx
feishu-docx --version
```

`which feishu-docx` 应指向当前项目的 `.venv/bin/feishu-docx`。

## First login

首次运行需要使用你有权限访问的 Wiki 首页登录：

```bash
.venv/bin/python exporter.py login "https://your-domain.feishu.cn/wiki/<wiki_token>"
```

浏览器窗口打开后完成登录。登录态会保存到 `data/storage_state.json`，请勿提交或分享该文件。

登录完成后继续执行 Stable workflow。

## Stable workflow

```text
login → capture-network → build-tree → export-all-browser
```

从仓库根目录依次执行：

```bash
.venv/bin/python exporter.py login "https://your-domain.feishu.cn/wiki/<wiki_token>"
.venv/bin/python exporter.py capture-network "https://your-domain.feishu.cn/wiki/<wiki_token>"
.venv/bin/python exporter.py build-tree
.venv/bin/python exporter.py export-all-browser --output-dir output
```

`capture-network` 和 `build-tree` 用于恢复完整 Wiki 节点树；`export-all-browser` 使用同一登录态导出所有节点。

## Output structure

导出结果会保留页面层级。每个页面的图片资源放在同名资源目录中：

```text
output/
├── 页面.md
└── 页面/
    ├── image.png
    └── image-1.png
```

批量导出失败的页面会记录在：

```text
output/export_failures_browser.jsonl
```

## Running notes

- 大量 Wiki 节点导出需要等待；
- CLI 会显示实时进度、当前页面、成功状态和耗时；
- 导出过程中不要关闭终端或浏览器相关进程；
- 单个页面首次失败时会自动等待并重试一次，最终失败才会写入失败日志。

## Troubleshooting

### 登录失效

重新执行 `login`，在浏览器中完成登录后再从 `capture-network` 开始执行。不要复用他人的 `data/storage_state.json`。

### 页面导出失败

检查终端中的失败信息和 `output/export_failures_browser.jsonl`。工具会对单页进行一次自动重试；重试后仍失败的页面才会记录在日志中。

### 图片资源或引用异常

确认页面同名资源目录与 Markdown 文件同时存在，并检查 Markdown 中的相对图片路径。建议使用新的输出目录重新导出，避免与旧结果混用。

## Technical architecture

- 使用 Playwright 完成登录并保存浏览器状态；
- 通过网络日志定位 Wiki 树接口，再递归构建本地节点树；
- 使用 `feishu-docx export-browser` 读取登录态页面并生成 Markdown 与资源；
- 项目本身不提供 GUI、云端服务、数据库或绕过权限的能力。

## Validation

当前验证结果：

- Wiki 节点：68；
- 导出成功：68；
- 失败数量：0；
- 图片资源：187；
- 图片引用缺失：0。
