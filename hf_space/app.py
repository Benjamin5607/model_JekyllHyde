"""
Jekyll & Hyde — Hugging Face Gradio Space demo.

Loads Gemma 2 2B + dual LoRA from Hub, MoE blend + dynamic decoding.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent if (HERE.parent / "safety_eval").exists() else HERE
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import gradio as gr

BASE_MODEL = os.environ.get("HF_BASE_MODEL", "google/gemma-2-2b-it")
JEKYLL_ADAPTER = os.environ.get("HF_JEKYLL_ADAPTER", "Benjamin5607/jekyll-hyde-jekyll-lora")
HYDE_ADAPTER = os.environ.get("HF_HYDE_ADAPTER", "Benjamin5607/jekyll-hyde-hyde-lora")

_model = None
_tokenizer = None
_load_error: str | None = None
_warmed: set[str] = set()
_last_bucket: str | None = None
_active_adapter = "jekyll"


def _gpu_wrap(fn):
    try:
        import spaces

        return spaces.GPU(fn)
    except ImportError:
        return fn


@_gpu_wrap
def _load_model() -> str:
    global _model, _tokenizer, _load_error, _active_adapter
    if _model is not None:
        return "Model already loaded."

    try:
        import torch
        from huggingface_hub import login
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

        token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
        if token:
            login(token=token, add_to_git_credential=False)

        tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        if torch.cuda.is_available():
            quant = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_use_double_quant=True,
            )
            base = AutoModelForCausalLM.from_pretrained(
                BASE_MODEL,
                trust_remote_code=True,
                quantization_config=quant,
                device_map="auto",
            )
        else:
            base = AutoModelForCausalLM.from_pretrained(
                BASE_MODEL,
                trust_remote_code=True,
                torch_dtype=torch.float32,
                device_map="cpu",
            )

        model = PeftModel.from_pretrained(base, JEKYLL_ADAPTER, adapter_name="jekyll")
        model.load_adapter(HYDE_ADAPTER, adapter_name="hyde")
        model.set_adapter("jekyll")
        model.eval()

        from safety_eval.platform.lora_mix_cache import MOE_BUCKETS

        for name, jw, hw in MOE_BUCKETS:
            try:
                if name not in getattr(model, "peft_config", {}):
                    model.add_weighted_adapter(
                        adapters=["jekyll", "hyde"],
                        weights=[jw, hw],
                        adapter_name=name,
                        combination_type="linear",
                    )
                _warmed.add(name)
            except Exception:
                pass
        model.set_adapter("jekyll")

        _model = model
        _tokenizer = tokenizer
        _active_adapter = "jekyll"
        _load_error = None
        device = "CUDA" if torch.cuda.is_available() else "CPU"
        return f"Ready on {device} · base={BASE_MODEL} · adapters from Hub"
    except Exception as exc:
        _load_error = str(exc)
        return f"Load failed: {exc}\nAccept Gemma license + upload adapters (scripts/upload_hf_hub.py)."


def _set_mix(jekyll_w: float, hyde_w: float) -> dict:
    from safety_eval.platform.lora_mix_cache import record_mix_usage, snap_to_bucket

    global _last_bucket, _active_adapter
    snap = snap_to_bucket(jekyll_w, hyde_w)
    record_mix_usage(snap)
    if _last_bucket == snap.bucket_id:
        return snap.to_dict()

    if snap.adapter_name in ("jekyll", "hyde"):
        _model.set_adapter(snap.adapter_name)
        _active_adapter = snap.adapter_name
    else:
        if snap.adapter_name not in getattr(_model, "peft_config", {}):
            _model.add_weighted_adapter(
                adapters=["jekyll", "hyde"],
                weights=[snap.jekyll, snap.hyde],
                adapter_name=snap.adapter_name,
                combination_type="linear",
            )
        _model.set_adapter(snap.adapter_name)
        _active_adapter = snap.adapter_name
    _last_bucket = snap.bucket_id
    return snap.to_dict()


def _generate(user_text: str, mode: str, history: list[tuple[str, str]]) -> tuple:
    import torch
    from safety_eval.platform.decoding_entropy import apply_to_generation_kwargs, decoding_for_lora_mix
    from safety_eval.platform.lora_router import compute_lora_mix
    from safety_eval.platform.local_model import clean_generation, normalize_messages

    if _model is None or _tokenizer is None:
        status = _load_model()
        if _model is None:
            history = history + [(user_text, f"⚠ {status}")]
            return history, "", "Model not loaded", 0.5

    mode_key = (mode or "chat").lower()
    mix = compute_lora_mix(mode=mode_key, user_text=user_text)
    mix_info = _set_mix(mix.jekyll, mix.hyde)
    decode = decoding_for_lora_mix(mix.jekyll, mix.hyde)

    messages: list[dict[str, str]] = []
    for u, a in history[-6:]:
        messages.append({"role": "user", "content": u})
        messages.append({"role": "assistant", "content": a})
    messages.append({"role": "user", "content": user_text})
    norm = normalize_messages(messages)
    prompt = _tokenizer.apply_chat_template(norm, tokenize=False, add_generation_prompt=True)
    inputs = _tokenizer(prompt, return_tensors="pt")
    device = next(_model.parameters()).device
    inputs = {k: v.to(device) for k, v in inputs.items()}

    gen_kwargs = apply_to_generation_kwargs(
        decode,
        {
            "max_new_tokens": 384,
            "pad_token_id": _tokenizer.pad_token_id or _tokenizer.eos_token_id,
            "eos_token_id": _tokenizer.eos_token_id,
            "repetition_penalty": 1.12,
            "no_repeat_ngram_size": 4,
        },
    )

    with torch.no_grad():
        out = _model.generate(**inputs, **gen_kwargs)
    text = clean_generation(_tokenizer.decode(out[0][inputs["input_ids"].shape[1] :], skip_special_tokens=True))

    if mode_key == "duel":
        hyde_mix = _set_mix(0.0, 1.0)
        _model.set_adapter("hyde")
        hyde_prompt = _tokenizer.apply_chat_template(
            normalize_messages(
                [
                    {"role": "user", "content": user_text},
                    {"role": "assistant", "content": text},
                    {"role": "user", "content": "Hyde: challenge assumptions and probe gray zones."},
                ]
            ),
            tokenize=False,
            add_generation_prompt=True,
        )
        h_in = _tokenizer(hyde_prompt, return_tensors="pt")
        h_in = {k: v.to(device) for k, v in h_in.items()}
        with torch.no_grad():
            h_out = _model.generate(**h_in, **gen_kwargs)
        hyde_txt = clean_generation(
            _tokenizer.decode(h_out[0][h_in["input_ids"].shape[1] :], skip_special_tokens=True)
        )
        blend = _set_mix(0.5, 0.5)
        mid_decode = decoding_for_lora_mix(0.5, 0.5)
        mid_kwargs = apply_to_generation_kwargs(mid_decode, dict(gen_kwargs))
        syn_prompt = _tokenizer.apply_chat_template(
            normalize_messages(
                [
                    {"role": "user", "content": user_text},
                    {"role": "assistant", "content": f"Jekyll:\n{text}\n\nHyde:\n{hyde_txt}"},
                    {"role": "user", "content": "Synthesize a balanced middle-ground verdict."},
                ]
            ),
            tokenize=False,
            add_generation_prompt=True,
        )
        s_in = _tokenizer(syn_prompt, return_tensors="pt")
        s_in = {k: v.to(device) for k, v in s_in.items()}
        with torch.no_grad():
            s_out = _model.generate(**s_in, **mid_kwargs)
        syn = clean_generation(_tokenizer.decode(s_out[0][s_in["input_ids"].shape[1] :], skip_special_tokens=True))
        text = f"**Jekyll**\n{text}\n\n**Hyde**\n{hyde_txt}\n\n**Middle ground**\n{syn}"
        mix_info = blend

    blend_label = f"Jekyll {int(mix_info['jekyll'] * 100)}% · Hyde {int(mix_info['hyde'] * 100)}%"
    decode_label = f"temp={decode.temperature:.2f} · {decode.profile}"
    history = history + [(user_text, text)]
    return history, "", f"{blend_label} · {decode_label}", mix_info.get("jekyll", 0.5)


def build_ui() -> gr.Blocks:
    with gr.Blocks(
        title="Jekyll & Hyde",
        theme=gr.themes.Soft(primary_hue="teal", secondary_hue="red"),
    ) as demo:
        gr.Markdown(
            "# 🎭 Jekyll & Hyde\n"
            "Gemma 2 2B + dual LoRA · MoE blend · dynamic decoding  \n"
            f"Adapters: [`{JEKYLL_ADAPTER}`](https://huggingface.co/{JEKYLL_ADAPTER}) · "
            f"[`{HYDE_ADAPTER}`](https://huggingface.co/{HYDE_ADAPTER})"
        )
        with gr.Row():
            mode = gr.Radio(
                ["chat", "jekyll", "hyde", "duel"],
                value="chat",
                label="Mode",
                info="Chat = auto MoE · Duel = Jekyll + Hyde + synthesis",
            )
            load_btn = gr.Button("Load model", variant="secondary")
        load_status = gr.Textbox(label="Status", interactive=False, value="Click Load model (first request also auto-loads)")
        blend_bar = gr.Slider(0, 1, value=0.7, label="LoRA mix (Jekyll ← → Hyde)", interactive=False)
        blend_meta = gr.Textbox(label="Decoding", interactive=False)
        chat = gr.Chatbot(label="Chat", height=420)
        msg = gr.Textbox(label="Message", placeholder="Audit gray zones in our IT policy…")
        with gr.Row():
            send = gr.Button("Send", variant="primary")
            clear = gr.Button("Clear")

        load_btn.click(_load_model, outputs=load_status)

        def respond(user_text, mode_val, history):
            if not user_text.strip():
                return history, "", blend_meta.value or "", blend_bar.value
            hist, _, meta, j_ratio = _generate(user_text, mode_val, history or [])
            return hist, "", meta, j_ratio

        send.click(respond, [msg, mode, chat], [chat, msg, blend_meta, blend_bar])
        msg.submit(respond, [msg, mode, chat], [chat, msg, blend_meta, blend_bar])
        clear.click(lambda: ([], "", "", 0.7), outputs=[chat, msg, blend_meta, blend_bar])

        gr.Markdown(
            "---\n"
            "**Tips:** Accept [Gemma 2 license](https://huggingface.co/google/gemma-2-2b-it) on HF. "
            "Use GPU hardware on Spaces. "
            "[Full platform on GitHub](https://github.com/Benjamin5607/model_JekyllHyde)"
        )
    return demo


if __name__ == "__main__":
    demo = build_ui()
    demo.queue(max_size=8).launch(server_name="0.0.0.0", server_port=int(os.environ.get("PORT", 7860)))
