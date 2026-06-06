"""Compose post text over a background image into portrait feed cards.

The image model produces a quiet *background*; this renderer overlays the
post's title and body on top with Pillow, paginating long bodies into multiple
cards (a carousel). Text is drawn locally — image models can't render legible
text, and we explicitly forbid text in the generated backgrounds.

Card geometry is 4:5 portrait (1080x1350) to match the background aspect ratio.
"""

from __future__ import annotations

import io
import os
from dataclasses import dataclass, field

from PIL import Image, ImageDraw, ImageFont

from generators._logging import get_logger
from generators.s3_util import download_object, upload_png

logger = get_logger(__name__)

# Card geometry (4:5 portrait)
CARD_W = 1080
CARD_H = 1350
MARGIN = 90                      # safe padding around text
SCRIM_OPACITY = 140             # 0-255 dark overlay for text contrast
TITLE_SIZE = 64
BODY_SIZE = 44
LINE_SPACING = 1.35             # multiple of font size
TITLE_GAP = 36                  # px between title block and body
PARAGRAPH_GAP = 20              # extra px between paragraphs

# Common scalable TrueType fonts, tried in order. Falls back to Pillow's
# bundled DejaVuSans (load_default supports a size in Pillow >= 10.1).
_FONT_CANDIDATES = (
    "/System/Library/Fonts/Supplemental/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "DejaVuSans.ttf",
)


def _load_font(size: int, *, font_path: str | None = None) -> ImageFont.FreeTypeFont:
    candidates = ([font_path] if font_path else []) + list(_FONT_CANDIDATES)
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except (OSError, ValueError):
            continue
    # Last resort: Pillow's built-in font, scaled.
    return ImageFont.load_default(size=size)


@dataclass
class CardStyle:
    """Tunable layout knobs (overridable per render call)."""

    width: int = CARD_W
    height: int = CARD_H
    margin: int = MARGIN
    scrim_opacity: int = SCRIM_OPACITY
    title_size: int = TITLE_SIZE
    body_size: int = BODY_SIZE
    line_spacing: float = LINE_SPACING
    title_gap: int = TITLE_GAP
    paragraph_gap: int = PARAGRAPH_GAP
    text_color: tuple[int, int, int] = (255, 255, 255)
    font_path: str | None = None


@dataclass
class _Line:
    text: str
    font: ImageFont.FreeTypeFont
    height: int
    is_paragraph_break: bool = False


@dataclass
class _Page:
    lines: list[_Line] = field(default_factory=list)


class PostImageRenderer:
    """Renders post cards. Pure rendering returns PNG bytes; `render` also uploads.

    Pass `bucket` (+ optional region) only if you intend to call `render`, which
    uploads to S3. `render_cards` is pure and needs no AWS.
    """

    def __init__(
        self,
        bucket: str | None = None,
        *,
        region: str | None = None,
        style: CardStyle | None = None,
    ):
        self.bucket = bucket
        self.region = region
        self.style = style or CardStyle()

    # -------------------------------------------------------------- public API

    def render(self, background_png: bytes, title: str, body: str) -> list[str]:
        """Render cards and upload each to S3. Returns the list of card URLs."""
        if not self.bucket:
            raise RuntimeError("PostImageRenderer.render requires a bucket")
        pages = self.render_cards(background_png, title, body)
        urls = [
            upload_png(png, self.bucket, key_prefix="post-images", region=self.region)
            for png in pages
        ]
        logger.info("post_cards_rendered", extra={"cards": len(urls)})
        return urls

    def render_from_url(self, background_url: str, title: str, body: str) -> list[str]:
        """Fetch a background from S3, render cards, upload them. Returns card URLs."""
        background_png = download_object(background_url, region=self.region)
        return self.render(background_png, title, body)

    def render_cards(self, background_png: bytes, title: str, body: str) -> list[bytes]:
        """Render the post into one or more card PNGs. Pure — no network."""
        s = self.style
        background = self._prepare_background(background_png)

        title_font = _load_font(s.title_size, font_path=s.font_path)
        body_font = _load_font(s.body_size, font_path=s.font_path)

        # A throwaway draw context for text measurement.
        measure = ImageDraw.Draw(Image.new("RGB", (s.width, s.height)))
        max_text_w = s.width - 2 * s.margin
        max_text_h = s.height - 2 * s.margin

        title_lines = self._wrap(measure, title, title_font, max_text_w)
        body_lines = self._wrap_body(measure, body, body_font, max_text_w)

        pages = self._paginate(title_lines, body_lines, max_text_h)
        return [self._draw_page(background, page) for page in pages]

    # ----------------------------------------------------------- layout helpers

    def _prepare_background(self, background_png: bytes) -> Image.Image:
        """Decode, cover-fit to the card, and darken with a scrim."""
        s = self.style
        img = Image.open(io.BytesIO(background_png)).convert("RGB")
        img = self._cover_fit(img, s.width, s.height)
        scrim = Image.new("RGBA", (s.width, s.height), (0, 0, 0, s.scrim_opacity))
        img = Image.alpha_composite(img.convert("RGBA"), scrim).convert("RGB")
        return img

    @staticmethod
    def _cover_fit(img: Image.Image, w: int, h: int) -> Image.Image:
        """Scale + center-crop so the image fully covers a w×h box."""
        src_w, src_h = img.size
        scale = max(w / src_w, h / src_h)
        new_w, new_h = int(src_w * scale + 0.5), int(src_h * scale + 0.5)
        img = img.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - w) // 2
        top = (new_h - h) // 2
        return img.crop((left, top, left + w, top + h))

    def _line_height(self, font: ImageFont.FreeTypeFont) -> int:
        ascent, descent = font.getmetrics()
        return int((ascent + descent) * self.style.line_spacing)

    def _wrap(
        self,
        draw: ImageDraw.ImageDraw,
        text: str,
        font: ImageFont.FreeTypeFont,
        max_w: int,
    ) -> list[_Line]:
        """Greedy word wrap of a single block of text."""
        lh = self._line_height(font)
        lines: list[_Line] = []
        words = text.split()
        if not words:
            return lines
        current = words[0]
        for word in words[1:]:
            trial = f"{current} {word}"
            if draw.textlength(trial, font=font) <= max_w:
                current = trial
            else:
                lines.append(_Line(current, font, lh))
                current = word
        lines.append(_Line(current, font, lh))
        return lines

    def _wrap_body(
        self,
        draw: ImageDraw.ImageDraw,
        body: str,
        font: ImageFont.FreeTypeFont,
        max_w: int,
    ) -> list[_Line]:
        """Wrap each paragraph; mark the first line of each as a paragraph start."""
        out: list[_Line] = []
        paragraphs = [p for p in body.split("\n") if p.strip()]
        for i, para in enumerate(paragraphs):
            wrapped = self._wrap(draw, para, font, max_w)
            if wrapped and i > 0:
                wrapped[0].is_paragraph_break = True
            out.extend(wrapped)
        return out

    def _paginate(
        self,
        title_lines: list[_Line],
        body_lines: list[_Line],
        max_h: int,
    ) -> list[_Page]:
        """Split lines into pages that each fit within max_h.

        The title block goes only on the first page.
        """
        s = self.style
        pages: list[_Page] = []
        page = _Page()
        used = 0

        # Title block on page 1.
        for ln in title_lines:
            page.lines.append(ln)
            used += ln.height
        if title_lines:
            used += s.title_gap
            page.lines.append(_Line("", title_lines[0].font, s.title_gap))

        for ln in body_lines:
            extra = s.paragraph_gap if ln.is_paragraph_break else 0
            needed = ln.height + extra
            if used + needed > max_h and page.lines:
                pages.append(page)
                page = _Page()
                used = 0
                extra = 0  # no leading paragraph gap at the top of a new page
            if extra:
                page.lines.append(_Line("", ln.font, extra))
                used += extra
            page.lines.append(ln)
            used += ln.height

        if page.lines:
            pages.append(page)
        return pages or [_Page()]

    def _draw_page(self, background: Image.Image, page: _Page) -> bytes:
        s = self.style
        img = background.copy()
        draw = ImageDraw.Draw(img)
        y = s.margin
        for ln in page.lines:
            if ln.text:
                draw.text((s.margin, y), ln.text, font=ln.font, fill=s.text_color)
            y += ln.height
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()


def get_post_image_renderer() -> PostImageRenderer | None:
    """Factory for the pipeline.

    Returns None (rendering disabled) unless the backgrounds actually live in
    S3 — i.e. an S3-backed image backend plus a bucket. On the stub backend the
    backgrounds are placeholder URLs that can't be fetched/composed, so we skip.

    Rendered cards are uploaded to POST_IMAGE_S3_BUCKET if set, otherwise to the
    same IMAGE_S3_BUCKET as the raw backgrounds. (Backgrounds are always read
    from whatever bucket their URL points at, so only the upload target matters.)
    """
    backend = os.environ.get("IMAGE_BACKEND", "stub")
    bg_bucket = os.environ.get("IMAGE_S3_BUCKET")
    if backend not in ("bedrock", "local_sdxl") or not bg_bucket:
        logger.info("post_image_renderer_disabled", extra={"backend": backend})
        return None
    region = os.environ.get("AWS_REGION", "us-east-1")
    cards_bucket = os.environ.get("POST_IMAGE_S3_BUCKET") or bg_bucket
    return PostImageRenderer(bucket=cards_bucket, region=region)
