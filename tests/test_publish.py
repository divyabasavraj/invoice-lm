import json

from invoice_lm.generator.build import build, build_injection_set
from invoice_lm.publish import stage_dataset


def test_stage_dataset_writes_imagefolder_configs(tmp_path):
    build(tmp_path / "synth", 12, 0)
    build_injection_set(tmp_path / "inj")
    out = stage_dataset(tmp_path / "hf", {"synthetic": tmp_path / "synth",
                                          "injection": tmp_path / "inj"})

    card = (out / "README.md").read_text()
    assert card.startswith("---\n") and "configs:" in card and "config_name: injection" in card

    rows = [json.loads(line) for line in (out / "synthetic" / "metadata.jsonl").open()]
    assert len(rows) == 12
    for row in rows:
        assert (out / "synthetic" / row["file_name"]).is_file()
        assert row["split"] in {"train", "val", "test"}
        assert json.loads(row["label"])["invoice_number"]  # the full label travels as JSON

    inj = [json.loads(line) for line in (out / "injection" / "metadata.jsonl").open()]
    assert len(inj) == 24 and all(r["attack"] for r in inj)


def test_stage_dataset_is_rerunnable(tmp_path):
    build(tmp_path / "synth", 3, 0)
    stage_dataset(tmp_path / "hf", {"synthetic": tmp_path / "synth"})
    out = stage_dataset(tmp_path / "hf", {"synthetic": tmp_path / "synth"})
    assert sum(1 for _ in (out / "synthetic" / "metadata.jsonl").open()) == 3
