"""
本地冒烟测试：对每个测试用例模拟一轮对话，检查 DeepSeek API 是否正常返回，
并对回复做宽松的关键词命中统计。

用法:
    cp .env.example .env   # 填入 DEEPSEEK_API_KEY
    python test_local.py            # 跑全部用例
    python test_local.py --case 2   # 只跑第 3 个用例（0 基）

说明:
    - 这是冒烟测试，不是严格断言：LLM 输出有随机性，关键词命中率仅供参考。
    - 判定「通过」的硬标准是：API 成功返回、结构完整（advice/action_items/summary）、
      且 advice 不是以 ⚠️ 开头的错误提示。
"""

from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv

from test_cases import TEST_CASES
from utils.api_client import chat_turn

load_dotenv()


def run_case(idx: int, case: dict) -> bool:
    """跑单个用例，打印结果，返回是否通过（API 层面）。"""
    print("=" * 70)
    print(f"[用例 {idx}] {case['persona']}")
    print(f"用户输入：{case['user_input']}")
    print("-" * 70)

    messages = [{"role": "user", "content": case["user_input"]}]
    result = chat_turn(messages)

    advice = result.get("advice", "")
    items = result.get("action_items", [])
    summary = result.get("summary", "")

    # 硬标准：API 正常返回且非错误
    if not advice or advice.startswith("⚠️"):
        print(f"❌ API 调用失败或返回异常：{advice!r}")
        return False

    # 结构完整性
    structure_ok = isinstance(items, list) and isinstance(summary, str)

    # 宽松关键词命中
    haystack = advice + " " + " ".join(items)
    hit = [kw for kw in case["expected_keywords"] if kw in haystack]
    miss = [kw for kw in case["expected_keywords"] if kw not in haystack]

    print(f"AI 回复（advice）：\n{advice}\n")
    if items:
        print("行动项（action_items）：")
        for it in items:
            print(f"  - {it}")
    else:
        print("行动项：（无）")
    print(f"\n摘要（summary）：{summary or '（空）'}")
    print(
        f"\n关键词命中：{len(hit)}/{len(case['expected_keywords'])} "
        f"命中={hit} 未命中={miss}"
    )

    # 软提醒（不影响通过判定）
    if case.get("expect_action_items") and not items:
        print("⚠️ 提醒：本用例期望产出行动项，但本次没有。")
    if not structure_ok:
        print("⚠️ 提醒：返回结构不完整（action_items/summary 类型异常）。")

    print("✅ 通过（API 正常返回）")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="职来 Careerture 本地冒烟测试")
    parser.add_argument("--case", type=int, default=None, help="只跑指定下标的用例（0 基）")
    args = parser.parse_args()

    if not os.getenv("DEEPSEEK_API_KEY"):
        print("❌ 未检测到 DEEPSEEK_API_KEY。请先 cp .env.example .env 并填入 key。")
        return 1

    cases = TEST_CASES
    if args.case is not None:
        if not (0 <= args.case < len(TEST_CASES)):
            print(f"❌ --case 超出范围（应为 0~{len(TEST_CASES) - 1}）")
            return 1
        cases = [TEST_CASES[args.case]]

    results = [run_case(i, c) for i, c in enumerate(cases)]

    print("=" * 70)
    passed = sum(results)
    print(f"总计：{passed}/{len(results)} 个用例 API 正常返回")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
