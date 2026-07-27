#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
销售线索评分器 (Lead Scoring Assistant)
=========================================
纯 Python 标准库实现，无需安装任何第三方依赖，
可在普通 Windows 电脑（已安装 Python 3）上直接运行。

用法：
    python lead_scoring.py
    （默认读取同目录下的 leads_sample.csv，输出 leads_scored.csv）

    也可以指定输入/输出文件：
    python lead_scoring.py 我的线索.csv 打分结果.csv

评分规则详见 README.md。
"""

import csv
import sys
import os


# ---------------------------------------------------------------------------
# 评分规则配置（每项满分 20 分，共 5 项，总分 100 分）
# ---------------------------------------------------------------------------

# 1. 公司规模（支持分类文字或员工人数）
COMPANY_SIZE_SCORES = {
    "大型": 20,
    "中型": 12,
    "小型": 5,
}


def score_company_size(value, row_no):
    text = str(value).strip()
    if text in COMPANY_SIZE_SCORES:
        return COMPANY_SIZE_SCORES[text]
    try:
        size = int(text)
    except (ValueError, TypeError):
        raise LeadValidationError(
            row_no, "company_size",
            f"公司规模字段无效：'{value}'，应为大型 / 中型 / 小型，"
            "或正整数（员工人数），例如 50"
        )
    if size < 0:
        raise LeadValidationError(
            row_no, "company_size",
            f"公司规模字段无效：'{value}'，不能为负数"
        )
    if size >= 201:
        return 20
    elif size >= 51:
        return 15
    elif size >= 11:
        return 10
    else:
        return 5


# 2. 职位（按关键词匹配职级）
JOB_TITLE_TIERS = [
    (20, ["ceo", "cto", "cfo", "coo", "vp", "总裁", "副总裁", "总监",
          "director", "president", "创始人", "founder", "合伙人", "老板",
          "董事长", "总经理"]),
    (14, ["manager", "经理", "主管", "head of", "负责人"]),
    (8, ["engineer", "specialist", "analyst", "专员", "工程师",
         "分析师", "运营"]),
    (3, ["intern", "实习生", "assistant", "助理"]),
]


def score_job_title(value, row_no):
    text = str(value).strip()
    if text == "" or text.lower() == "nan":
        raise LeadValidationError(
            row_no, "job_title", "职位字段不能为空"
        )
    lowered = text.lower()
    for score, keywords in JOB_TITLE_TIERS:
        for kw in keywords:
            if kw and kw in lowered:
                return score
    # 无法识别的职位名称：不视为致命错误，给予中等偏下分数，并提示（非阻断）
    print(f"  [提示] 第 {row_no} 行：职位 '{text}' 未能匹配已知职级关键词，"
          f"按默认分（8分）处理")
    return 8


# 3. 预算（支持高/中/低/无，或具体金额）
BUDGET_SCORES = {
    "高": 20,
    "中": 12,
    "低": 5,
    "无": 0,
}


def score_budget(value, row_no):
    text = str(value).strip()
    if text in BUDGET_SCORES:
        return BUDGET_SCORES[text]
    try:
        budget = float(text)
    except (ValueError, TypeError):
        raise LeadValidationError(
            row_no, "budget",
            f"预算字段无效：'{value}'，应为高 / 中 / 低 / 无，"
            "或数字金额（如 50000）"
        )
    if budget < 0:
        raise LeadValidationError(
            row_no, "budget",
            f"预算字段无效：'{value}'，不能为负数"
        )
    if budget >= 100000:
        return 20
    elif budget >= 50000:
        return 15
    elif budget >= 10000:
        return 10
    elif budget > 0:
        return 5
    else:
        return 0


# 4. 紧迫度
URGENCY_SCORES = {
    "高": 20,
    "中": 12,
    "低": 5,
    "无": 0,
}


def score_urgency(value, row_no):
    text = str(value).strip()
    if text not in URGENCY_SCORES:
        raise LeadValidationError(
            row_no, "urgency",
            f"紧迫度字段无效：'{value}'，允许的取值为：高 / 中 / 低 / 无"
        )
    return URGENCY_SCORES[text]


# 5. 互动程度（支持高/中/低/无，或互动次数）
ENGAGEMENT_SCORES = {
    "高": 20,
    "中": 12,
    "低": 5,
    "无": 0,
}


def score_engagement(value, row_no):
    text = str(value).strip()
    if text in ENGAGEMENT_SCORES:
        return ENGAGEMENT_SCORES[text]
    try:
        engagement = int(float(text))
    except (ValueError, TypeError):
        raise LeadValidationError(
            row_no, "engagement",
            f"互动程度字段无效：'{value}'，应为高 / 中 / 低 / 无，"
            "或非负整数（互动次数）"
        )
    if engagement < 0:
        raise LeadValidationError(
            row_no, "engagement",
            f"互动程度字段无效：'{value}'，不能为负数"
        )
    if engagement >= 10:
        return 20
    elif engagement >= 5:
        return 14
    elif engagement >= 1:
        return 8
    else:
        return 0


# ---------------------------------------------------------------------------
# 异常类
# ---------------------------------------------------------------------------
class LeadValidationError(Exception):
    """用于携带行号、字段名、中文错误说明的自定义异常"""
    def __init__(self, row_no, field, message):
        self.row_no = row_no
        self.field = field
        self.message = message
        super().__init__(message)


REQUIRED_COLUMNS = [
    "lead_id", "company_name", "company_size",
    "job_title", "budget", "urgency", "engagement",
]


def grade_of(total_score):
    if total_score >= 80:
        return "A"
    elif total_score >= 60:
        return "B"
    else:
        return "C"


def score_leads(input_path, output_path):
    if not os.path.exists(input_path):
        print(f"错误：找不到输入文件 '{input_path}'，请确认文件路径是否正确。")
        return False

    with open(input_path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        # 检查列名是否齐全
        missing = [c for c in REQUIRED_COLUMNS if c not in (reader.fieldnames or [])]
        if missing:
            print("错误：CSV 文件缺少必要的列：" + "、".join(missing))
            print(f"必须包含以下列：{', '.join(REQUIRED_COLUMNS)}")
            return False

        results = []
        error_count = 0
        total_rows = 0

        for i, row in enumerate(reader, start=2):  # 第1行是表头，数据从第2行开始
            total_rows += 1
            lead_id = row.get("lead_id", "").strip() or f"(第{i}行,无lead_id)"
            try:
                s_size = score_company_size(row.get("company_size"), i)
                s_job = score_job_title(row.get("job_title"), i)
                s_budget = score_budget(row.get("budget"), i)
                s_urgency = score_urgency(row.get("urgency"), i)
                s_engagement = score_engagement(row.get("engagement"), i)
            except LeadValidationError as e:
                error_count += 1
                print(f"  [跳过] 第 {e.row_no} 行（{lead_id}）：{e.message}")
                continue

            total = s_size + s_job + s_budget + s_urgency + s_engagement
            results.append({
                "lead_id": lead_id,
                "company_name": row.get("company_name", "").strip(),
                "company_size_score": s_size,
                "job_title_score": s_job,
                "budget_score": s_budget,
                "urgency_score": s_urgency,
                "engagement_score": s_engagement,
                "total_score": total,
                "grade": grade_of(total),
            })

        # 按总分从高到低排序，同分时按 lead_id 排序保证结果稳定
        results.sort(key=lambda r: (-r["total_score"], r["lead_id"]))

        fieldnames = [
            "lead_id", "company_name",
            "company_size_score", "job_title_score", "budget_score",
            "urgency_score", "engagement_score",
            "total_score", "grade",
        ]
        with open(output_path, "w", encoding="utf-8-sig", newline="") as out_f:
            writer = csv.DictWriter(out_f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(results)

        print("\n" + "=" * 50)
        print(f"处理完成：共读取 {total_rows} 条线索，"
              f"成功评分 {len(results)} 条，跳过 {error_count} 条（字段无效）")
        if results:
            a = sum(1 for r in results if r["grade"] == "A")
            b = sum(1 for r in results if r["grade"] == "B")
            c = sum(1 for r in results if r["grade"] == "C")
            print(f"等级分布：A级 {a} 条，B级 {b} 条，C级 {c} 条")
        print(f"结果已保存到：{output_path}")
        print("=" * 50)
        return True


def main():
    input_path = sys.argv[1] if len(sys.argv) > 1 else "leads_sample.csv"
    output_path = sys.argv[2] if len(sys.argv) > 2 else "leads_scored.csv"
    print(f"开始处理：{input_path} -> {output_path}\n")
    ok = score_leads(input_path, output_path)
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
