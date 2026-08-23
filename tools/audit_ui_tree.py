#!/usr/bin/env python3
"""Audit the rendered Feishu Wiki sidebar against the locally built API tree.

This is a test-only diagnostic. It uses an existing Playwright storage state,
expands visible sidebar controls conservatively, and writes local metadata only.
It never downloads page bodies or resources.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from playwright.sync_api import Page, sync_playwright


def normalise_title(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def flatten_tree(node: dict[str, Any]) -> list[dict[str, Any]]:
    items = [node]
    for child in node.get("children", []):
        if isinstance(child, dict):
            items.extend(flatten_tree(child))
    return items


def collect_visible_sidebar_items(page: Page) -> dict[str, list[dict[str, Any]]]:
    """Collect sidebar-ish tree items and real Wiki anchors currently in the DOM."""
    return page.evaluate(
        """() => {
          const isVisible = (element) => {
            const rect = element.getBoundingClientRect();
            const style = getComputedStyle(element);
            return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
          };
          const inLeftPane = (element) => {
            const rect = element.getBoundingClientRect();
            return rect.left < window.innerWidth * 0.55;
          };
          const wantedAttributes = (element) => Object.fromEntries(
            [...element.attributes]
              .filter((attribute) => /wiki|token|node|url|href|title|level|expanded/i.test(attribute.name))
              .map((attribute) => [attribute.name, attribute.value])
          );
          const anchors = [...document.querySelectorAll('a[href*="/wiki/"]')]
            .filter((element) => isVisible(element) && inLeftPane(element))
            .map((element) => ({
              title: (element.innerText || element.textContent || '').trim(),
              url: element.href,
              attributes: wantedAttributes(element),
            }));
          const candidates = [...document.querySelectorAll(
            '[role="treeitem"], [aria-level], [data-wiki-token], [data-node-id]'
          )]
            .filter((element) => isVisible(element) && inLeftPane(element))
            .map((element) => {
              const link = element.closest('a[href*="/wiki/"]') || element.querySelector('a[href*="/wiki/"]');
              return {
                title: (element.innerText || element.textContent || '').trim(),
                url: link ? link.href : null,
                attributes: wantedAttributes(element),
              };
            });
          return { anchors, treeItems: candidates };
        }"""
    )


def click_one_collapsed_sidebar_control(page: Page) -> bool:
    """Click one visible collapsed control in a sidebar/tree region, if present."""
    return bool(
        page.evaluate(
            """() => {
              const visible = (element) => {
                const rect = element.getBoundingClientRect();
                const style = getComputedStyle(element);
                return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
              };
              const elements = [...document.querySelectorAll('[aria-expanded="false"]')];
              const target = elements.find((element) => {
                const rect = element.getBoundingClientRect();
                const shell = element.closest('[role="tree"], nav, aside, [class*="sidebar" i], [class*="catalog" i], [class*="wiki" i]');
                return visible(element) && rect.left < window.innerWidth * 0.55 && shell;
              });
              if (!target) return false;
              target.click();
              return true;
            }"""
        )
    )


def click_root_tree_expand(page: Page) -> bool:
    """Click Feishu's root sidebar-tree control once, never a document link."""
    return bool(
        page.evaluate(
            """() => {
              const target = document.querySelector('[data-e2e="wiki-space-detail-tree-expand-btn"]');
              if (!target) return false;
              const rect = target.getBoundingClientRect();
              if (rect.width <= 0 || rect.height <= 0) return false;
              target.click();
              return true;
            }"""
        )
    )


def collect_expansion_candidates(page: Page) -> list[dict[str, Any]]:
    """Report visible left-pane controls before choosing a click selector."""
    return page.evaluate(
        """() => {
          const visible = (element) => {
            const rect = element.getBoundingClientRect();
            const style = getComputedStyle(element);
            return rect.width > 0 && rect.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
          };
          const cleanAttributes = (element) => Object.fromEntries(
            [...element.attributes]
              .filter((attribute) => /aria|role|title|class|data/i.test(attribute.name))
              .map((attribute) => [attribute.name, attribute.value])
          );
          return [...document.querySelectorAll('[aria-expanded], button, [role="button"]')]
            .filter((element) => {
              const rect = element.getBoundingClientRect();
              const hint = [element.getAttribute('aria-label'), element.getAttribute('title'), element.innerText, element.textContent]
                .filter(Boolean).join(' ');
              return visible(element) && rect.left < window.innerWidth * 0.55 &&
                (element.hasAttribute('aria-expanded') || /展开|收起|expand|collapse|目录|tree/i.test(hint));
            })
            .map((element) => ({
              tag: element.tagName,
              text: (element.innerText || element.textContent || '').trim().slice(0, 80),
              attributes: cleanAttributes(element),
            }));
        }"""
    )


def scroll_sidebar_containers(page: Page) -> int:
    """Advance scrollable sidebar/tree containers and return how many moved."""
    return int(
        page.evaluate(
            """() => {
              const selectors = '[role="tree"], nav, aside, [class*="sidebar" i], [class*="catalog" i], [class*="wiki" i]';
              const seen = new Set();
              let moved = 0;
              for (const element of document.querySelectorAll(selectors)) {
                if (seen.has(element)) continue;
                seen.add(element);
                const rect = element.getBoundingClientRect();
                if (rect.left >= window.innerWidth * 0.55) continue;
                if (element.scrollHeight <= element.clientHeight + 4) continue;
                const before = element.scrollTop;
                element.scrollTop = Math.min(
                  element.scrollTop + Math.max(160, Math.floor(element.clientHeight * 0.8)),
                  element.scrollHeight
                );
                if (element.scrollTop > before) moved += 1;
              }
              return moved;
            }"""
        )
    )


def unique_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        key = json.dumps(item, ensure_ascii=False, sort_keys=True)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit rendered Wiki sidebar coverage")
    parser.add_argument("wiki_url", help="Feishu Wiki homepage URL")
    parser.add_argument("--state-path", type=Path, default=Path("data/storage_state.json"))
    parser.add_argument("--tree-path", type=Path, default=Path("data/full_wiki_tree.json"))
    parser.add_argument("--output", type=Path, default=Path("data/ui_tree_audit.json"))
    parser.add_argument("--wait-ms", type=int, default=5000)
    args = parser.parse_args()

    if not args.state_path.exists():
        raise SystemExit(f"未找到登录状态：{args.state_path}")
    if not args.tree_path.exists():
        raise SystemExit(f"未找到 API 目录树：{args.tree_path}")

    api_root = json.loads(args.tree_path.read_text(encoding="utf-8"))
    api_items = flatten_tree(api_root)
    api_titles = {normalise_title(str(item.get("title", ""))) for item in api_items}
    observed_anchors: list[dict[str, Any]] = []
    observed_tree_items: list[dict[str, Any]] = []

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)
        context = browser.new_context(storage_state=str(args.state_path))
        page = context.new_page()
        page.goto(args.wiki_url, wait_until="domcontentloaded")
        page.wait_for_timeout(args.wait_ms)
        input("请确认 Wiki 左侧目录已显示，然后按 Enter 开始审计…")

        expansion_candidates = collect_expansion_candidates(page)
        before_root_click = collect_visible_sidebar_items(page)
        root_tree_expand_clicked = click_root_tree_expand(page)
        if root_tree_expand_clicked:
            page.wait_for_timeout(700)
            after_root_click = collect_visible_sidebar_items(page)
            if len(after_root_click["anchors"]) < len(before_root_click["anchors"]):
                click_root_tree_expand(page)
                page.wait_for_timeout(500)
                root_tree_expand_clicked = False

        expansion_clicks = 0
        for _ in range(40):
            snapshot = collect_visible_sidebar_items(page)
            observed_anchors.extend(snapshot["anchors"])
            observed_tree_items.extend(snapshot["treeItems"])
            if not click_one_collapsed_sidebar_control(page):
                break
            expansion_clicks += 1
            page.wait_for_timeout(350)

        for _ in range(30):
            snapshot = collect_visible_sidebar_items(page)
            observed_anchors.extend(snapshot["anchors"])
            observed_tree_items.extend(snapshot["treeItems"])
            if scroll_sidebar_containers(page) == 0:
                break
            page.wait_for_timeout(250)

        snapshot = collect_visible_sidebar_items(page)
        observed_anchors.extend(snapshot["anchors"])
        observed_tree_items.extend(snapshot["treeItems"])
        context.close()
        browser.close()

    anchors = unique_items(observed_anchors)
    tree_items = unique_items(observed_tree_items)
    ui_titles = {
        normalise_title(str(item.get("title", "")))
        for item in [*anchors, *tree_items]
        if normalise_title(str(item.get("title", "")))
    }
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "wiki_url": args.wiki_url,
        "automated_expansion_clicks": expansion_clicks,
        "api_tree": {"node_count": len(api_items), "titles": sorted(api_titles)},
        "ui_sidebar": {"anchors": anchors, "tree_items": tree_items},
        "expansion_candidates": expansion_candidates,
        "root_tree_expand_clicked": root_tree_expand_clicked,
        "comparison": {
            "ui_title_count": len(ui_titles),
            "ui_titles_not_in_api_tree": sorted(ui_titles - api_titles),
            "api_titles_not_seen_in_ui": sorted(api_titles - ui_titles),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"API 树节点数：{len(api_items)}")
    print(f"UI 锚点数量：{len(anchors)}")
    print(f"UI 目录元素数量：{len(tree_items)}")
    print(f"候选展开控件数量：{len(expansion_candidates)}")
    print(f"根目录展开点击：{root_tree_expand_clicked}")
    print(f"UI 标题数：{len(ui_titles)}")
    print(f"UI 有、API 树没有的标题：{len(report['comparison']['ui_titles_not_in_api_tree'])}")
    print(f"审计报告：{args.output}")


if __name__ == "__main__":
    main()
