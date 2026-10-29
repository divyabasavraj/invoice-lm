"""Write a synthetic dataset: images/, labels/ and a manifest.jsonl.

Each sample gets a difficulty level (clean / scan / photo) and a split
(train / val / test). Both are drawn from a per-sample RNG, so sample i keeps
its split when the dataset grows and the test set never leaks into training.
"""

import json
import random
from pathlib import Path

from invoice_lm.generator.augment import augment
from invoice_lm.generator.data import random_invoice
from invoice_lm.generator.inject import ATTACKS, STYLES, add_injection
from invoice_lm.generator.regional import regional_invoice
from invoice_lm.generator.render import printed_label, render
from invoice_lm.schema import SCHEMA_VERSION

LEVEL_WEIGHTS = {"clean": 0.3, "scan": 0.3, "photo": 0.4}
SPLIT_WEIGHTS = {"train": 0.8, "val": 0.1, "test": 0.1}


def _pick(rng: random.Random, weights: dict[str, float]) -> str:
    return rng.choices(list(weights), list(weights.values()))[0]


def _save(out: Path, sid: str, img, level: str) -> str:
    # Clean renders stay lossless; degraded ones are already JPEG-compressed.
    name = f"images/{sid}.png" if level == "clean" else f"images/{sid}.jpg"
    if level == "clean":
        img.save(out / name, optimize=True)
    else:
        img.save(out / name, quality=92)
    return name


def build(out: Path, n: int, seed: int = 0) -> Path:
    (out / "images").mkdir(parents=True, exist_ok=True)
    (out / "labels").mkdir(exist_ok=True)
    manifest = out / "manifest.jsonl"
    with manifest.open("w") as mf:
        for i in range(n):
            rng = random.Random(f"{seed}-{i}")
            split = _pick(random.Random(f"split-{seed}-{i}"), SPLIT_WEIGHTS)
            inv = random_invoice(rng)
            img, settings = render(inv, rng)
            level = _pick(rng, LEVEL_WEIGHTS)
            img = augment(img, rng, level)
            sid = f"syn_{seed}_{i:05d}"
            name = _save(out, sid, img, level)
            label = printed_label(inv, settings["layout"])
            (out / "labels" / f"{sid}.json").write_text(label.model_dump_json(indent=2))
            mf.write(json.dumps({
                "id": sid, "image": name, "label": f"labels/{sid}.json", "split": split,
                "level": level, "schema_version": SCHEMA_VERSION, "seed": seed, **settings,
                "supply_type": inv.supply_type.value, "n_items": len(inv.line_items),
            }) + "\n")
    return manifest


def build_injection_set(out: Path, seed: int = 1000) -> Path:
    """One invoice per (attack, style): 8 x 3 = 24 test-only samples."""
    (out / "images").mkdir(parents=True, exist_ok=True)
    (out / "labels").mkdir(exist_ok=True)
    manifest = out / "manifest.jsonl"
    with manifest.open("w") as mf:
        k = 0
        for attack_id, _, target in ATTACKS:
            for style in STYLES:
                rng = random.Random(f"inj-{seed}-{k}")
                inv = random_invoice(rng)
                img, settings = render(inv, rng, layout=rng.choice(["classic", "minimal"]))
                img = add_injection(img, rng, attack_id, style)
                level = "clean" if style == "low_contrast" else rng.choice(["clean", "scan"])
                img = augment(img, rng, level)
                sid = f"inj_{k:03d}"
                name = _save(out, sid, img, level)
                label = printed_label(inv, settings["layout"])
                (out / "labels" / f"{sid}.json").write_text(label.model_dump_json(indent=2))
                mf.write(json.dumps({
                    "id": sid, "image": name, "label": f"labels/{sid}.json", "split": "test",
                    "level": level, "attack": attack_id, "attack_style": style,
                    "attack_target": target, "schema_version": SCHEMA_VERSION, **settings,
                    "supply_type": inv.supply_type.value, "n_items": len(inv.line_items),
                }) + "\n")
                k += 1
    return manifest


def build_regional_set(out: Path, n: int = 40, seed: int = 2000) -> Path:
    """Hindi / Kannada invoices (hard-case test set, milestone 7). Test only."""
    (out / "images").mkdir(parents=True, exist_ok=True)
    (out / "labels").mkdir(exist_ok=True)
    manifest = out / "manifest.jsonl"
    with manifest.open("w") as mf:
        for i in range(n):
            rng = random.Random(f"reg-{seed}-{i}")
            inv, script = regional_invoice(rng, "deva" if i % 2 == 0 else "knda")
            img, settings = render(inv, rng)
            level = _pick(rng, LEVEL_WEIGHTS)
            img = augment(img, rng, level)
            sid = f"reg_{i:03d}"
            name = _save(out, sid, img, level)
            label = printed_label(inv, settings["layout"])
            (out / "labels" / f"{sid}.json").write_text(label.model_dump_json(indent=2))
            mf.write(json.dumps({
                "id": sid, "image": name, "label": f"labels/{sid}.json", "split": "test",
                "level": level, "script": script, "schema_version": SCHEMA_VERSION, **settings,
                "supply_type": inv.supply_type.value, "n_items": len(inv.line_items),
            }) + "\n")
    return manifest
