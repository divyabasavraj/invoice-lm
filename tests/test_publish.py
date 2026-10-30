import json

from invoice_lm.generator.build import build, build_injection_set
from invoice_lm.publish import stage_dataset, stage_model


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


def test_stage_model_copies_final_adapter_only(tmp_path):
    src = tmp_path / "adapters"
    src.mkdir()
    for name in ("adapters.safetensors", "0000100_adapters.safetensors"):
        (src / name).write_bytes(b"w")
    (src / "adapter_config.json").write_text(json.dumps({"lora_parameters": {"rank": 16}}))
    out = stage_model(tmp_path / "hf_model", src)

    assert sorted(p.name for p in out.iterdir()) == [
        "README.md", "adapter_config.json", "adapters.safetensors"]
    card = (out / "README.md").read_text()
    assert card.startswith("---\n") and "base_model: mlx-community/Qwen3-VL-4B-Instruct-4bit" in card
    assert "Limits" in card and str(tmp_path) not in card
    assert stage_model(tmp_path / "hf_model", src) == out  # rerunnable
