"""Vision package — lightweight SigLIP adapter for chart / PDF screenshots."""

from safety_eval.vision.encoder import SigLipVisionEncoder, VisionCaption, get_vision_encoder, vision_enabled

__all__ = [
    "SigLipVisionEncoder",
    "VisionCaption",
    "get_vision_encoder",
    "vision_enabled",
]
