"""Converts a merged Qwen2 / Qwen2.5 Hugging Face model to a GGUF file that Ollama can load.

Recent Ollama releases import safetensors only for their MLX engine, which does not run Qwen2 on Windows
CUDA, while GGUF (the format of Ollama's own qwen2.5 models) loads everywhere. This mirrors what
llama.cpp's convert_hf_to_gguf.py does for Qwen2, using llama.cpp's `gguf` package.
"""

from __future__ import annotations

import json
from pathlib import Path


def _looks_special(token: str) -> bool:
    return (token.startswith("<|") and token.endswith("|>")) or token in ("<pad>", "<mask>")


def _rope_theta(cfg: dict) -> float:
    return float(cfg.get("rope_theta") or (cfg.get("rope_parameters") or {}).get("rope_theta") or 1_000_000.0)


QUANTS = ("q5_0", "q8_0", "f16")


def _types(quant: str):
    """(weights, embeddings, file type). Embeddings double as the output layer in tied models, so they keep 8 bits."""
    import gguf

    Q, F = gguf.GGMLQuantizationType, gguf.LlamaFileType
    return {
        "q5_0": (Q.Q5_0, Q.Q8_0, F.MOSTLY_Q5_0),
        "q8_0": (Q.Q8_0, Q.Q8_0, F.MOSTLY_Q8_0),
        "f16": (Q.F16, Q.F16, F.MOSTLY_F16),
    }[quant]


def convert(model_dir: Path, out_file: Path, name: str, quant: str = "q5_0") -> Path:
    """Writes `out_file`; 2-D weights are quantized to `quant`, norms and biases stay f32."""
    import gguf
    import numpy as np
    import torch
    from safetensors import safe_open
    from transformers import AutoTokenizer

    cfg = json.loads((model_dir / "config.json").read_text(encoding="utf-8"))
    if cfg.get("architectures", [""])[0] != "Qwen2ForCausalLM":
        raise SystemExit(f"Only Qwen2 / Qwen2.5 models are supported here, not {cfg.get('architectures')}.")
    if (cfg.get("rope_scaling") or {}).get("type") not in (None, "default") or (cfg.get("rope_parameters") or {}).get("rope_type", "default") != "default":
        raise SystemExit("RoPE scaling is not supported by this converter.")

    arch = gguf.MODEL_ARCH.QWEN2
    n_layers = cfg["num_hidden_layers"]
    weight_type, embed_type, file_type = _types(quant)
    w = gguf.GGUFWriter(str(out_file), gguf.MODEL_ARCH_NAMES[arch])
    w.add_name(name)
    w.add_context_length(cfg["max_position_embeddings"])
    w.add_embedding_length(cfg["hidden_size"])
    w.add_feed_forward_length(cfg["intermediate_size"])
    w.add_block_count(n_layers)
    w.add_head_count(cfg["num_attention_heads"])
    w.add_head_count_kv(cfg["num_key_value_heads"])
    w.add_rope_freq_base(_rope_theta(cfg))
    w.add_layer_norm_rms_eps(cfg["rms_norm_eps"])
    w.add_file_type(file_type)

    # Vocabulary, as convert_hf_to_gguf.py writes it for GPT-2-style BPE tokenizers.
    tok = AutoTokenizer.from_pretrained(model_dir)
    reverse = {i: t for t, i in tok.get_vocab().items()}
    added = tok.get_added_vocab()
    decoder = tok.added_tokens_decoder
    tokens: list[str] = []
    types: list[int] = []
    for i in range(cfg["vocab_size"]):
        token = reverse.get(i)
        if token is None:
            tokens.append(f"[PAD{i}]")
            types.append(gguf.TokenType.UNUSED)
        elif token in added:
            special = decoder[i].special if i in decoder else False
            tokens.append(token)
            types.append(gguf.TokenType.CONTROL if special or _looks_special(token) else gguf.TokenType.USER_DEFINED)
        else:
            tokens.append(token)
            types.append(gguf.TokenType.NORMAL)
    w.add_tokenizer_model("gpt2")
    w.add_tokenizer_pre("qwen2")
    w.add_token_list(tokens)
    w.add_token_types(types)
    special = gguf.SpecialVocab(model_dir, load_merges=True, n_vocab=len(tokens))
    special.add_special_token["bos"] = False  # Qwen does not prepend a BOS token
    special.add_to_gguf(w)

    names = gguf.get_tensor_name_map(arch, n_layers)
    for shard in sorted(model_dir.glob("*.safetensors")):
        with safe_open(shard, framework="pt") as f:
            for key in f.keys():
                new = names.get_name(key, try_suffixes=(".weight", ".bias"))
                if new is None:
                    raise SystemExit(f"Unexpected tensor {key} in {shard.name}")
                t = f.get_tensor(key)
                if t.ndim == 1:
                    w.add_tensor(new, t.to(torch.float32).numpy())
                    continue
                qtype = embed_type if key.endswith(("embed_tokens.weight", "lm_head.weight")) else weight_type
                block = gguf.GGML_QUANT_SIZES[qtype][0]
                if qtype == gguf.GGMLQuantizationType.F16 or t.shape[-1] % block:
                    w.add_tensor(new, t.to(torch.float16).numpy().astype(np.float16))
                else:
                    w.add_tensor(new, gguf.quants.quantize(t.to(torch.float32).numpy(), qtype), raw_dtype=qtype)
    w.write_header_to_file()
    w.write_kv_data_to_file()
    w.write_tensors_to_file(progress=False)
    w.close()
    return out_file
