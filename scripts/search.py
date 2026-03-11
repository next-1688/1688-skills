#!/usr/bin/env python3
"""
选品模块 - 商品搜索和结果处理

Usage:
    python3 search.py --query "连衣裙" [--channel douyin]
"""

import argparse
import os
import json
from datetime import datetime
from pathlib import Path
from typing import List

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _api import search_products, Product
from _const import DATA_DIR


def save_search_result(products: List[Product], query: str, channel: str) -> str:
    """
    保存搜索结果到文件（含完整 stats）

    Returns:
        data_id (时间戳格式)
    """
    data_dir = DATA_DIR
    Path(data_dir).mkdir(parents=True, exist_ok=True)

    data_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(data_dir, f"1688_{data_id}.json")

    products_map = {}
    for p in products:
        entry = {
            "title": p.title,
            "price": p.price,
            "image": p.image,
        }
        if p.stats:
            entry["stats"] = p.stats
        products_map[p.id] = entry

    data = {
        "query": query,
        "channel": channel,
        "timestamp": datetime.now().isoformat(),
        "data_id": data_id,
        "products": products_map,
    }

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return data_id


def _fmt_rate(v):
    """小数转百分比，如 0.857 → 85.7%；无值返回 -"""
    if v is None:
        return "-"
    try:
        f = float(v)
        return f"{f * 100:.1f}%" if f <= 1.0 else f"{f:.1f}%"
    except (TypeError, ValueError):
        return str(v)


def format_product_list(products: List[Product], max_show: int = 20) -> str:
    """格式化商品列表为 Markdown 表格"""
    if not products:
        return "未找到符合条件的商品。"

    lines = [f"找到 **{len(products)}** 个商品：\n"]
    lines.append("| # | 商品 | 价格 | 30天销量 | 好评率 | 复购率 | 铺货数 | 揽收率 |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- |")

    for i, p in enumerate(products[:max_show], 1):
        s = p.stats or {}
        sales = s.get("last30DaysSales", "-") if s.get("last30DaysSales") is not None else "-"
        good = _fmt_rate(s.get("goodRates"))
        repurchase = _fmt_rate(s.get("repurchaseRate"))
        downstream = s.get("downstreamOffer", "-") if s.get("downstreamOffer") is not None else "-"
        collection = _fmt_rate(s.get("collectionRate24h"))
        title = p.title.replace("|", "\\|")
        lines.append(f"| {i} | [{title}]({p.url}) | ¥{p.price} | {sales} | {good} | {repurchase} | {downstream} | {collection} |")

    if len(products) > max_show:
        lines.append(f"\n*... 还有 {len(products) - max_show} 个商品，完整数据见 JSON 输出*")

    return "\n".join(lines)


def search_and_save(query: str, channel: str = "") -> dict:
    """
    搜索并保存结果

    Returns:
        {"products": List[Product], "data_id": str, "markdown": str}
    """
    products = search_products(query, channel)

    if not products:
        return {
            "products": [],
            "data_id": "",
            "markdown": "未找到商品，请尝试更换关键词。",
        }

    data_id = save_search_result(products, query, channel)
    markdown = format_product_list(products)

    return {
        "products": products,
        "data_id": data_id,
        "markdown": markdown,
    }


def _product_to_dict(p: Product) -> dict:
    """将 Product 转为可 JSON 序列化的 dict"""
    d = {"id": p.id, "title": p.title, "price": p.price, "url": p.url}
    if p.stats:
        d["stats"] = p.stats
    return d


def main():
    import os
    if not os.environ.get("ALI_1688_AK"):
        print(json.dumps({
            "success": False,
            "markdown": "❌ AK 未配置，无法搜索商品。\n\n运行: `cli.py configure YOUR_AK`",
            "data": {"data_id": "", "product_count": 0, "products": []},
        }, ensure_ascii=False, indent=2))
        return

    parser = argparse.ArgumentParser(description="1688 商品搜索")
    parser.add_argument("--query", "-q", required=True, help="搜索关键词（自然语言描述）")
    parser.add_argument("--channel", "-c", default="",
                        choices=["", "douyin", "taobao", "pinduoduo", "xiaohongshu"],
                        help="下游渠道（可选；未识别渠道意图时留空）")
    args = parser.parse_args()

    try:
        result = search_and_save(args.query, args.channel)
        output = {
            "success": True,
            "markdown": result["markdown"],
            "data": {
                "data_id": result["data_id"],
                "product_count": len(result["products"]),
                "products": [_product_to_dict(p) for p in result["products"]],
            },
        }
    except Exception as e:
        output = {
            "success": False,
            "markdown": f"搜索失败（网络异常，已重试3次）：{e}",
            "data": {"data_id": "", "product_count": 0, "products": []},
        }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
