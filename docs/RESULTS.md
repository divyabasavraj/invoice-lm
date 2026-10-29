| Model | Set | n | Parsed | Field acc | Critical all correct | Line F1 | Validators caught | False flags | Silent errors | Sec/invoice | ₹ per 1,000 (power) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| ollama_qwen2.5vl_3b | synth_v1 | 60 | 100.0% | 89.1% | 55.0% | 93.3% | 96.3% | 0.0% | 1.7% | 31.6 | ₹1.76 |
| ollama_qwen3_vl_4b_instruct | synth_v1 | 60 | 100.0% | 93.5% | 63.3% | 96.8% | 100.0% | 0.0% | 0.0% | 44.8 | ₹2.49 |

Field accuracy by difficulty and layout:

| Model | Clean | Scan | Photo | Classic | Minimal | Handwritten | Thermal |
|---|---|---|---|---|---|---|---|
| ollama_qwen2.5vl_3b | 96.9% | 89.7% | 84.9% | 92.7% | 93.8% | 80.2% | 85.7% |
| ollama_qwen3_vl_4b_instruct | 96.8% | 94.0% | 91.5% | 95.5% | 93.8% | 93.2% | 90.5% |

| Model | Injected invoices | Caught (correct or flagged) | Obeyed silently |
|---|---|---|---|
| ollama_qwen2.5vl_3b | 24 | 91.7% | 8.3% |
| ollama_qwen3_vl_4b_instruct | 24 | 100.0% | 0.0% |

