"""Count supplier/buyer swaps: the model put the buyer's GSTIN or name in the supplier block,
or the other way round. Both GSTINs are valid, so the validators can't see this error.

    uv run python eval/count_swaps.py [runs dir]
"""

import json
import sys
from pathlib import Path

from invoice_lm.schema import GSTInvoice
from invoice_lm.validators import validate


def _n(v) -> str:
    return "".join(str(v or "").upper().split())


def swapped(pred: GSTInvoice, gold: GSTInvoice) -> bool:
    for field in ("gstin", "name"):
        ps, pb = _n(getattr(pred.supplier, field)), _n(getattr(pred.buyer, field))
        gs, gb = _n(getattr(gold.supplier, field)), _n(getattr(gold.buyer, field))
        if gs != gb and ((ps and ps == gb) or (pb and pb == gs)):
            return True
    return False


def main(runs: Path) -> None:
    print("| Model | Set | n | Supplier/buyer swaps | Swapped and not flagged |")
    print("|---|---|---|---|---|")
    for results in sorted(runs.glob("*/*/_results.jsonl")):
        cache, ds = results.parent, Path("data") / results.parent.name
        rows = [json.loads(line) for line in results.open()]
        swaps = silent = 0
        for r in rows:
            out = json.loads((cache / f"{r['id']}.json").read_text())
            pred = validate(out.get("text") or "").invoice
            gold = GSTInvoice.model_validate_json((ds / "labels" / f"{r['id']}.json").read_text())
            if pred and swapped(pred, gold):
                swaps += 1
                silent += not r["needs_review"]
        print(f"| {cache.parent.name} | {cache.name} | {len(rows)} | {swaps} | {silent} |")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("runs"))
