#!/usr/bin/env python3
"""
1688-shopkeeper —— 1688 AI 店长 CLI 统一入口

在 1688 AI 版 APP 中配置 AK 并绑定下游店铺后，可通过本 CLI：选品搜货、查商品详情、
查看已绑定店铺（抖店/拼多多/小红书/淘宝）、铺货上架，以及商机热榜、类目/行业趋势、
店铺经营日报等。子命令位于 scripts/capabilities/<能力名>/cmd.py，启动时自动扫描注册。

Usage:
    python3 cli.py <command> [options]

Commands（更多参数见项目根目录 SKILL.md）:
    search        搜商品          python3 cli.py search --query "..." [--channel douyin]
    prod_detail   商品详情        python3 cli.py prod_detail --item-ids "id1,id2"
    shops         查绑定店铺      python3 cli.py shops
    publish       铺货到下游      python3 cli.py publish --shop-code XXX (--data-id Y | --item-ids a,b)
    opportunities 商机热榜        python3 cli.py opportunities
    trend         趋势洞察        python3 cli.py trend --query "大码女装"
    shop_daily    店铺经营日报    python3 cli.py shop_daily
    configure     配置 AK         python3 cli.py configure YOUR_AK
    check         检查配置状态    python3 cli.py check

所有命令输出 JSON: {"success": bool, "markdown": str, "data": {...}}
面向用户展示时优先使用 markdown；Agent 追加分析时不要写入 markdown 正文。
"""

import json
import os
import sys
import importlib

SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts")
sys.path.insert(0, SCRIPTS_DIR)


def _discover_capabilities() -> dict:
    """扫描 capabilities/*/cmd.py，自动注册命令"""
    commands = {}
    caps_dir = os.path.join(SCRIPTS_DIR, "capabilities")

    if not os.path.isdir(caps_dir):
        return commands

    for name in sorted(os.listdir(caps_dir)):
        cmd_path = os.path.join(caps_dir, name, "cmd.py")
        if not os.path.isfile(cmd_path):
            continue
        module_path = f"capabilities.{name}.cmd"
        try:
            mod = importlib.import_module(module_path)
            cmd_name = getattr(mod, 'COMMAND_NAME', name)
            commands[cmd_name] = module_path
        except Exception:
            pass

    return commands


def _usage(commands: dict):
    lines = ["**1688-shopkeeper 用法**\n", "```"]
    for name in sorted(commands):
        try:
            mod = importlib.import_module(commands[name])
            desc = getattr(mod, 'COMMAND_DESC', '')
            lines.append(f"python3 cli.py {name:<12} {desc}")
        except Exception:
            lines.append(f"python3 cli.py {name}")
    lines.append("```")

    print(json.dumps({
        "success": False,
        "data": {},
        "markdown": "\n".join(lines),
    }, ensure_ascii=False, indent=2))


def main():
    commands = _discover_capabilities()

    if len(sys.argv) < 2 or sys.argv[1] not in commands:
        _usage(commands)
        sys.exit(1)

    cmd = sys.argv[1]
    module_path = commands[cmd]

    sys.argv = [f"cli.py {cmd}"] + sys.argv[2:]

    module = importlib.import_module(module_path)
    module.main()


if __name__ == "__main__":
    main()
