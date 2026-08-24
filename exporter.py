"""Stable personal exporter for Feishu Wiki courses."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from pathlib import Path
from urllib.parse import parse_qs, parse_qsl, unquote, urlencode, urlparse, urlunparse

from playwright.sync_api import (
    Browser,
    BrowserContext,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)


DEFAULT_STATE_PATH = Path("data/storage_state.json")
DEFAULT_OUTPUT_DIR = Path("output")
PROJECT_ROOT = Path(__file__).resolve().parent
PROJECT_FEISHU_DOCX = PROJECT_ROOT / ".venv" / "bin" / "feishu-docx"
MARKDOWN_IMAGE_REFERENCE_PATTERN = re.compile(r"!\[[^\]]*\]\(([^)\n]+)\)")
NETWORK_PRIORITY_KEYWORDS = (
    "wiki",
    "space",
    "node",
    "child",
    "block",
    "tree",
    "outline",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Personal stable exporter for Feishu Wiki courses."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_common_arguments(command_parser: argparse.ArgumentParser) -> None:
        command_parser.add_argument("wiki_url", help="Feishu Wiki homepage URL")
        command_parser.add_argument(
            "--state-path",
            type=Path,
            default=DEFAULT_STATE_PATH,
            help=f"Path for the saved login state (default: {DEFAULT_STATE_PATH})",
        )

    login_parser = subparsers.add_parser("login", help="Save browser login state")
    add_common_arguments(login_parser)

    network_parser = subparsers.add_parser(
        "capture-network", help="Record response metadata while loading a Wiki page"
    )
    add_common_arguments(network_parser)
    network_parser.add_argument(
        "--timeout-ms",
        type=int,
        default=30_000,
        help="Page-load timeout in milliseconds (default: 30000)",
    )

    build_tree_parser = subparsers.add_parser(
        "build-tree", help="Recursively build the complete Wiki directory tree"
    )
    build_tree_parser.add_argument(
        "--state-path",
        type=Path,
        default=DEFAULT_STATE_PATH,
        help=f"Path for the saved login state (default: {DEFAULT_STATE_PATH})",
    )

    export_all_browser_parser = subparsers.add_parser(
        "export-all-browser", help="Export all Wiki nodes through feishu-docx"
    )
    export_all_browser_parser.add_argument(
        "--state-path",
        type=Path,
        default=DEFAULT_STATE_PATH,
        help=f"Path for the saved login state (default: {DEFAULT_STATE_PATH})",
    )
    export_all_browser_parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Directory for exported pages and resources (default: {DEFAULT_OUTPUT_DIR})",
    )

    return parser.parse_args()


def require_state_file(state_path: Path) -> None:
    if not state_path.exists():
        raise FileNotFoundError(
            f"未找到登录状态文件：{state_path}。请先运行 login 命令完成登录。"
        )


def capture_network(wiki_url: str, state_path: Path, timeout_ms: int) -> None:
    """Record response metadata only; response bodies are never read."""
    require_state_file(state_path)
    responses: list[dict[str, str]] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = create_context(browser, state_path)
        page = context.new_page()

        def record_response(response: object) -> None:
            responses.append(
                {
                    "url": response.url,
                    "method": response.request.method,
                    "content_type": response.headers.get("content-type", ""),
                }
            )

        page.on("response", record_response)
        page.goto(wiki_url, wait_until="domcontentloaded", timeout=timeout_ms)
        try:
            page.wait_for_load_state("networkidle", timeout=min(timeout_ms, 5_000))
        except PlaywrightTimeoutError:
            pass
        page.wait_for_timeout(1_000)

        context.close()
        browser.close()

    responses.sort(
        key=lambda response: (
            not any(keyword in response["url"].lower() for keyword in NETWORK_PRIORITY_KEYWORDS),
            response["url"],
        )
    )
    log_path = Path("data/network_log.json")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        json.dumps(responses, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    high_priority_urls = [
        response["url"]
        for response in responses
        if any(keyword in response["url"].lower() for keyword in NETWORK_PRIORITY_KEYWORDS)
    ]
    print(f"捕获请求总数：{len(responses)}")
    print(f"网络日志已保存至：{log_path}")
    print("高优先级 URL：")
    print(json.dumps(high_priority_urls, ensure_ascii=False, indent=2))


def build_tree(state_path: Path) -> None:
    """Recursively request tree/get_info and write a restricted local tree."""
    require_state_file(state_path)
    network_log_path = Path("data/network_log.json")
    if not network_log_path.exists():
        raise FileNotFoundError(f"未找到网络日志：{network_log_path}")

    network_log = json.loads(network_log_path.read_text(encoding="utf-8"))
    tree_url = next(
        (
            record["url"]
            for record in network_log
            if "/space/api/wiki/v2/tree/get_info/" in record.get("url", "")
        ),
        None,
    )
    if tree_url is None:
        raise ValueError("网络日志中未找到 /space/api/wiki/v2/tree/get_info/ URL")

    parsed_url = urlparse(tree_url)
    root_tokens = parse_qs(parsed_url.query).get("wiki_token", [])
    if not root_tokens:
        raise ValueError("tree/get_info URL 中未找到 wiki_token")
    root_token = root_tokens[0]

    def url_for_token(wiki_token: str) -> str:
        query = [
            (key, wiki_token if key == "wiki_token" else value)
            for key, value in parse_qsl(parsed_url.query, keep_blank_values=True)
        ]
        return urlunparse(parsed_url._replace(query=urlencode(query)))

    all_nodes: dict[str, dict[str, object]] = {}
    all_children: dict[str, list[str]] = {}
    pending_tokens = [root_token]
    requested_tokens: set[str] = set()

    with sync_playwright() as playwright:
        request_context = playwright.request.new_context(storage_state=str(state_path))
        while pending_tokens:
            wiki_token = pending_tokens.pop(0)
            if wiki_token in requested_tokens:
                continue
            requested_tokens.add(wiki_token)

            response = request_context.get(url_for_token(wiki_token))
            if not response.ok:
                request_context.dispose()
                raise ValueError(
                    f"tree/get_info 请求失败：{wiki_token}，HTTP 状态码：{response.status}"
                )
            tree = response.json()["data"]["tree"]
            response_nodes = tree["nodes"]
            all_nodes.update(response_nodes)
            all_children.update(tree["child_map"])

            for token, node in response_nodes.items():
                if node.get("has_child") and token not in requested_tokens:
                    pending_tokens.append(token)
        request_context.dispose()

    def build_node(wiki_token: str, ancestry: set[str]) -> dict[str, object] | None:
        if wiki_token in ancestry or wiki_token not in all_nodes:
            return None
        source = all_nodes[wiki_token]
        child_nodes = [
            child
            for child_token in all_children.get(wiki_token, [])
            if (child := build_node(child_token, ancestry | {wiki_token})) is not None
        ]
        return {
            "title": source.get("title", ""),
            "wiki_token": source.get("wiki_token", wiki_token),
            "url": source.get("url", ""),
            "obj_token": source.get("obj_token", ""),
            "has_child": source.get("has_child", False),
            "children": child_nodes,
        }

    full_tree = build_node(root_token, set())
    if full_tree is None:
        raise ValueError("根 wiki_token 未出现在 tree/get_info 的 nodes 中")

    output_path = Path("data/full_wiki_tree.json")
    output_path.write_text(
        json.dumps(full_tree, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    flat_nodes = _flatten_tree([full_tree])
    max_level = _max_tree_level(full_tree)
    titles = [node["title"] for node in flat_nodes]
    child_count = sum(node["has_child"] for node in flat_nodes)
    print(f"总节点数量：{len(flat_nodes)}")
    print(f"叶子节点数量：{len(flat_nodes) - child_count}")
    print(f"有子节点数量：{child_count}")
    print(f"最大层级：{max_level}")
    print("前 20 个标题：")
    print(json.dumps(titles[:20], ensure_ascii=False, indent=2))


def _flatten_tree(nodes: list[dict[str, object]]) -> list[dict[str, object]]:
    flattened: list[dict[str, object]] = []
    for node in nodes:
        flattened.append(node)
        flattened.extend(_flatten_tree(node["children"]))
    return flattened


def _max_tree_level(node: dict[str, object]) -> int:
    children = node["children"]
    if not children:
        return 1
    return 1 + max(_max_tree_level(child) for child in children)


def export_all_browser(state_path: Path, output_root: Path) -> None:
    """Delegate every Wiki node export to the project feishu-docx CLI."""
    require_state_file(state_path)
    tree_path = Path("data/full_wiki_tree.json")
    if not tree_path.exists():
        raise FileNotFoundError(f"未找到完整目录树：{tree_path}")

    if not PROJECT_FEISHU_DOCX.is_file() or not (
        PROJECT_FEISHU_DOCX.stat().st_mode & 0o111
    ):
        raise FileNotFoundError(
            "未找到可执行的项目 feishu-docx CLI："
            f"{PROJECT_FEISHU_DOCX}。请在项目根目录执行 requirements.txt 安装步骤。"
        )
    cli_path = str(PROJECT_FEISHU_DOCX)

    root_node = json.loads(tree_path.read_text(encoding="utf-8"))
    if not isinstance(root_node, dict):
        raise ValueError("full_wiki_tree.json 根节点不是对象")

    def safe_path_part(value: object, fallback: str) -> str:
        title = str(value or fallback).strip()
        safe_title = "".join(
            "_" if character in '/\\:*?\"<>|' else character for character in title
        ).rstrip(".")
        return safe_title or fallback

    export_items: list[tuple[dict[str, object], list[str]]] = []

    def collect_export_nodes(node: dict[str, object], ancestors: list[str]) -> None:
        current_title = safe_path_part(
            node.get("title"), str(node.get("wiki_token", "untitled"))
        )
        export_items.append((node, ancestors))
        children = node.get("children", [])
        if isinstance(children, list):
            for child in children:
                if isinstance(child, dict):
                    collect_export_nodes(child, ancestors + [current_title])

    collect_export_nodes(root_node, [])

    output_root.mkdir(parents=True, exist_ok=True)
    failure_log_path = output_root / "export_failures_browser.jsonl"
    failure_log_path.write_text("", encoding="utf-8")
    used_paths: set[Path] = set()
    exported_count = 0
    failure_count = 0
    export_started = time.perf_counter()
    total_items = len(export_items)
    print(f"发现节点数量：{total_items}", flush=True)

    for index, (export_node, ancestors) in enumerate(export_items, start=1):
        title = str(export_node.get("title", ""))
        url = str(export_node.get("url", ""))
        wiki_token = str(export_node.get("wiki_token", ""))
        page_started = time.perf_counter()
        print(f"[{index}/{total_items}] 正在导出：\n{title}", flush=True)
        try:
            if not url:
                raise ValueError("叶子节点缺少 URL")
            output_dir = output_root.joinpath(*ancestors[1:])
            output_name = safe_path_part(title, wiki_token or "untitled")
            output_path = output_dir / f"{output_name}.md"
            if output_path in used_paths:
                output_name = f"{output_name}_{wiki_token}"
                output_path = output_dir / f"{output_name}.md"
            used_paths.add(output_path)
            output_dir.mkdir(parents=True, exist_ok=True)

            command = [
                cli_path,
                "export-browser",
                url,
                "--storage-state",
                str(state_path),
                "--output",
                str(output_dir),
                "--name",
                output_name,
            ]
            result = subprocess.run(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                print("第一次失败，等待重试...", flush=True)
                time.sleep(3)
                result = subprocess.run(
                    command,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                )
            if result.returncode != 0:
                raise RuntimeError(
                    f"feishu-docx 退出码 {result.returncode}: {result.stderr[-1_000:].strip()}"
                )
            validate_export_output(output_path)
            exported_count += 1
            print("✓ 成功", flush=True)
            print(f"耗时：{time.perf_counter() - page_started:.2f}秒", flush=True)
        except Exception as error:
            failure_count += 1
            with failure_log_path.open("a", encoding="utf-8") as failure_log:
                failure_log.write(
                    json.dumps(
                        {
                            "title": title,
                            "wiki_token": wiki_token,
                            "url": url,
                            "error_type": type(error).__name__,
                            "error": str(error),
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )

    print("导出完成", flush=True)
    print(f"节点总数：{total_items}", flush=True)
    print(f"成功：{exported_count}", flush=True)
    print(f"失败：{failure_count}", flush=True)
    print(f"总耗时：{time.perf_counter() - export_started:.2f}秒", flush=True)
    print(f"导出目录：{output_root}")
    print(f"失败日志：{failure_log_path}")
    if failure_count:
        raise SystemExit(f"导出失败：{failure_count} 个节点未通过导出或完整性校验。")


def validate_export_output(markdown_path: Path) -> None:
    """Verify the output conditions required before a node counts as exported."""
    if not markdown_path.is_file():
        raise FileNotFoundError(f"未生成 Markdown 文件：{markdown_path}")
    if markdown_path.stat().st_size == 0:
        raise ValueError(f"Markdown 文件为空：{markdown_path}")

    markdown = markdown_path.read_text(encoding="utf-8")
    if "browser-asset://" in markdown:
        raise ValueError(f"Markdown 仍包含 browser-asset 占位符：{markdown_path}")

    for raw_reference in MARKDOWN_IMAGE_REFERENCE_PATTERN.findall(markdown):
        reference = raw_reference.strip().strip("<>")
        parsed_reference = urlparse(reference)
        if parsed_reference.scheme or reference.startswith("//"):
            continue
        image_path = Path(unquote(reference))
        if not image_path.is_absolute():
            image_path = markdown_path.parent / image_path
        if not image_path.is_file():
            raise FileNotFoundError(
                f"Markdown 图片引用缺少本地文件：{reference}（来自 {markdown_path}）"
            )


def create_context(browser: Browser, state_path: Path) -> BrowserContext:
    if state_path.exists():
        return browser.new_context(storage_state=str(state_path))
    return browser.new_context()


def save_login_state(wiki_url: str, state_path: Path) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = create_context(browser, state_path)
        page = context.new_page()
        page.goto(wiki_url, wait_until="domcontentloaded")

        input("请完成飞书登录（如需），确认页面可访问后按 Enter 保存登录状态…")
        context.storage_state(path=str(state_path))
        print(f"登录状态已保存至：{state_path}")

        context.close()
        browser.close()


def main() -> None:
    args = parse_args()
    if args.command == "login":
        save_login_state(args.wiki_url, args.state_path)
    elif args.command == "capture-network":
        try:
            capture_network(args.wiki_url, args.state_path, args.timeout_ms)
        except FileNotFoundError as error:
            raise SystemExit(f"错误：{error}") from error
    elif args.command == "build-tree":
        try:
            build_tree(args.state_path)
        except (FileNotFoundError, ValueError, KeyError, json.JSONDecodeError) as error:
            raise SystemExit(f"错误：{error}") from error
    elif args.command == "export-all-browser":
        try:
            export_all_browser(args.state_path, args.output_dir)
        except (FileNotFoundError, ValueError, KeyError, json.JSONDecodeError) as error:
            raise SystemExit(f"错误：{error}") from error


if __name__ == "__main__":
    main()
