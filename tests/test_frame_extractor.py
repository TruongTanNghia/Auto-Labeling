"""Kiem thu FrameExtractor va 5 che do cat frame từ video."""
from __future__ import annotations

from pathlib import Path
import pytest

from app.constants import (
    MODE_ADAPTIVE_MOTION,
    MODE_EVERY_FRAME,
    MODE_EVERY_N_FRAMES,
    MODE_EVERY_N_SECONDS,
    MODE_SCENE_DETECT,
)
from app.core.frame_extractor import (
    ExtractConfig,
    FrameExtractor,
    estimate_output,
    probe_video,
)


def test_probe_video(sample_data):
    _, video = sample_data
    info = probe_video(video)
    assert info is not None
    assert info.frame_count > 0


@pytest.mark.parametrize(
    "mode",
    [
        MODE_EVERY_FRAME,
        MODE_EVERY_N_FRAMES,
        MODE_EVERY_N_SECONDS,
        MODE_ADAPTIVE_MOTION,
        MODE_SCENE_DETECT,
    ],
)
def test_extraction_modes(sample_data, tmp_dir: Path, mode: str):
    _, video = sample_data
    info = probe_video(video)
    assert info is not None

    c = ExtractConfig(
        mode=mode,
        every_n_frames=5,
        every_n_seconds=0.5,
        remove_similar=False,
        blur_detection=False,
    )
    estimate_output(info, c)
    r = FrameExtractor(c).extract(video, tmp_dir / f"f_{mode}")
    assert r.n_saved > 0
