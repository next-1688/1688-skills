#!/usr/bin/env python3
"""
运营日报模块 - 今日复盘简报

Usage:
    python3 summary.py
"""

import json
import os
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from _const import DATA_DIR, PUBLISH_DATA_DIR


def _safe_read_json(filepath: Path) -> Dict[str, Any]:
    try:
        with filepath.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def _is_today_from_name(name: str, prefix: str, today_key: str) -> bool:
    # 例如: 1688_20260317_222131.json / publish_20260317_222131.json
    if not name.startswith(prefix):
        return False
    parts = name.replace(".json", "").split("_")
    if len(parts) < 3:
        return False
    return parts[1] == today_key


def _is_today_from_timestamp(timestamp_text: str, today: datetime) -> bool:
    try:
        ts = datetime.fromisoformat(timestamp_text)
        return ts.date() == today.date()
    except Exception:
        return False


def build_daily_summary() -> Dict[str, Any]:
    now = datetime.now()
    today_key = now.strftime("%Y%m%d")
    today_text = now.strftime("%Y-%m-%d")

    search_dir = Path(DATA_DIR)
    publish_dir = Path(PUBLISH_DATA_DIR)

    search_count = 0
    recommended_total = 0

    if search_dir.exists():
        for filepath in search_dir.glob("1688_*.json"):
            if not filepath.is_file():
                continue
            if not _is_today_from_name(filepath.name, "1688_", today_key):
                payload = _safe_read_json(filepath)
                if not _is_today_from_timestamp(str(payload.get("timestamp", "")), now):
                    continue
            else:
                payload = _safe_read_json(filepath)

            products = payload.get("products", {})
            if isinstance(products, dict):
                product_count = len(products)
            elif isinstance(products, list):
                product_count = len(products)
            else:
                product_count = 0
            search_count += 1
            recommended_total += product_count

    recommended_avg = round(recommended_total / search_count, 2) if search_count else 0

    publish_events_total = 0
    publish_dry_run_total = 0
    submitted_total = 0
    success_total = 0
    fail_total = 0
    fail_reason_counter: Counter = Counter()

    if publish_dir.exists():
        for filepath in publish_dir.glob("publish_*.json"):
            if not filepath.is_file():
                continue
            if not _is_today_from_name(filepath.name, "publish_", today_key):
                payload = _safe_read_json(filepath)
                if not _is_today_from_timestamp(str(payload.get("timestamp", "")), now):
                    continue
            else:
                payload = _safe_read_json(filepath)

            if not payload:
                continue

            publish_events_total += 1
            is_dry_run = bool(payload.get("dry_run", False))
            if is_dry_run:
                publish_dry_run_total += 1
                continue

            submitted = int(payload.get("submitted_count") or 0)
            success = int(payload.get("success_count") or 0)
            fail = int(payload.get("fail_count") or 0)
            submitted_total += submitted
            success_total += success
            fail_total += fail

            failed_items = payload.get("failed_items", [])
            if isinstance(failed_items, list):
                for item in failed_items:
                    if not isinstance(item, dict):
                        continue
                    reason = str(item.get("error") or "未知错误").strip() or "未知错误"
                    fail_reason_counter[reason] += 1

    success_rate_value = (success_total / submitted_total) if submitted_total else None
    success_rate_text = f"{success_rate_value * 100:.1f}%" if success_rate_value is not None else "-"

    fail_reason_top3: List[Dict[str, Any]] = []
    for reason, count in fail_reason_counter.most_common(3):
        fail_reason_top3.append({"reason": reason, "count": count})

    markdown_lines = [
        "## 运营视角小结报表",
        "",
        f"**日期**: {today_text}",
        "",
        "### 今日核心数据",
        f"- 搜索次数：**{search_count}**",
        f"- 推荐商品总数：**{recommended_total}**",
        f"- 平均每次推荐：**{recommended_avg}**",
        f"- 正式铺货成功率：**{success_rate_text}**",
        f"- 正式铺货：提交 **{submitted_total}** / 成功 **{success_total}** / 失败 **{fail_total}**",
    ]

    if publish_dry_run_total:
        markdown_lines.append(f"- 预检查次数（dry-run）：**{publish_dry_run_total}**")

    markdown_lines.extend(["", "### 失败原因 Top3"])
    if fail_reason_top3:
        for index, item in enumerate(fail_reason_top3, 1):
            markdown_lines.append(f"{index}. {item['reason']}（{item['count']} 次）")
    else:
        markdown_lines.append("- 今日暂无失败原因记录")

    markdown_lines.extend(["", "### 运营建议"])
    if search_count == 0:
        markdown_lines.append("- 今天还没有搜索记录，先执行一次 search 建立选品样本。")
    elif recommended_avg < 5:
        markdown_lines.append("- 每次推荐数量偏少，可适当放宽关键词描述并减少限制条件。")
    else:
        markdown_lines.append("- 选品供给量正常，建议优先复盘高转化类目并持续迭代关键词。")

    if submitted_total == 0:
        markdown_lines.append("- 今天还未执行正式铺货，可先 dry-run 预检查后再正式提交。")
    elif success_rate_value is not None and success_rate_value < 0.8:
        markdown_lines.append("- 铺货成功率偏低，建议优先处理 Top 失败原因后再批量铺货。")
    else:
        markdown_lines.append("- 铺货执行稳定，可扩大同类商品测试规模。")

    return {
        "success": True,
        "markdown": "\n".join(markdown_lines),
        "data": {
            "date": today_text,
            "search_count": search_count,
            "recommended_products_total": recommended_total,
            "recommended_products_avg": recommended_avg,
            "publish_events_total": publish_events_total,
            "publish_dry_run_total": publish_dry_run_total,
            "publish_submitted_total": submitted_total,
            "publish_success_total": success_total,
            "publish_fail_total": fail_total,
            "publish_success_rate": success_rate_value,
            "publish_success_rate_display": success_rate_text,
            "fail_reason_top3": fail_reason_top3,
        },
    }


def main():
    try:
        output = build_daily_summary()
    except Exception as e:
        output = {
            "success": False,
            "markdown": f"生成运营小结失败：{e}",
            "data": {},
        }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
