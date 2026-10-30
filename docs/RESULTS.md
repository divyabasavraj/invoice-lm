| Model | Set | n | Parsed | Field acc | Critical all correct | Line F1 | Validators caught | False flags | Silent errors | Sec/invoice | ₹ per 1,000 (power) |
|---|---|---|---|---|---|---|---|---|---|---|---|
| mlx_mlx_community_Qwen3_VL_4B_Instruct_4bit | regional_v1 | 40 | 97.5% | 81.9% | 27.5% | 89.1% | 100.0% | 0.0% | 0.0% | 28.9 | ₹1.61 |
| mlx_mlx_community_Qwen3_VL_4B_Instruct_4bit | synth_v1 | 60 | 98.3% | 85.7% | 21.7% | 89.9% | 100.0% | 0.0% | 0.0% | 30.3 | ₹1.68 |
| mlx_mlx_community_Qwen3_VL_4B_Instruct_4bit_runs_train_qwen3vl4b_lora_r16_adapters | regional_v1 | 40 | 100.0% | 89.3% | 72.5% | 93.7% | 100.0% | 0.0% | 0.0% | 23.8 | ₹1.32 |
| mlx_mlx_community_Qwen3_VL_4B_Instruct_4bit_runs_train_qwen3vl4b_lora_r16_adapters | synth_v1 | 197 | 99.5% | 96.3% | 75.6% | 98.1% | 95.8% | 0.0% | 1.0% | 25.0 | ₹1.39 |
| ollama_qwen2.5vl_3b | synth_v1 | 60 | 100.0% | 89.1% | 55.0% | 93.3% | 96.3% | 0.0% | 1.7% | 31.6 | ₹1.76 |
| ollama_qwen2.5vl_7b | synth_v1 | 60 | 100.0% | 94.1% | 60.0% | 98.0% | 100.0% | 0.0% | 0.0% | 77.0 | ₹4.28 |
| ollama_qwen3_vl_4b_instruct | synth_v1 | 60 | 100.0% | 93.5% | 63.3% | 96.8% | 100.0% | 0.0% | 0.0% | 44.8 | ₹2.49 |

Field accuracy by difficulty and layout:

| Model | Clean | Scan | Photo | Classic | Minimal | Handwritten | Thermal |
|---|---|---|---|---|---|---|---|
| mlx_mlx_community_Qwen3_VL_4B_Instruct_4bit | 91.4% | 88.3% | 81.2% | 89.2% | 88.9% | 79.2% | 82.1% |
| mlx_mlx_community_Qwen3_VL_4B_Instruct_4bit_runs_train_qwen3vl4b_lora_r16_adapters | 97.7% | 97.9% | 94.2% | 96.9% | 96.9% | 93.3% | 96.3% |
| ollama_qwen2.5vl_3b | 96.9% | 89.7% | 84.9% | 92.7% | 93.8% | 80.2% | 85.7% |
| ollama_qwen2.5vl_7b | 96.4% | 94.0% | 93.0% | 95.1% | 95.1% | 92.2% | 92.9% |
| ollama_qwen3_vl_4b_instruct | 96.8% | 94.0% | 91.5% | 95.5% | 93.8% | 93.2% | 90.5% |

| Model | Injected invoices | Caught (correct or flagged) | Obeyed silently |
|---|---|---|---|
| mlx_mlx_community_Qwen3_VL_4B_Instruct_4bit | 24 | 95.8% | 4.2% |
| mlx_mlx_community_Qwen3_VL_4B_Instruct_4bit_runs_train_qwen3vl4b_lora_r16_adapters | 24 | 100.0% | 0.0% |
| ollama_qwen2.5vl_3b | 24 | 91.7% | 8.3% |
| ollama_qwen2.5vl_7b | 24 | 100.0% | 0.0% |
| ollama_qwen3_vl_4b_instruct | 24 | 100.0% | 0.0% |

Field accuracy on regional-language invoices:

| Model | Hindi (Devanagari) | Kannada |
|---|---|---|
| mlx_mlx_community_Qwen3_VL_4B_Instruct_4bit | 83.5% | 80.2% |
| mlx_mlx_community_Qwen3_VL_4B_Instruct_4bit_runs_train_qwen3vl4b_lora_r16_adapters | 89.7% | 88.8% |

