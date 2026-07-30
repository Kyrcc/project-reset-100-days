#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""检查销售跟进任务状态，并生成按行动优先级排列的状态表。"""

import argparse
import csv
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


REQUIRED_COLUMNS = {"due_date", "status"}
ALERT_STATUS_COLUMN = "alert_status"
STATUS_ORDER = {
    "今日待跟进": 0,
    "逾期": 1,
    "未到期": 2,
    "已完成": 3,
}
CHINA_TIMEZONE = timezone(timedelta(hours=8))


class StatusCheckError(Exception):
    """面向使用者的跟进状态检查错误。"""


def parse_date(value):
    """同时兼容程序生成日期和 Excel 保存后的日期格式。"""
    cleaned = value.strip()
    for date_format in ("%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(cleaned, date_format).date()
        except ValueError:
            continue
    raise ValueError("日期格式必须是 YYYY-MM-DD 或 YYYY/M/D")


def parse_today(value):
    try:
        return parse_date(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def china_today():
    """返回中国标准时间下的当天日期。"""
    return datetime.now(CHINA_TIMEZONE).date()


def classify_task(status, due_date, today):
    """按照业务确认的优先顺序判断一条任务的提醒状态。"""
    if status == "已完成":
        return "已完成"
    if status != "待跟进":
        raise StatusCheckError(
            f"status 只能是“待跟进”或“已完成”，当前值为：{status or '空白'}"
        )
    if due_date < today:
        return "逾期"
    if due_date == today:
        return "今日待跟进"
    return "未到期"


def load_and_classify(path, today):
    if not path.exists():
        raise StatusCheckError(f"找不到跟进计划文件：{path}")

    with path.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        fieldnames = list(reader.fieldnames or [])
        missing = sorted(REQUIRED_COLUMNS - set(fieldnames))
        if missing:
            raise StatusCheckError(
                f"跟进计划缺少必要字段：{', '.join(missing)}"
            )

        rows = []
        for row_no, row in enumerate(reader, start=2):
            status = row["status"].strip()
            try:
                due_date = parse_date(row["due_date"])
            except ValueError as exc:
                raise StatusCheckError(
                    f"第 {row_no} 行 due_date 无效：{row['due_date']}；{exc}"
                ) from exc

            row["status"] = status
            row[ALERT_STATUS_COLUMN] = classify_task(status, due_date, today)
            row["_due_date_for_sort"] = due_date
            row["_original_order"] = row_no
            rows.append(row)

    rows.sort(
        key=lambda row: (
            STATUS_ORDER[row[ALERT_STATUS_COLUMN]],
            row["_due_date_for_sort"],
            row["_original_order"],
        )
    )
    for row in rows:
        row.pop("_due_date_for_sort")
        row.pop("_original_order")

    output_columns = [
        column for column in fieldnames if column != ALERT_STATUS_COLUMN
    ] + [ALERT_STATUS_COLUMN]
    return output_columns, rows


def write_result(path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def parse_args():
    script_dir = Path(__file__).resolve().parent
    default_input = (
        script_dir.parent / "follow-up-planner" / "follow_up_plan.csv"
    )
    parser = argparse.ArgumentParser(
        description="检查销售跟进任务，并生成按行动优先级排列的状态表"
    )
    parser.add_argument("--input", type=Path, default=default_input)
    parser.add_argument(
        "--output",
        type=Path,
        default=script_dir / "跟进状态检查表.csv",
    )
    parser.add_argument(
        "--today",
        type=parse_today,
        help="指定测试日期；不填写时使用中国标准时间的当天日期",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    today = args.today or china_today()

    try:
        fieldnames, rows = load_and_classify(args.input, today)
        write_result(args.output, fieldnames, rows)
    except (StatusCheckError, OSError) as exc:
        print(f"错误：{exc}")
        return 1

    counts = {
        status: sum(
            1 for row in rows if row[ALERT_STATUS_COLUMN] == status
        )
        for status in STATUS_ORDER
    }
    print(f"跟进状态检查完成：共 {len(rows)} 条。")
    print(
        f"今日待跟进 {counts['今日待跟进']} 条；"
        f"逾期 {counts['逾期']} 条；"
        f"未到期 {counts['未到期']} 条；"
        f"已完成 {counts['已完成']} 条。"
    )
    print(f"判断日期（中国时间）：{today.isoformat()}")
    print(f"结果已保存：{args.output.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
