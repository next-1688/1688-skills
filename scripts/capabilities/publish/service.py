#!/usr/bin/env python3
"""铺货服务 — 商品铺货到下游店铺"""

import json
import os
from dataclasses import dataclass
from typing import List, Optional

from _http import api_post
from _const import CHANNEL_MAP, DATA_DIR, PUBLISH_LIMIT
from _errors import SkillError
from capabilities.shops.service import list_bound_shops


@dataclass
class PublishResult:
    """铺货结果"""
    success: bool
    submitted_count: int = 0
    error_code: str = ""    # "210" / "511" / "512" / "500" / ""
    error_message: str = ""


_ERROR_MESSAGES = {
    "210": "有部分提交失败，请前往【分销管理-铺货失败】查看明细",
    "511": "下游店铺授权信息失效，请重新授权",
    "512": "您未完成铺货设置，请先完成铺货设置",
    "500": "三方工具服务请求错误，请稍后重试",
}


def _parse_error_code(mcd: dict) -> str:
    """从 mcd.data（JSON 字符串）中提取 outShops[0].errorCode"""
    mcd_data_str = mcd.get("data", "")
    try:
        mcd_data = json.loads(mcd_data_str) if mcd_data_str else {}
    except Exception:
        mcd_data = {}
    out_shops = mcd_data.get("outShops", [])
    if not out_shops:
        return ""
    code = out_shops[0].get("errorCode", "") or ""
    return str(code)


def load_products_by_data_id(data_id: str) -> Optional[List[str]]:
    """根据 data_id 加载商品ID列表，未找到返回 None"""
    filepath = os.path.join(DATA_DIR, f"1688_{data_id}.json")
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        products = data.get("products", {})
        if isinstance(products, dict):
            return list(products.keys())
        elif isinstance(products, list):
            return [p.get("id") for p in products if p.get("id")]
        return []
    except Exception:
        return None


def normalize_item_ids(raw_item_ids: List[str]) -> List[str]:
    """清洗并去重商品ID，保留顺序"""
    seen = set()
    cleaned = []
    for item_id in raw_item_ids:
        if not item_id or item_id in seen:
            continue
        seen.add(item_id)
        cleaned.append(item_id)
    return cleaned


def publish_items(item_ids: List[str], shop_code: str,
                  channel: Optional[str] = None) -> PublishResult:
    """
    铺货到指定店铺

    写操作内部捕获 API 异常并返回 PublishResult(success=False)，
    因为铺货有"部分成功"语义，调用方需要统一结构。
    """
    if not channel:
        shops = list_bound_shops()
        target_shop = next((s for s in shops if s.code == shop_code), None)
        if not target_shop:
            return PublishResult(success=False, error_message="店铺不存在")
        if not target_shop.is_authorized:
            return PublishResult(success=False, error_message="店铺授权已过期")
        channel = CHANNEL_MAP.get(target_shop.channel)
        if not channel:
            return PublishResult(success=False,
                                 error_message=f"未知渠道: {target_shop.channel}")

    submitted_count = len(item_ids[:PUBLISH_LIMIT])

    try:
        model = api_post("/1688claw/skill/distributingoffer", {
            "offerIdList": ",".join(item_ids[:PUBLISH_LIMIT]),
            "channel": channel,
            "shopCode": shop_code,
        }, timeout=60)
    except SkillError as e:
        return PublishResult(
            success=False,
            submitted_count=submitted_count,
            error_message=e.message,
        )

    mcd = model.get("mcd", {})
    biz_success = mcd.get("bizSuccess", False)
    error_code = _parse_error_code(mcd)

    # 全量成功：bizSuccess=True 且无异常 errorCode（空/"0"）
    is_success = biz_success and error_code in ("", "0")

    if is_success:
        return PublishResult(success=True, submitted_count=submitted_count)

    # 部分失败（210）归为 success=True，其余归为 success=False
    if error_code == "210":
        return PublishResult(
            success=True,
            submitted_count=submitted_count,
            error_code=error_code,
            error_message=_ERROR_MESSAGES["210"],
        )

    error_message = _ERROR_MESSAGES.get(error_code, "铺货失败，请重试")
    return PublishResult(
        success=False,
        submitted_count=submitted_count,
        error_code=error_code,
        error_message=error_message,
    )


def format_publish_result(result: PublishResult, shop_name: str = "",
                          origin_count: int = 0) -> str:
    """格式化铺货结果为 Markdown"""
    lines = ["## 铺货结果\n"]
    if shop_name:
        lines.append(f"**目标店铺**: {shop_name}\n")

    n = result.submitted_count
    if origin_count > PUBLISH_LIMIT:
        lines.append(f"- ⚠️ 检测到商品总数 {origin_count}，按接口限制仅提交前 {PUBLISH_LIMIT} 个\n")

    if result.success and not result.error_code:
        lines.append(f"✅ 共 {n} 个商品，已全部提交成功！")
        lines.append("请前往【下游店铺-铺货成功】查看明细。")
    elif result.error_code == "210":
        lines.append(f"⚠️ 共 {n} 个商品，部分提交成功，有部分失败。")
        lines.append("建议稍后重试失败的商品，或检查商品信息是否完整。")
        lines.append("可前往【分销管理-铺货失败】查看明细。")
    elif result.error_code == "511":
        lines.append(f"❌ **铺货失败**（共 {n} 个商品）")
        lines.append(f"\n**原因**：{result.error_message}")
        lines.append("\n**建议**：请重新授权后重试。")
    elif result.error_code == "512":
        lines.append(f"❌ **铺货失败**（共 {n} 个商品）")
        lines.append(f"\n**原因**：{result.error_message}")
        lines.append("\n**建议**：请先完成铺货设置后重试。")
    else:
        lines.append(f"❌ **铺货失败**（共 {n} 个商品）")
        if result.error_message:
            lines.append(f"\n**原因**：{result.error_message}")
        lines.append("\n**建议**：")
        lines.append("1. 检查店铺授权是否过期")
        lines.append("2. 确认商品信息完整")
        lines.append("3. 稍后重试")

    return "\n".join(lines)


def publish_with_check(item_ids: List[str], shop_code: str,
                       dry_run: bool = False) -> dict:
    """带店铺校验的铺货（主流程入口）"""
    shops = list_bound_shops()
    target_shop = next((s for s in shops if s.code == shop_code), None)

    if not target_shop:
        return {
            "success": False,
            "markdown": "❌ 店铺不存在，请检查店铺代码。",
            "result": PublishResult(success=False, error_message="店铺不存在"),
            "origin_count": len(item_ids),
        }

    if not target_shop.is_authorized:
        return {
            "success": False,
            "markdown": f"❌ 店铺「{target_shop.name}」授权已过期，请在1688 AI版APP中重新授权。",
            "result": PublishResult(success=False, error_message="授权过期"),
            "origin_count": len(item_ids),
        }

    origin_count = len(item_ids)

    if dry_run:
        preview_count = min(origin_count, PUBLISH_LIMIT)
        markdown = (
            "## 铺货预检查结果\n\n"
            f"✅ 店铺校验通过：{target_shop.name}\n"
            f"- 来源商品数：{origin_count}\n"
            f"- 实际将提交：{preview_count}\n"
            + (f"- ⚠️ 超出接口限制，仅会提交前 {PUBLISH_LIMIT} 个\n"
               if origin_count > PUBLISH_LIMIT else "")
            + "\n确认后去掉 `--dry-run` 执行正式铺货。"
        )
        return {
            "success": True, "markdown": markdown,
            "result": PublishResult(success=True, submitted_count=preview_count),
            "origin_count": origin_count,
        }

    channel = CHANNEL_MAP.get(target_shop.channel)
    if not channel:
        return {
            "success": False,
            "markdown": f"❌ 店铺「{target_shop.name}」的渠道「{target_shop.channel}」无法识别，请联系客服确认。",
            "result": PublishResult(success=False,
                                    error_message=f"未知渠道: {target_shop.channel}"),
            "origin_count": origin_count,
        }

    result = publish_items(item_ids, shop_code, channel=channel)
    markdown = format_publish_result(result, target_shop.name, origin_count=origin_count)

    return {
        "success": result.success, "markdown": markdown,
        "result": result, "origin_count": origin_count,
    }
