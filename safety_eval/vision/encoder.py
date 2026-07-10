"""Lightweight vision encoder — SigLIP for chart / document image captions."""

from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = ROOT / "config" / "vision.yaml"


def _load_cfg() -> dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {"vision": {"enabled": False}}
    with CONFIG_PATH.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@dataclass
class VisionCaption:
    text: str
    model: str
    labels: list[tuple[str, float]]

    def to_dict(self) -> dict[str, Any]:
        return {"text": self.text, "model": self.model, "labels": self.labels}


class SigLipVisionEncoder:
    """Zero-shot image classification / soft caption via SigLIP."""

    def __init__(self, model_id: str | None = None):
        cfg = _load_cfg().get("vision", {})
        self.model_id = model_id or cfg.get("siglip_model", "google/siglip-base-patch16-224")
        self._model = None
        self._processor = None
        self._default_labels = list(cfg.get("chart_labels", [
            "stock price candlestick chart",
            "line chart financial data",
            "bar chart quarterly revenue",
            "regulatory infographic",
            "corporate presentation slide",
            "table of numbers",
            "document screenshot",
        ]))

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        try:
            from transformers import AutoModel, AutoProcessor

            self._processor = AutoProcessor.from_pretrained(self.model_id)
            self._model = AutoModel.from_pretrained(self.model_id)
            self._model.eval()
        except Exception as exc:
            raise RuntimeError(
                f"Vision deps missing. pip install -e '.[vision]' — {exc}"
            ) from exc

    def describe_image_bytes(self, data: bytes, *, labels: list[str] | None = None) -> VisionCaption:
        from PIL import Image
        import torch

        self._ensure_loaded()
        labels = labels or self._default_labels
        image = Image.open(io.BytesIO(data)).convert("RGB")
        inputs = self._processor(text=labels, images=image, return_tensors="pt", padding=True)
        with torch.no_grad():
            outputs = self._model(**inputs)
            logits = outputs.logits_per_image[0]
            probs = torch.softmax(logits, dim=0).tolist()
        ranked = sorted(zip(labels, probs), key=lambda x: x[1], reverse=True)
        top_label, top_score = ranked[0]
        text = f"Image analysis (SigLIP): likely '{top_label}' (confidence {top_score:.2f})."
        if len(ranked) > 1:
            alt = ", ".join(f"{l} ({s:.2f})" for l, s in ranked[1:3])
            text += f" Alternatives: {alt}."
        return VisionCaption(text=text, model=self.model_id, labels=ranked[:5])

    def describe_base64(self, b64: str, **kwargs: Any) -> VisionCaption:
        raw = b64.split(",", 1)[-1] if b64.startswith("data:") else b64
        return self.describe_image_bytes(base64.b64decode(raw), **kwargs)


_encoder: SigLipVisionEncoder | None = None


def get_vision_encoder() -> SigLipVisionEncoder:
    global _encoder
    if _encoder is None:
        _encoder = SigLipVisionEncoder()
    return _encoder


def vision_enabled() -> bool:
    return bool(_load_cfg().get("vision", {}).get("enabled", False))
