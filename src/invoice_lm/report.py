"""Collect runs/*/<dataset>/_summary.json into one markdown results table."""

import json
from pathlib import Path


# Local cost = electricity. 25 W is the whole-Mac draw measured from the battery during
# qwen2.5vl:3b inference (2026-10-21); Rs 8/kWh is a typical Indian residential tariff.
WATTS, RS_PER_KWH = 25, 8.0


def rs_per_1000(sec: float | None, backend: str) -> str:
    if sec is None or not backend.startswith(("ollama", "mlx")):
        return "–"
    return f"₹{sec * 1000 / 3600 * WATTS / 1000 * RS_PER_KWH:.2f}"


def _pct(x) -> str:
    return "–" if x is None else f"{100 * x:.1f}%"


def table(runs_dir: Path = Path("runs")) -> str:
    out = ["| Model | Set | n | Parsed | Field acc | Critical all correct | Line F1 "
           "| Validators caught | False flags | Silent errors | Sec/invoice | ₹ per 1,000 (power) |",
           "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    inj = ["", "| Model | Injected invoices | Caught (correct or flagged) | Obeyed silently |",
           "|---|---|---|---|"]
    levels = ["", "| Model | Clean | Scan | Photo | Classic | Minimal | Handwritten | Thermal |",
              "|---|---|---|---|---|---|---|---|"]
    scripts = ["", "| Model | Hindi (Devanagari) | Kannada |", "|---|---|---|"]
    for f in sorted(runs_dir.glob("*/*/_summary.json")):
        model, ds = f.parent.parent.name, f.parent.name
        s = json.loads(f.read_text())
        o = s["overall"]
        if "injection_caught" in s:
            inj.append(f"| {model} | {o['n']} | {_pct(s['injection_caught'])} "
                       f"| {_pct(s['injection_obeyed_silently'])} |")
            continue
        out.append(f"| {model} | {ds} | {o['n']} | {_pct(o['parse_rate'])} | {_pct(o['field_acc'])} "
                   f"| {_pct(o['critical_all_correct'])} | {_pct(o['line_f1'])} "
                   f"| {_pct(o.get('validator_catch_rate'))} | {_pct(o.get('false_flag_rate'))} "
                   f"| {_pct(o.get('silent_error_rate'))} | {s.get('sec_per_invoice')} "
                   f"| {rs_per_1000(s.get('sec_per_invoice'), model)} |")
        cell = lambda grp, k: _pct(s.get(grp, {}).get(k, {}).get("field_acc"))  # noqa: E731
        if "by_script" in s:
            scripts.append(f"| {model} | {cell('by_script', 'deva')} | {cell('by_script', 'knda')} |")
            continue
        levels.append(f"| {model} | " + " | ".join(
            [cell("by_level", k) for k in ("clean", "scan", "photo")]
            + [cell("by_layout", k) for k in ("classic", "minimal", "handwritten", "thermal")]) + " |")
    tail = ["", "Field accuracy on regional-language invoices:", *scripts] if len(scripts) > 3 else []
    return "\n".join(out + ["", "Field accuracy by difficulty and layout:"] + levels + inj + tail) + "\n"


if __name__ == "__main__":
    print(table())
