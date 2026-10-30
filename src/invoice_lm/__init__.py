import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(prog="invoice-lm")
    sub = parser.add_subparsers(dest="cmd", required=True)
    gen = sub.add_parser("generate", help="build a synthetic GST invoice dataset")
    gen.add_argument("--n", type=int, default=20)
    gen.add_argument("--out", type=Path, default=Path("data/synth_v0"))
    gen.add_argument("--seed", type=int, default=0)
    gen.add_argument("--injection", action="store_true",
                     help="build the 24-invoice prompt-injection test set instead")
    gen.add_argument("--regional", action="store_true",
                     help="build the Hindi/Kannada hard-case test set instead (--n invoices)")
    sub.add_parser("schema", help="print the output JSON schema")
    base = sub.add_parser("baseline", help="run a zero-shot model on a dataset split and score it")
    base.add_argument("backend", help="ollama:<model>, gemini:<model> or mlx:<hf model>[+<adapter dir>]")
    base.add_argument("--data", type=Path, default=Path("data/synth_v1"))
    base.add_argument("--split", default="test")
    base.add_argument("--limit", type=int)
    srv = sub.add_parser("serve", help="run the HTTP API and demo page (needs the api extra)")
    srv.add_argument("--port", type=int, default=8000)
    srv.add_argument("--host", default="127.0.0.1")
    sft = sub.add_parser("export-sft", help="write train/validation JSONL for mlx-vlm")
    sft.add_argument("--data", type=Path, default=Path("data/synth_v1"))
    hf = sub.add_parser("stage-hf", help="lay out the datasets as a Hugging Face dataset repo")
    hf.add_argument("--out", type=Path, default=Path("runs/hf_dataset"))
    hfm = sub.add_parser("stage-hf-model", help="lay out the LoRA adapter as a Hugging Face model repo")
    hfm.add_argument("--adapter", type=Path, default=Path("runs/train/qwen3vl4b_lora_r16/adapters"))
    hfm.add_argument("--out", type=Path, default=Path("runs/hf_model"))
    args = parser.parse_args()

    if args.cmd == "generate":
        from invoice_lm.generator.build import build, build_injection_set

        if args.regional:
            from invoice_lm.generator.build import build_regional_set

            print(f"wrote {build_regional_set(args.out, args.n)}")
        elif args.injection:
            print(f"wrote {build_injection_set(args.out)}")
        else:
            print(f"wrote {build(args.out, args.n, args.seed)}")
    elif args.cmd == "schema":
        from invoice_lm.schema import json_schema

        print(json.dumps(json_schema(), indent=2))
    elif args.cmd == "export-sft":
        from invoice_lm.sft import export

        print(f"wrote {export(args.data)}")
    elif args.cmd == "stage-hf":
        from invoice_lm.publish import stage_dataset

        print(f"wrote {stage_dataset(args.out)}")
    elif args.cmd == "stage-hf-model":
        from invoice_lm.publish import stage_model

        print(f"wrote {stage_model(args.out, args.adapter)}")
    elif args.cmd == "serve":
        import logging

        import uvicorn

        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
        uvicorn.run("invoice_lm.api:app", host=args.host, port=args.port)
    elif args.cmd == "baseline":
        from invoice_lm.baseline import run

        summary = run(args.backend, args.data, args.split, args.limit)
        print(json.dumps(summary, indent=2))
