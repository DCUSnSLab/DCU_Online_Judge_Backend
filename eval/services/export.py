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


def _norm_weights(weights):
    """examWeights normalize: {contest_id (str|int): number} → {int: float}."""
    out = {}
    if not isinstance(weights, dict):
        return out
    for k, v in weights.items():
        try:
            cid = int(k)
            w = float(v)
            if w > 0:
                out[cid] = w
        except (TypeError, ValueError):
            continue
    return out


def _norm_scales(scales):
    """groupScaleMax normalize: {group_key: number} → {key: float}."""
    out = {}
    if not isinstance(scales, dict):
        return out
    for k, v in scales.items():
        if k in GROUP_LABELS:
            try:
                f = float(v)
                if f > 0:
                    out[k] = f
            except (TypeError, ValueError):
                continue
    return out


def _ssn_str(s):
    """schoolssn 표시 — 0 또는 None 이면 빈 문자열."""
    v = s.get("schoolssn") if isinstance(s, dict) else None
    if not v:
        return ""
    return str(v)


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
                "schoolssn": _ssn_str(s),
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
            "schoolssn": _ssn_str(s),
            "auto_total": earned,
            "auto_max": max_total,
            "qual_overall_avg": round(qual_sum / qual_n, 1) if qual_n else None,
        })
    return out


def write_contest_csv(scoreboard):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        "이름", "ID", "학번",
        "문제", "문제명", "총점",
        "자동결과", "자동점수", "언어", "시간(ms)", "메모리(KB)",
        "정성_overall", "제안부분점수", "AI_likelihood", "AI_confidence"
    ])
    for r in _flat_rows_for_contest(scoreboard):
        w.writerow([
            r["realname"], r["username"], r["schoolssn"],
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
        "그룹", "컨테스트", "이름", "ID", "학번",
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
                glabel, ctitle, r["realname"], r["username"], r["schoolssn"],
                r["problem_label"], r["problem_title"], r["problem_total_score"],
                r["auto_result"], r["auto_score"],
                r["qual_overall"] if r["qual_overall"] is not None else "",
                r["qual_partial_suggested"] if r["qual_partial_suggested"] is not None else "",
                r["ai_likelihood"] if r["ai_likelihood"] is not None else "",
            ])
    return buf.getvalue().encode("utf-8-sig")


def write_contest_xlsx(scoreboard, weight=None):
    """단일 contest export.
    weight: 이 contest 의 환산 만점 (시험/대회 그룹). None 또는 0 이면 환산 컬럼 미표시.
    """
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})
    contest = scoreboard["contest"]
    problems = scoreboard["problems"]

    fmt_header = wb.add_format({
        "bold": True, "bg_color": "#F0F2F5", "border": 1, "align": "center", "valign": "vcenter"
    })
    fmt_center = wb.add_format({"align": "center", "border": 1})
    fmt_num = wb.add_format({"align": "center", "border": 1, "num_format": "0"})
    fmt_num1 = wb.add_format({"align": "center", "border": 1, "num_format": "0.0"})
    fmt_pct = wb.add_format({"align": "center", "border": 1, "num_format": "0.0%"})

    ws = wb.add_worksheet("매트릭스")
    ws.merge_range(
        0, 0, 0, 2 + len(problems) * 2,
        f"{contest['title']} ({contest.get('lecture_contest_type', '')})",
        fmt_header,
    )
    ws.write(2, 0, "이름", fmt_header)
    ws.write(2, 1, "ID", fmt_header)
    ws.write(2, 2, "학번", fmt_header)
    for i, p in enumerate(problems):
        ws.merge_range(1, 3 + i * 2, 1, 4 + i * 2, f"{p['label']} {p['title']} (/{p.get('total_score', 0)})", fmt_header)
        ws.write(2, 3 + i * 2, "자동", fmt_header)
        ws.write(2, 4 + i * 2, "정성", fmt_header)

    row = 3
    for s in scoreboard.get("students", []):
        ws.write(row, 0, s.get("realname") or "", fmt_center)
        ws.write(row, 1, s["username"], fmt_center)
        ws.write(row, 2, _ssn_str(s), fmt_center)
        for i, p in enumerate(problems):
            cell = (s.get("by_problem") or {}).get(p["label"]) or {}
            tc = cell.get("testcase") or {}
            qa = cell.get("qualitative") or {}
            ws.write(row, 3 + i * 2, tc.get("score", "") if tc else "", fmt_num)
            ws.write(row, 4 + i * 2, qa.get("overall", "") if qa else "", fmt_num)
        row += 1

    ws.set_column(0, 2, 14)
    ws.set_column(3, 2 + len(problems) * 2, 9)

    ws2 = wb.add_worksheet("학생합계")
    headers2 = ["이름", "ID", "학번", "자동총점", "자동만점", "취득비율", "정성평균(0-100)"]
    if weight:
        headers2.append(f"환산(/{weight})")
    ws2.write_row(0, 0, headers2, fmt_header)
    for i, t in enumerate(_student_totals_for_contest(scoreboard)):
        ws2.write(i + 1, 0, t["realname"], fmt_center)
        ws2.write(i + 1, 1, t["username"], fmt_center)
        ws2.write(i + 1, 2, t["schoolssn"], fmt_center)
        ws2.write(i + 1, 3, t["auto_total"], fmt_num)
        ws2.write(i + 1, 4, t["auto_max"], fmt_num)
        ws2.write(i + 1, 5, (t["auto_total"] / t["auto_max"]) if t["auto_max"] else 0, fmt_pct)
        ws2.write(i + 1, 6, t["qual_overall_avg"] if t["qual_overall_avg"] is not None else "", fmt_num)
        if weight:
            conv = (t["auto_total"] / t["auto_max"]) * weight if t["auto_max"] else 0
            ws2.write(i + 1, 7, round(conv, 1), fmt_num1)
    ws2.set_column(0, 2, 14)
    ws2.set_column(3, len(headers2) - 1, 12)

    wb.close()
    return buf.getvalue()


def write_lecture_xlsx(lecture, contests, scoreboards, weights=None, scales=None):
    """전체 lecture export.
    weights: {contest_id (int): 환산 만점 (점)}. 시험/대회 그룹의 contest 에만 적용.
    scales:  {group_key: 그룹 전체 환산 만점 (점)}. 비-시험 그룹에만 적용.
    """
    weights = weights or {}
    scales = scales or {}
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"in_memory": True})

    fmt_header = wb.add_format({
        "bold": True, "bg_color": "#F0F2F5", "border": 1, "align": "center", "valign": "vcenter"
    })
    fmt_header_conv = wb.add_format({
        "bold": True, "bg_color": "#FDECEC", "border": 1, "align": "center", "valign": "vcenter", "font_color": "#C0392B"
    })
    fmt_center = wb.add_format({"align": "center", "border": 1})
    fmt_num = wb.add_format({"align": "center", "border": 1, "num_format": "0"})
    fmt_num1 = wb.add_format({"align": "center", "border": 1, "num_format": "0.0"})
    fmt_pct = wb.add_format({"align": "center", "border": 1, "num_format": "0.0%"})
    fmt_bold = wb.add_format({"bold": True, "align": "center", "border": 1, "num_format": "0"})
    fmt_bold_conv = wb.add_format({
        "bold": True, "align": "center", "border": 1, "num_format": "0.0", "font_color": "#C0392B"
    })

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
                    "schoolssn": _ssn_str(s),
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

    def _exam_total_conv(s):
        """학생의 시험/대회 전체 환산점 — sum(c_score / c_max × weight)."""
        acc = 0
        for cid, w in weights.items():
            cmax = contest_max.get(cid, 0)
            if not cmax or contest_to_group.get(cid) != "exam":
                continue
            acc += (s["by_contest"].get(cid, 0) / cmax) * w
        return round(acc, 1)

    def _group_conv(s, gkey):
        gmax = contest_group_max[gkey] or 0
        smax = scales.get(gkey, 0)
        if not gmax or not smax:
            return 0
        return round((s["by_group"][gkey] / gmax) * smax, 1)

    exam_weight_sum = sum(w for cid, w in weights.items() if contest_to_group.get(cid) == "exam")

    # ─── 종합 시트 ───
    ws = wb.add_worksheet("종합")
    ws.merge_range(0, 0, 0, 6, f"{lecture.get('title', '')}  ({lecture.get('year', '')}-{lecture.get('semester', '')})", fmt_header)
    headers = ["이름", "ID", "학번", "총점", f"만점({total_max})", "취득%"]
    # 그룹 소계
    for g in GROUP_ORDER:
        if contest_group_max[g] > 0:
            headers.append(f"{GROUP_LABELS[g]}({contest_group_max[g]})")
    # 환산 컬럼들: 시험·대회 전체 + 시험·대회 contest별 + 비-시험 그룹 전체
    # conv_cols 항목 형식: ("exam_total" | "exam_contest" | "group", key)
    conv_cols = []
    if exam_weight_sum > 0 and contest_group_max["exam"] > 0:
        headers.append(f"시험·대회 전체 환산(/{exam_weight_sum:g})")
        conv_cols.append(("exam_total", None))
        # 시험·대회 그룹의 각 contest 환산 (weight 설정된 것만)
        for sb in scoreboards:
            if not sb:
                continue
            cid = sb["contest"]["id"]
            if contest_to_group.get(cid) != "exam":
                continue
            w = weights.get(cid, 0)
            if w <= 0:
                continue
            headers.append(f"{sb['contest']['title']} 환산(/{w:g})")
            conv_cols.append(("exam_contest", cid))
    for g in ("lab", "assignment", "other"):
        if scales.get(g, 0) > 0 and contest_group_max[g] > 0:
            headers.append(f"{GROUP_LABELS[g]} 환산(/{scales[g]:g})")
            conv_cols.append(("group", g))
    for i, h in enumerate(headers):
        is_conv = i >= len(headers) - len(conv_cols)
        ws.write(2, i, h, fmt_header_conv if is_conv else fmt_header)

    row = 3
    for s in students:
        ws.write(row, 0, s["realname"], fmt_center)
        ws.write(row, 1, s["username"], fmt_center)
        ws.write(row, 2, s["schoolssn"], fmt_center)
        ws.write(row, 3, s["total"], fmt_bold)
        ws.write(row, 4, total_max, fmt_num)
        ws.write(row, 5, (s["total"] / total_max) if total_max else 0, fmt_pct)
        col = 6
        for g in GROUP_ORDER:
            if contest_group_max[g] > 0:
                ws.write(row, col, s["by_group"][g], fmt_num)
                col += 1
        for kind, key in conv_cols:
            if kind == "exam_total":
                v = _exam_total_conv(s)
            elif kind == "exam_contest":
                cmax = contest_max.get(key, 0)
                w = weights.get(key, 0)
                v = round((s["by_contest"].get(key, 0) / cmax) * w, 1) if (cmax and w) else 0
            else:  # group
                v = _group_conv(s, key)
            ws.write(row, col, v, fmt_bold_conv)
            col += 1
        row += 1
    ws.freeze_panes(3, 3)
    ws.set_column(0, 2, 14)
    ws.set_column(3, len(headers) - 1, 14)

    # ─── 그룹별 시트 ───
    for gkey in GROUP_ORDER:
        contests_in_group = [c for c in scoreboards if c and contest_to_group.get(c["contest"]["id"]) == gkey]
        if not contests_in_group:
            continue
        wsg = wb.add_worksheet(GROUP_LABELS[gkey][:30])
        wsg.write(0, 0, "이름", fmt_header)
        wsg.write(0, 1, "ID", fmt_header)
        wsg.write(0, 2, "학번", fmt_header)
        col = 3
        col_to_cid = {}            # 원점수 컬럼
        conv_col_to_cid = {}       # 환산점 컬럼 (시험/대회 만)
        for sb in contests_in_group:
            cid = sb["contest"]["id"]
            wsg.write(0, col, f"{sb['contest']['title']} (/{contest_max[cid]})", fmt_header)
            col_to_cid[col] = cid
            col += 1
            if gkey == "exam" and weights.get(cid, 0) > 0:
                wsg.write(0, col, f"{sb['contest']['title']} 환산(/{weights[cid]:g})", fmt_header_conv)
                conv_col_to_cid[col] = cid
                col += 1
        wsg.write(0, col, f"소계(/{contest_group_max[gkey]})", fmt_header)
        sub_col = col
        wsg.write(0, col + 1, "취득%", fmt_header)
        pct_col = col + 1
        col = pct_col + 1
        # 그룹 전체 환산 컬럼
        group_total_max = 0
        if gkey == "exam" and exam_weight_sum > 0:
            group_total_max = exam_weight_sum
            wsg.write(0, col, f"전체 환산(/{exam_weight_sum:g})", fmt_header_conv)
        elif gkey != "exam" and scales.get(gkey, 0) > 0:
            group_total_max = scales[gkey]
            wsg.write(0, col, f"전체 환산(/{scales[gkey]:g})", fmt_header_conv)
        conv_total_col = col if group_total_max else None
        for i, s in enumerate(students):
            r = i + 1
            wsg.write(r, 0, s["realname"], fmt_center)
            wsg.write(r, 1, s["username"], fmt_center)
            wsg.write(r, 2, s["schoolssn"], fmt_center)
            for c, cid in col_to_cid.items():
                wsg.write(r, c, s["by_contest"].get(cid, 0), fmt_num)
            for c, cid in conv_col_to_cid.items():
                cmax = contest_max.get(cid, 0)
                w = weights.get(cid, 0)
                v = (s["by_contest"].get(cid, 0) / cmax * w) if (cmax and w) else 0
                wsg.write(r, c, round(v, 1), fmt_num1)
            wsg.write(r, sub_col, s["by_group"][gkey], fmt_bold)
            denom = contest_group_max[gkey] or 1
            wsg.write(r, pct_col, s["by_group"][gkey] / denom, fmt_pct)
            if conv_total_col is not None:
                tv = _exam_total_conv(s) if gkey == "exam" else _group_conv(s, gkey)
                wsg.write(r, conv_total_col, tv, fmt_bold_conv)
        wsg.freeze_panes(1, 3)
        wsg.set_column(0, 2, 14)
        wsg.set_column(3, conv_total_col or pct_col, 14)

    # ─── Raw 시트 ───
    wsf = wb.add_worksheet("Raw")
    wsf.write_row(0, 0, [
        "그룹", "컨테스트", "이름", "ID", "학번", "문제", "문제명", "총점",
        "자동결과", "자동점수", "정성_overall", "제안부분점수", "AI_likelihood"
    ], fmt_header)
    rr = 1
    for sb in scoreboards:
        if not sb:
            continue
        group = _classify((sb.get("contest") or {}).get("lecture_contest_type"))
        for r in _flat_rows_for_contest(sb):
            wsf.write_row(rr, 0, [
                GROUP_LABELS[group], r["contest_title"], r["realname"], r["username"], r["schoolssn"],
                r["problem_label"], r["problem_title"], r["problem_total_score"],
                r["auto_result"], r["auto_score"],
                r["qual_overall"] if r["qual_overall"] is not None else "",
                r["qual_partial_suggested"] if r["qual_partial_suggested"] is not None else "",
                r["ai_likelihood"] if r["ai_likelihood"] is not None else "",
            ])
            rr += 1
    wsf.freeze_panes(1, 0)
    wsf.set_column(0, 1, 14)
    wsf.set_column(2, 12, 12)

    wb.close()
    return buf.getvalue()


# ─────────────────────────────────────────────────────────────────────
# In-process orchestrators
# ─────────────────────────────────────────────────────────────────────

def build_contest_export(contest_id, fmt, weights=None, scales=None):
    """contest 1건 export. weights 에 이 contest 의 환산 만점이 있으면 환산 컬럼 포함."""
    sb, err = sb_service.build_scoreboard(contest_id)
    if err:
        return None, err, None
    title = (sb.get("contest") or {}).get("title") or f"contest_{contest_id}"
    w_norm = _norm_weights(weights)
    this_weight = w_norm.get(int(contest_id), 0)
    if fmt == "csv":
        return title.replace("/", "_"), write_contest_csv(sb), "text/csv; charset=utf-8"
    elif fmt == "xlsx":
        return (
            title.replace("/", "_"),
            write_contest_xlsx(sb, weight=this_weight or None),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    return None, "unsupported format", None


def build_lecture_export(lecture_id, fmt, weights=None, scales=None):
    """lecture 전체 export — 모든 contest 의 scoreboard 합쳐서.
    weights: {contest_id: 환산 만점} — 시험/대회 그룹에 적용.
    scales:  {group_key: 그룹 전체 환산 만점} — 비-시험 그룹에 적용.
    """
    lecture = sb_service.get_lecture_dict(lecture_id)
    if not lecture:
        return None, "lecture not found", None
    contests = sb_service.list_lecture_contests(lecture_id)
    scoreboards = []
    for c in contests:
        sb, err = sb_service.build_scoreboard(c["id"])
        scoreboards.append(sb)  # err 면 None 으로 (skip)
    title = (lecture.get("title") or f"lecture_{lecture_id}").replace("/", "_")
    w_norm = _norm_weights(weights)
    s_norm = _norm_scales(scales)
    if fmt == "csv":
        return title, write_lecture_csv(lecture, contests, scoreboards), "text/csv; charset=utf-8"
    elif fmt == "xlsx":
        return (
            title,
            write_lecture_xlsx(lecture, contests, scoreboards, weights=w_norm, scales=s_norm),
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    return None, "unsupported format", None
