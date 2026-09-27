"""在测试集上跑多种配置并计算指标。

用法：
  python scripts/run_experiments.py --testset data/testset/pilot.csv --configs baseline,no_multi_agent,full,no_source_filter,no_rerank
  python scripts/run_experiments.py --limit 2 --configs full            # 快速 dry-run
结果写入 data/experiments/ ：results.json（原始）+ report.md（对比表）。
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.models import VerdictLabel  # noqa: E402
from app.experiments import metrics, variants  # noqa: E402

CONFIGS = ["baseline", "no_multi_agent", "full", "no_source_filter", "no_rerank"]
GOLD_KEYS = ["gold", "label", "suggested_label", "final_label"]


def load_testset(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            claim = (r.get("claim") or "").strip()
            if not claim:
                continue
            gold = ""
            for k in GOLD_KEYS:
                if r.get(k):
                    gold = r[k].strip().lower()
                    break
            if gold not in ("support", "refute", "insufficient"):
                print(f"[warn] 跳过（标签无效）: {r.get('id')} gold='{gold}'")
                continue
            rows.append({"id": r.get("id", ""), "domain": r.get("domain", ""), "claim": claim, "gold": gold})
    return rows


def _verdict_value(v) -> str:
    return v.verdict.value if hasattr(v.verdict, "value") else str(v.verdict)


def run_one(config: str, sample: dict) -> dict:
    claim = sample["claim"]
    t0 = time.perf_counter()
    if config == "baseline":
        out = variants.run_baseline(claim)
        pred, conf, n_ev, cite = out["verdict"], out["confidence"], 0, False
    elif config == "no_multi_agent":
        out = variants.run_single_agent(claim)
        pred, conf, n_ev, cite = out["verdict"], out["confidence"], out.get("n_evidence", 0), out.get("n_evidence", 0) > 0
    else:
        skip_assess = config == "no_source_filter"
        skip_rerank = config == "no_rerank"
        st = variants.run_pipeline(claim, task_id=f"exp-{sample['id']}", skip_assess=skip_assess, skip_rerank=skip_rerank)
        verdicts = st.get("verdicts", [])
        pred = variants._aggregate(verdicts)
        conf = round(sum(v.confidence for v in verdicts) / len(verdicts), 2) if verdicts else 0.0
        n_ev = len(st.get("evidences", []))
        cite = any(v.evidence_refs for v in verdicts)
    return {
        "id": sample["id"], "domain": sample["domain"], "claim": claim,
        "gold": sample["gold"], "pred": pred, "confidence": conf,
        "n_evidence": n_ev, "has_citation": bool(cite),
        "elapsed_s": round(time.perf_counter() - t0, 2),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--testset", default="data/testset/pilot.csv")
    ap.add_argument("--configs", default=",".join(CONFIGS))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--out", default="data/experiments")
    args = ap.parse_args()

    testset_path = Path(args.testset)
    if not testset_path.is_absolute():
        testset_path = Path(__file__).resolve().parent.parent / testset_path
    if not testset_path.exists():
        print(f"[error] 测试集不存在: {testset_path}")
        sys.exit(1)

    samples = load_testset(testset_path)
    if args.limit:
        samples = samples[: args.limit]
    configs = [c.strip() for c in args.configs.split(",") if c.strip()]
    print(f"测试集: {testset_path.name}  样本数: {len(samples)}  配置: {configs}")

    all_rows: dict[str, list[dict]] = {}
    for cfg in configs:
        rows = []
        for i, s in enumerate(samples, 1):
            try:
                row = run_one(cfg, s)
            except Exception as exc:  # noqa: BLE001
                print(f"  [{cfg}] {s['id']} 出错: {exc}")
                row = {"id": s["id"], "domain": s["domain"], "claim": s["claim"],
                       "gold": s["gold"], "pred": "error", "confidence": 0.0,
                       "n_evidence": 0, "has_citation": False, "elapsed_s": 0.0}
            rows.append(row)
            print(f"  [{cfg}] {i}/{len(samples)} {s['id']} gold={row['gold']} pred={row['pred']} ({row['elapsed_s']}s)")
        all_rows[cfg] = rows

    summaries = {cfg: metrics.summarize([r for r in rows if r["pred"] != "error"]) for cfg, rows in all_rows.items()}

    out_dir = Path(args.out)
    if not out_dir.is_absolute():
        out_dir = Path(__file__).resolve().parent.parent / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "results.json").write_text(
        json.dumps({"summaries": summaries, "rows": all_rows}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    report = ["# 实验结果\n", f"测试集: `{testset_path.name}`，样本数: {len(samples)}\n", "## 对比总表\n",
              metrics.markdown_table(summaries), "\n## 各类别 F1\n"]
    for cfg, s in summaries.items():
        report.append(f"### {cfg}")
        report.append(f"- 准确率 {s['accuracy']:.3f}，macro-F1 {s['macro_f1']:.3f}")
        report.append(f"- 各类 F1: " + "，".join(f"{metrics.LABELS_CN[k]}={v:.3f}" for k, v in s["per_class_f1"].items()))
        report.append(f"- 混淆矩阵（行=真值, 列=预测）: {json.dumps(s['confusion'], ensure_ascii=False)}")
        report.append("")
    (out_dir / "report.md").write_text("\n".join(report), encoding="utf-8")

    print("\n=== 对比总表 ===")
    print(metrics.markdown_table(summaries))
    print(f"已写入: {out_dir / 'results.json'} 和 {out_dir / 'report.md'}")


if __name__ == "__main__":
    main()
