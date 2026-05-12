"""
정성평가 + 자동채점 점수 export (CSV / XLSX).

원본: lecture/views/score_export.py (Round 1/GEN-975 의 사이드카 HTTP 호출 버전).
PR 4: 데이터 소스를 사이드카 HTTP → 본 서버의 build_scoreboard() in-process 로 교체.
응답 컬럼/시트 구조는 동일.
"""
import csv
import io

import xlsxwriter

from . import scoreboard as sb_service


# contest type → 그룹 키 매핑 (Frontend OverallTab 와 일치)
TYPE_GROUP = {
    "대회": "exam",
    "시험": "exam",
    "실습": "lab",
    "과제": "assignment",
}
GROUP_LABELS = {
    "exam": "시험·대회",
    "lab": "실습",
    "assignment": "과제",
    "other": "기타",
}
GROUP_ORDER = ["exam", "lab", "assignment", "other"]


def _classify(t):
    return TYPE_GROUP.get(t, "other")


def _flat_rows_for_contest(scoreboard):
    """단일 contest 의 학생 × 문제 평탄화 행."""
    contest = scoreboard["contest"]
    problems = scoreboard["problems"]
    rows = []
    for s in scoreboard.get("students", []):
        for p in problems:
            cell = (s.get("by_problem") or {}).get(p["label"]) or {}
            tc = cell.get("testcase") or {}
            qa = cell.get("qualitative") or {}
            rows.append({
                "contest_id": contest["id"],
                "contest_title": contest["title"],
                "contest_type": contest.get("lecture_contest_type", ""),
                "user_id": s["user_id"],
                "username": s["username"],
                "realname": s.get("realname") or "",
                "problem_label": p["label"],
                "problem_title": p["title"],
                "problem_total_score": p.get("total_score", 0),
                "submission_id": tc.get("submission_id", ""),
                "auto_result": tc.get("result_label", ""),
                "auto_score": tc.get("score", 0) if tc else 0,
                "language": tc.get("language", ""),
                "time_ms": tc.get("time_cost_ms", ""),
                "memory_kb": tc.get("memory_cost_kb", ""),
                "qual_overall": qa.get("overall") if qa else None,
                "qual_partial_suggested": qa.get("suggested_partial_score") if qa else None,
                "ai_likelihood": qa.get("ai_likelihood_score") if qa else None,
                "ai_confidence": qa.get("ai_confidence") if qa else None,
            })
    return rows


def _student_totals_for_contest(scoreboard):
    problems = scoreboard.get("problems", [])
    max_total = sum(p.get("total_score", 0) for p in problems)
    out = []
    for s in scoreboard.get("students", []):
        earned = 0
        qual_sum = 0
        qual_n = 0
        for p in problems:
            cell = (s.get("by_problem") or {}).get(p["label"]) or {}
            tc = cell.get("testcase") or {}
            qa = cell.get("qualitative") or {}
            if tc:
                earned += tc.get("score", 0) or 0
            if qa and qa.get("overall") is not None:
                qual_sum += qa["overall"]
                qual_n += 1
        out.append({
            "user_id": s["user_id"],
            "username": s["username"],
            "realname": s.get("realname") or "",
            "auto_total": earned,
            "auto_max": max_total,
            "qual_overall_avg": round(qual_sum / qual_n, 1) if qual_n else None,
        })
    return out


def write_contest_csv(scoreboard):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        "학번", "이름",
        "문제", "문제명", "총점",
        "자동결과", "자동점수", "언어", "시간(ms)", "메모리(KB)",
        "정성_overall", "제안부분점수", "AI_likelihood", "AI_confidence"
    ])
    for r in _flat_rows_for_contest(scoreboard):
        w.writerow([
            r["username"], r["realname"],
            r["problem_label"], r["problem_title"], r["problem_total_score"],
            r["auto_result"], r["auto_score"], r["language"], r["time_ms"], r["memory_kb"],
            r["qual_overall"] if r["qual_overall"] is not None else "",
            r["qual_partial_suggested"] if r["qual_partial_suggested"] is not None else "",
            r["ai_likelihood"] if r["ai_likelihood"] is not None else "",
            r["ai_confidence"] or "",
        ])
    return buf.getvalue().encode("utf-8-sig")  # BOM for Excel CJK


def write_lecture_csv(lecture, contests, scoreboards):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        "그룹", "컨테스트", "학번", "이름",
        "문제", "문제명", "총점",
        "자동결과", "자동점수",
        "정성_overall", "제안부분점수", "AI_likelihood"
    ])
    for sb in scoreboards:
        if not sb:
            continue
        group = _classify((sb.get("contest") or {}).get("lecture_contest_type"))
        glabel = GROUP_LABELS[group]
        ctitle = (sb.get("contest") or {}).get("title", "")
        for r in _flat_rows_for_contest(sb):
            w.writerow([
                glabel, ctitle, r["username"], r["realname"],
                r["problem_label"], r["problem_title"], r["problem_total_score"],
                r["auto_result"], r["auto_score"],
                r["qual_overall"] if r["qual_overall"] is not None else "",
                r["qual_partial_suggested"] if r["qual_partial_suggested"] is not None else "",
                r["ai_likelihood"] if r["ai_likelihood"] is not None else "",
            ])
    return buf.getvalue().encode("utf-8-sig")


def write_contest_xlsx(scoreboard):
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})
    contest = scoreboard["contest"]
    problems = scoreboard["problems"]

    fmt_header = wb.add_format({
        "bold": True, "bg_color": "#F0F2F5", "border": 1, "align": "center", "valign": "vcenter"
    })
    fmt_center = wb.add_format({"align": "center", "border": 1})
    fmt_num = wb.add_format({"align": "center", "border": 1, "num_format": "0"})
    fmt_pct = wb.add_format({"align": "center", "border": 1, "num_format": "0.0%"})

    ws = wb.add_worksheet("매트릭스")
    ws.merge_range(
        0, 0, 0, 1 + len(problems) * 2,
        f"{contest['title']} ({contest.get('lecture_contest_type', '')})",
        fmt_header,
    )
    ws.write(2, 0, "학번", fmt_header)
    ws.write(2, 1, "이름", fmt_header)
    for i, p in enumerate(problems):
        ws.merge_range(1, 2 + i * 2, 1, 3 + i * 2, f"{p['label']} {p['title']} (/{p.get('total_score', 0)})", fmt_header)
        ws.write(2, 2 + i * 2, "자동", fmt_header)
        ws.write(2, 3 + i * 2, "정성", fmt_header)

    row = 3
    for s in scoreboard.get("students", []):
        ws.write(row, 0, s["username"], fmt_center)
        ws.write(row, 1, s.get("realname") or "", fmt_center)
        for i, p in enumerate(problems):
            cell = (s.get("by_problem") or {}).get(p["label"]) or {}
            tc = cell.get("testcase") or {}
            qa = cell.get("qualitative") or {}
            ws.write(row, 2 + i * 2, tc.get("score", "") if tc else "", fmt_num)
            ws.write(row, 3 + i * 2, qa.get("overall", "") if qa else "", fmt_num)
        row += 1

    ws.set_column(0, 0, 14)
    ws.set_column(1, 1, 14)
    ws.set_column(2, 1 + len(problems) * 2, 9)

    ws2 = wb.add_worksheet("학생합계")
    ws2.write_row(0, 0, ["학번", "이름", "자동총점", "자동만점", "취득비율", "정성평균(0-100)"], fmt_header)
    for i, t in enumerate(_student_totals_for_contest(scoreboard)):
        ws2.write(i + 1, 0, t["username"], fmt_center)
        ws2.write(i + 1, 1, t["realname"], fmt_center)
        ws2.write(i + 1, 2, t["auto_total"], fmt_num)
        ws2.write(i + 1, 3, t["auto_max"], fmt_num)
        ws2.write(i + 1, 4, (t["auto_total"] / t["auto_max"]) if t["auto_max"] else 0, fmt_pct)
        ws2.write(i + 1, 5, t["qual_overall_avg"] if t["qual_overall_avg"] is not None else "", fmt_num)
    ws2.set_column(0, 0, 14)
    ws2.set_column(1, 1, 14)
    ws2.set_column(2, 5, 12)

    wb.close()
    return buf.getvalue()


def write_lecture_xlsx(lecture, contests, scoreboards):
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})

    fmt_header = wb.add_format({
        "bold": True, "bg_color": "#F0F2F5", "border": 1, "align": "center", "valign": "vcenter"
    })
    fmt_center = wb.add_format({"align": "center", "border": 1})
    fmt_num = wb.add_format({"align": "center", "border": 1, "num_format": "0"})
    fmt_pct = wb.add_format({"align": "center", "border": 1, "num_format": "0.0%"})
    fmt_bold = wb.add_format({"bold": True, "align": "center", "border": 1, "num_format": "0"})

    student_idx = {}
    contest_max = {}
    contest_to_group = {}
    contest_titles = {}
    contest_group_max = {g: 0 for g in GROUP_ORDER}

    for sb in scoreboards:
        if not sb:
            continue
        cid = sb["contest"]["id"]
        ctype = sb["contest"].get("lecture_contest_type")
        gkey = _classify(ctype)
        contest_to_group[cid] = gkey
        contest_titles[cid] = sb["contest"]["title"]
        cmax = sum(p.get("total_score", 0) for p in sb["problems"])
        contest_max[cid] = cmax
        contest_group_max[gkey] += cmax
        for s in sb.get("students", []):
            u = s["user_id"]
            if u not in student_idx:
                student_idx[u] = {
                    "user_id": u,
                    "username": s["username"],
                    "realname": s.get("realname") or "",
                    "by_contest": {},
                    "by_group": {g: 0 for g in GROUP_ORDER},
                    "total": 0,
                }
            row = student_idx[u]
            csum = 0
            for p in sb["problems"]:
                cell = (s.get("by_problem") or {}).get(p["label"]) or {}
                tc = cell.get("testcase") or {}
                if tc:
                    csum += tc.get("score", 0) or 0
            row["by_contest"][cid] = csum
            row["by_group"][gkey] += csum
            row["total"] += csum

    students = sorted(student_idx.values(), key=lambda r: -r["total"])
    total_max = sum(contest_max.values())

    ws = wb.add_worksheet("종합")
    ws.merge_range(0, 0, 0, 5, f"{lecture.get('title', '')}  ({lecture.get('year', '')}-{lecture.get('semester', '')})", fmt_header)

    headers = ["학번", "이름", "총점", f"만점({total_max})", "취득%"]
    for g in GROUP_ORDER:
        if contest_group_max[g] > 0:
            headers.append(f"{GROUP_LABELS[g]}({contest_group_max[g]})")
    for i, h in enumerate(headers):
        ws.write(2, i, h, fmt_header)

    row = 3
    for s in students:
        ws.write(row, 0, s["username"], fmt_center)
        ws.write(row, 1, s["realname"], fmt_center)
        ws.write(row, 2, s["total"], fmt_bold)
        ws.write(row, 3, total_max, fmt_num)
        ws.write(row, 4, (s["total"] / total_max) if total_max else 0, fmt_pct)
        col = 5
        for g in GROUP_ORDER:
            if contest_group_max[g] > 0:
                ws.write(row, col, s["by_group"][g], fmt_num)
                col += 1
        row += 1
    ws.freeze_panes(3, 2)
    ws.set_column(0, 0, 14)
    ws.set_column(1, 1, 14)
    ws.set_column(2, len(headers) - 1, 12)

    for gkey in GROUP_ORDER:
        contests_in_group = [c for c in scoreboards if c and contest_to_group.get(c["contest"]["id"]) == gkey]
        if not contests_in_group:
            continue
        wsg = wb.add_worksheet(GROUP_LABELS[gkey][:30])
        wsg.write(0, 0, "학번", fmt_header)
        wsg.write(0, 1, "이름", fmt_header)
        col = 2
        col_to_cid = {}
        for sb in contests_in_group:
            cid = sb["contest"]["id"]
            wsg.write(0, col, f"{sb['contest']['title']} (/{contest_max[cid]})", fmt_header)
            col_to_cid[col] = cid
            col += 1
        wsg.write(0, col, f"소계(/{contest_group_max[gkey]})", fmt_header)
        sub_col = col
        wsg.write(0, col + 1, "취득%", fmt_header)
        pct_col = col + 1
        for i, s in enumerate(students):
            r = i + 1
            wsg.write(r, 0, s["username"], fmt_center)
            wsg.write(r, 1, s["realname"], fmt_center)
            for c, cid in col_to_cid.items():
                wsg.write(r, c, s["by_contest"].get(cid, 0), fmt_num)
            wsg.write(r, sub_col, s["by_group"][gkey], fmt_bold)
            denom = contest_group_max[gkey] or 1
            wsg.write(r, pct_col, s["by_group"][gkey] / denom, fmt_pct)
        wsg.freeze_panes(1, 2)
        wsg.set_column(0, 1, 14)
        wsg.set_column(2, pct_col, 14)

    wsf = wb.add_worksheet("Raw")
    wsf.write_row(0, 0, [
        "그룹", "컨테스트", "학번", "이름", "문제", "문제명", "총점",
        "자동결과", "자동점수", "정성_overall", "제안부분점수", "AI_likelihood"
    ], fmt_header)
    rr = 1
    for sb in scoreboards:
        if not sb:
            continue
        group = _classify((sb.get("contest") or {}).get("lecture_contest_type"))
        for r in _flat_rows_for_contest(sb):
            wsf.write_row(rr, 0, [
                GROUP_LABELS[group], r["contest_title"], r["username"], r["realname"],
                r["problem_label"], r["problem_title"], r["problem_total_score"],
                r["auto_result"], r["auto_score"],
                r["qual_overall"] if r["qual_overall"] is not None else "",
                r["qual_partial_suggested"] if r["qual_partial_suggested"] is not None else "",
                r["ai_likelihood"] if r["ai_likelihood"] is not None else "",
            ])
            rr += 1
    wsf.freeze_panes(1, 0)
    wsf.set_column(0, 1, 14)
    wsf.set_column(2, 11, 12)

    wb.close()
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────────────
# In-process orchestrators
# ─────────────────────────────────────────────────────────────────────

def build_contest_export(contest_id, fmt):
    """contest 1건 export. (filename_stem, bytes, content_type) 반환 또는 (None, error, None)."""
    sb, err = sb_service.build_scoreboard(contest_id)
    if err:
        return None, err, None
    title = (sb.get("contest") or {}).get("title") or f"contest_{contest_id}"
    if fmt == "csv":
        return title.replace("/", "_"), write_contest_csv(sb), "text/csv; charset=utf-8"
    elif fmt == "xlsx":
        return (
            title.replace("/", "_"),
            write_contest_xlsx(sb),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    return None, "unsupported format", None


def build_lecture_export(lecture_id, fmt):
    """lecture 전체 export — 모든 contest 의 scoreboard 합쳐서."""
    lecture = sb_service.get_lecture_dict(lecture_id)
    if not lecture:
        return None, "lecture not found", None
    contests = sb_service.list_lecture_contests(lecture_id)
    scoreboards = []
    for c in contests:
        sb, err = sb_service.build_scoreboard(c["id"])
        scoreboards.append(sb)  # err 면 None 으로 (skip)
    title = (lecture.get("title") or f"lecture_{lecture_id}").replace("/", "_")
    if fmt == "csv":
        return title, write_lecture_csv(lecture, contests, scoreboards), "text/csv; charset=utf-8"
    elif fmt == "xlsx":
        return (
            title,
            write_lecture_xlsx(lecture, contests, scoreboards),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    return None, "unsupported format", None
