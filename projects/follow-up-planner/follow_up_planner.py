#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""根据销售线索评分结果自动生成跟进任务计划。"""

import argparse
import csv
import sys
from datetime import date, datetime, timedelta
from pathlib import Path


INPUT_COLUMNS = {"lead_id", "company_name", "grade", "total_score"}
RULE_COLUMNS = {
    "grade",
    "follow_up_days",
    "priority",
    "next_action",
    "channel",
}
OUTPUT_COLUMNS = [
    "lead_id",
    "company_name",
    "grade",
    "total_score",
    "priority",
    "next_action",
    "channel",
    "due_date",
    "status",
]


class PlannerError(Exception):
    """面向使用者的计划生成错误。"""


def parse_base_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "日期格式必须是 YYYY-MM-DD，例如 2026-07-30"
        ) from exc


def require_columns(fieldnames, required, file_label):
    missing = sorted(required - set(fieldnames or []))
    if missing:
        raise PlannerError(
            f"{file_label}缺少必要字段：{', '.join(missing)}"
        )


def load_rules(path):
    if not path.exists():
        raise PlannerError(f"找不到跟进规则文件：{path}")

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        require_columns(reader.fieldnames, RULE_COLUMNS, "跟进规则文件")
        rules = {}

        for row_no, row in enumerate(reader, start=2):
            grade = row["grade"].strip().upper()
            if not grade:
                raise PlannerError(f"规则文件第 {row_no} 行的 grade 不能为空")
            if grade in rules:
                raise PlannerError(f"规则文件中存在重复等级：{grade}")
            try:
                follow_up_days = int(row["follow_up_days"].strip())
            except ValueError as exc:
                raise PlannerError(
                    f"规则文件第 {row_no} 行的 follow_up_days 必须是整数"
                ) from exc
            if follow_up_days < 0:
                raise PlannerError(
                    f"规则文件第 {row_no} 行的 follow_up_days 不能为负数"
                )

            rules[grade] = {
                "follow_up_days": follow_up_days,
                "priority": row["priority"].strip(),
                "next_action": row["next_action"].strip(),
                "channel": row["channel"].strip(),
            }

    required_grades = {"A", "B", "C"}
    missing_grades = sorted(required_grades - set(rules))
    if missing_grades:
        raise PlannerError(
            f"跟进规则缺少等级：{', '.join(missing_grades)}"
        )
    return rules


def load_scored_leads(path):
    if not path.exists():
        raise PlannerError(f"找不到 Day 2 评分结果：{path}")

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        require_columns(reader.fieldnames, INPUT_COLUMNS, "评分结果文件")
        leads = []

        for row_no, row in enumerate(reader, start=2):
            lead_id = row["lead_id"].strip()
            company_name = row["company_name"].strip()
            grade = row["grade"].strip().upper()
            try:
                total_score = int(row["total_score"].strip())
            except ValueError as exc:
                raise PlannerError(
                    f"评分结果第 {row_no} 行的 total_score 必须是整数"
                ) from exc

            if not lead_id:
                raise PlannerError(f"评分结果第 {row_no} 行的 lead_id 不能为空")
            if grade not in {"A", "B", "C"}:
                raise PlannerError(
                    f"评分结果第 {row_no} 行的 grade 无效：{grade}"
                )
            if not 0 <= total_score <= 100:
                raise PlannerError(
                    f"评分结果第 {row_no} 行的 total_score 超出 0–100"
                )

            leads.append(
                {
                    "lead_id": lead_id,
                    "company_name": company_name,
                    "grade": grade,
                    "total_score": total_score,
                }
            )
    return leads


def build_plan(leads, rules, base_date):
    plan = []
    for lead in leads:
        rule = rules[lead["grade"]]
        due_date = base_date + timedelta(days=rule["follow_up_days"])
        plan.append(
            {
                "lead_id": lead["lead_id"],
                "company_name": lead["company_name"],
                "grade": lead["grade"],
                "total_score": lead["total_score"],
                "priority": rule["priority"],
                "next_action": rule["next_action"],
                "channel": rule["channel"],
                "due_date": due_date.isoformat(),
                "status": "待跟进",
            }
        )

    plan.sort(
        key=lambda row: (
            row["due_date"],
            -row["total_score"],
            row["lead_id"],
        )
    )
    return plan


def write_plan(path, plan):
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(plan)


def parse_args():
    script_dir = Path(__file__).resolve().parent
    default_input = script_dir.parent / "lead-scoring-assistant" / "leads_scored.csv"
    parser = argparse.ArgumentParser(
        description="根据 Day 2 评分结果生成销售跟进计划"
    )
    parser.add_argument("--input", type=Path, default=default_input)
    parser.add_argument(
        "--rules",
        type=Path,
        default=script_dir / "follow_up_rules.csv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=script_dir / "follow_up_plan.csv",
    )
    parser.add_argument(
        "--base-date",
        type=parse_base_date,
        default=date.today(),
        help="计划起算日期，格式 YYYY-MM-DD；默认使用今天",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    try:
        rules = load_rules(args.rules)
        leads = load_scored_leads(args.input)
        plan = build_plan(leads, rules, args.base_date)
        write_plan(args.output, plan)
    except (PlannerError, OSError) as exc:
        print(f"错误：{exc}")
        return 1

    grade_counts = {
        grade: sum(1 for row in plan if row["grade"] == grade)
        for grade in ("A", "B", "C")
    }
    print(
        f"跟进计划生成完成：共 {len(plan)} 条；"
        f"A级 {grade_counts['A']} 条，"
        f"B级 {grade_counts['B']} 条，"
        f"C级 {grade_counts['C']} 条。"
    )
    print(f"计划起算日期：{args.base_date.isoformat()}")
    print(f"结果已保存：{args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
