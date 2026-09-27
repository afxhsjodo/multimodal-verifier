"""评测指标：准确率、macro-F1、混淆矩阵、引用有效率、证据覆盖率。"""
from __future__ import annotations

LABELS = ["support", "refute", "insufficient"]
LABELS_CN = {"support": "支持", "refute": "反驳", "insufficient": "证据不足"}


def confusion(pairs: list[tuple[str, str]]) -> dict[str, dict[str, int]]:
    m = {g: {p: 0 for p in LABELS} for g in LABELS}
    for gold, pred in pairs:
        if gold in m and pred in m[gold]:
            m[gold][pred] += 1
    return m


def accuracy(pairs: list[tuple[str, str]]) -> float:
    if not pairs:
        return 0.0
    return round(sum(1 for g, p in pairs if g == p) / len(pairs), 4)


def macro_f1(pairs: list[tuple[str, str]]) -> float:
    m = confusion(pairs)
    f1s = []
    for lab in LABELS:
        tp = m[lab][lab]
        fp = sum(m[g][lab] for g in LABELS if g != lab)
        fn = sum(m[lab][p] for p in LABELS if p != lab)
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
        f1s.append(f1)
    return round(sum(f1s) / len(f1s), 4)


def per_class_f1(pairs: list[tuple[str, str]]) -> dict[str, float]:
    m = confusion(pairs)
    out = {}
    for lab in LABELS:
        tp = m[lab][lab]
        fp = sum(m[g][lab] for g in LABELS if g != lab)
        fn = sum(m[lab][p] for p in LABELS if p != lab)
        prec = tp / (tp + fp) if (tp + fp) else 0.0
        rec = tp / (tp + fn) if (tp + fn) else 0.0
        out[lab] = round(2 * prec * rec / (prec + rec), 4) if (prec + rec) else 0.0
    return out


def summarize(rows: list[dict]) -> dict:
    """rows: 每条样本结果 dict，含 gold, pred, evidence_refs, n_evidence, elapsed_s。"""
    pairs = [(r["gold"], r["pred"]) for r in rows]
    n = len(rows)
    cited = sum(1 for r in rows if r.get("has_citation"))
    covered = sum(1 for r in rows if r.get("n_evidence", 0) > 0)
    elapsed = [r.get("elapsed_s", 0.0) for r in rows]
    return {
        "n": n,
        "accuracy": accuracy(pairs),
        "macro_f1": macro_f1(pairs),
        "per_class_f1": per_class_f1(pairs),
        "confusion": confusion(pairs),
        "citation_rate": round(cited / n, 4) if n else 0.0,
        "evidence_coverage": round(covered / n, 4) if n else 0.0,
        "avg_elapsed_s": round(sum(elapsed) / n, 2) if n else 0.0,
    }


def markdown_table(summaries: dict[str, dict]) -> str:
    """把 {config: summary} 渲染成对比 Markdown 表。"""
    head = "| 配置 | 准确率 | macro-F1 | 引用有效率 | 证据覆盖率 | 平均耗时(s) |\n"
    head += "|---|---|---|---|---|---|\n"
    rows = []
    for cfg, s in summaries.items():
        rows.append(
            f"| {cfg} | {s['accuracy']:.3f} | {s['macro_f1']:.3f} | "
            f"{s['citation_rate']:.3f} | {s['evidence_coverage']:.3f} | {s['avg_elapsed_s']:.1f} |"
        )
    return head + "\n".join(rows) + "\n"
