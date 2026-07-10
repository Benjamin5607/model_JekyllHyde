"""Jekyll & Hyde — ZeroGPU Space. Tokenizer at boot; model loads inside @spaces.GPU (PEFT + worker)."""

from __future__ import annotations

import os
import re
import traceback

import spaces

import gradio as gr

BASE = os.environ.get("HF_BASE_MODEL", "google/gemma-2-2b-it")
JEKYLL = os.environ.get("HF_JEKYLL_ADAPTER", "benjamin5607/jekyll-hyde-jekyll-lora")
HYDE = os.environ.get("HF_HYDE_ADAPTER", "benjamin5607/jekyll-hyde-hyde-lora")

_model = None
_tokenizer = None
_status = "Starting…"


def _hf_token() -> str | None:
    from huggingface_hub import get_token

    return os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN") or get_token()


def _boot_tokenizer() -> str:
    global _tokenizer, _status
    from huggingface_hub import login
    from transformers import AutoTokenizer

    tok = _hf_token()
    if not tok:
        _status = "Add HF_TOKEN secret + accept Gemma license."
        return _status
    login(token=tok, add_to_git_credential=False)
    _tokenizer = AutoTokenizer.from_pretrained(BASE, token=tok)
    if _tokenizer.pad_token is None:
        _tokenizer.pad_token = _tokenizer.eos_token
    _status = "Tokenizer ready — first Send loads model on GPU (~60s)."
    return _status


def _ensure_model() -> None:
    global _model
    if _model is not None:
        return
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM

    tok = _hf_token()
    base = AutoModelForCausalLM.from_pretrained(
        BASE, torch_dtype=torch.bfloat16, token=tok, device_map="cuda"
    )
    m = PeftModel.from_pretrained(base, JEKYLL, adapter_name="jekyll", token=tok)
    m.load_adapter(HYDE, adapter_name="hyde", token=tok)
    m.set_adapter("jekyll")
    m.eval()
    _model = m


def _mix(mode: str, text: str) -> tuple[str, float, float]:
    mode = (mode or "chat").lower()
    if mode == "jekyll":
        return "jekyll", 1.0, 0.0
    if mode == "hyde":
        return "hyde", 0.0, 1.0
    j, h = 0.7, 0.3
    if re.search(r"\b(hyde|probe|exploit|허점)\b", text, re.I):
        j, h = 0.3, 0.7
    elif re.search(r"\b(jekyll|policy|audit)\b", text, re.I):
        j, h = 0.85, 0.15
    elif re.search(r"\b(gray|grey|회색|middle)\b", text, re.I):
        j, h = 0.5, 0.5
    return ("jekyll" if j >= h else "hyde", j, h)


@spaces.GPU(duration=120)
def chat(user_text: str, mode: str, history: list | None) -> tuple:
    import torch

    history = history or []
    if not user_text.strip():
        return history, "", _status, 0.7

    try:
        _ensure_model()
        adapter, jw, hw = _mix(mode, user_text)
        _model.set_adapter(adapter)
        temp = 0.2 if adapter == "jekyll" else 0.35

        msgs: list[dict[str, str]] = []
        for u, a in history[-6:]:
            msgs += [{"role": "user", "content": str(u)}, {"role": "assistant", "content": str(a)}]
        msgs.append({"role": "user", "content": user_text})
        prompt = _tokenizer.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        inp = _tokenizer(prompt, return_tensors="pt")
        dev = next(_model.parameters()).device
        inp = {k: v.to(dev) for k, v in inp.items()}

        with torch.inference_mode():
            out = _model.generate(
                **inp,
                max_new_tokens=180,
                do_sample=True,
                temperature=temp,
                top_p=0.9,
                pad_token_id=_tokenizer.pad_token_id,
            )
        reply = _tokenizer.decode(out[0][inp["input_ids"].shape[1] :], skip_special_tokens=True).strip()

        if (mode or "").lower() == "duel":
            _model.set_adapter("hyde")
            msgs.append({"role": "assistant", "content": reply})
            msgs.append({"role": "user", "content": "Hyde: challenge this."})
            p2 = _tokenizer.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
            i2 = {k: v.to(dev) for k, v in _tokenizer(p2, return_tensors="pt").items()}
            with torch.inference_mode():
                o2 = _model.generate(
                    **i2, max_new_tokens=180, do_sample=True, temperature=0.35, top_p=0.9,
                    pad_token_id=_tokenizer.pad_token_id,
                )
            hyde = _tokenizer.decode(o2[0][i2["input_ids"].shape[1] :], skip_special_tokens=True).strip()
            reply = f"**Jekyll**\n{reply}\n\n**Hyde**\n{hyde}"

        return history + [(user_text, reply)], "", f"{adapter} J{int(jw*100)}:H{int(hw*100)}", jw
    except Exception:
        err = traceback.format_exc(limit=8)
        return history + [(user_text, f"Error:\n{err}")], "", "error", 0.5


try:
    _status = _boot_tokenizer()
except Exception as exc:
    _status = f"Boot failed: {exc}"


with gr.Blocks(title="Jekyll & Hyde") as demo:
    gr.Markdown("# Jekyll & Hyde\nGemma 2B + dual LoRA · ZeroGPU")
    mode = gr.Radio(["chat", "jekyll", "hyde", "duel"], value="chat", label="Mode")
    st = gr.Textbox(label="Status", value=_status, interactive=False)
    meta = gr.Textbox(label="Mix", interactive=False)
    bar = gr.Slider(0, 1, value=0.7, label="Jekyll", interactive=False)
    box = gr.Chatbot(type="tuples", height=400)
    inp = gr.Textbox(label="Message")
    send = gr.Button("Send", variant="primary")
    send.click(chat, [inp, mode, box], [box, inp, meta, bar])
    inp.submit(chat, [inp, mode, box], [box, inp, meta, bar])

demo.queue().launch()
