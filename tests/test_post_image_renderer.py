"""Tests for the post-card renderer (pure rendering, no AWS)."""

import io

from PIL import Image

from generators.post_image_renderer import CARD_H, CARD_W, PostImageRenderer


def _background(w: int = 1024, h: int = 1280) -> bytes:
    img = Image.new("RGB", (w, h), (40, 60, 80))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _open(card: bytes) -> Image.Image:
    return Image.open(io.BytesIO(card))


def test_short_body_is_single_card():
    r = PostImageRenderer()
    cards = r.render_cards(_background(), "A short title", "One sentence body.")
    assert len(cards) == 1


def test_long_body_paginates_into_carousel():
    r = PostImageRenderer()
    para = (
        "A determinant measures how much a linear transformation scales area. "
        "When it is zero the transformation collapses space into fewer dimensions. "
    )
    body = "\n".join([para * 4] * 5)
    cards = r.render_cards(_background(), "Deep dive", body)
    assert len(cards) > 1


def test_cards_have_portrait_dimensions():
    r = PostImageRenderer()
    cards = r.render_cards(_background(), "Title", "Body text here.")
    img = _open(cards[0])
    assert img.size == (CARD_W, CARD_H)
    assert img.format == "PNG"


def test_empty_body_still_renders_one_card():
    r = PostImageRenderer()
    cards = r.render_cards(_background(), "Only a title", "")
    assert len(cards) == 1
    assert _open(cards[0]).size == (CARD_W, CARD_H)


def test_background_is_cover_fit_from_any_aspect():
    """A square background should still produce a correctly-sized portrait card."""
    r = PostImageRenderer()
    cards = r.render_cards(_background(800, 800), "Title", "Body.")
    assert _open(cards[0]).size == (CARD_W, CARD_H)


def test_render_without_bucket_raises():
    r = PostImageRenderer()  # no bucket
    try:
        r.render(_background(), "t", "b")
    except RuntimeError as e:
        assert "bucket" in str(e).lower()
    else:
        raise AssertionError("expected RuntimeError without a bucket")
