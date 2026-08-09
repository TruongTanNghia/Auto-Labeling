"""Kiem thu phash, ssim, blur_score va DuplicateFilter."""
from __future__ import annotations

import cv2
from app.core import image_quality as iq


def test_image_quality_and_dedupe(sample_data):
    img_dir, _ = sample_data
    img_path = str(img_dir / "img_000.jpg")
    img = cv2.imread(img_path)
    assert img is not None

    # Test phash
    ph = iq.phash(img)
    assert len(ph) == 16

    # Test SSIM
    ssim_val = iq.ssim(img, img)
    assert abs(ssim_val - 1.0) < 0.01

    # Test blur score
    analysis = iq.analyze(img)
    assert analysis.blur_score > 0

    # Test duplicate filter
    df = iq.DuplicateFilter()
    is_dup1, _, _ = df.check(img, 0)
    assert is_dup1 is False

    is_dup2, _, _ = df.check(img, 1)
    assert is_dup2 is True
