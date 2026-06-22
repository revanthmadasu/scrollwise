"""Template selection + input adaptation for data-driven post rendering.

`select_template` is a pure, deterministic function — hard-filter by content_type
and required-field feasibility, soft-score by level→vibe + capacity fit, then a
seeded weighted pick for variety (reproducible from the post_id, so re-runs don't
churn). `build_inputs` adapts already-generated post content to the chosen
template's field-spec with no extra LLM call.

The adapter only fills fields it can source from a generated post (title / body /
image). Templates that *require* richer fields (stats, steps, sides, lottie, …)
are filtered out here — generating those needs an LLM fill pass, a planned
follow-up. Selection is structural, not semantic; semantic fit is the job of the
later vector-rank / LLM-fill stage.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# --- field-spec mirror (the subset the selector/adapter needs) --------------


@dataclass
class TemplateField:
    name: str
    type: str
    required: bool = False
    max: Optional[int] = None
    min: Optional[int] = None
    asset: Optional[str] = None          # asset kind when type == "asset"
    values: Optional[list[str]] = None   # allowed values when type == "enum"
    of: Optional[list["TemplateField"]] = None   # list of objects: sub-fields
    item: Optional["TemplateField"] = None       # list of scalars: item shape


def _field_from_dict(f: dict) -> TemplateField:
    return TemplateField(
        name=f.get("name", ""),
        type=f.get("type", "text"),
        required=bool(f.get("required", False)),
        max=f.get("max"),
        min=f.get("min"),
        asset=f.get("asset"),
        values=f.get("values"),
        of=[_field_from_dict(s) for s in f["of"]] if f.get("of") else None,
        item=_field_from_dict(f["item"]) if f.get("item") else None,
    )


@dataclass
class TemplateSpec:
    template_id: str
    vibe: str
    content_types: list[str]
    fields: list[TemplateField]
    version: int = 1
    name: str = ""

    @classmethod
    def from_row(cls, row: dict) -> "TemplateSpec":
        return cls(
            template_id=row["template_id"],
            vibe=row.get("vibe", "calm"),
            content_types=row.get("content_types") or [],
            fields=[_field_from_dict(f) for f in (row.get("fields") or [])],
            version=row.get("version", 1),
            name=row.get("name", ""),
        )

    @property
    def required_fields(self) -> set[str]:
        return {f.name for f in self.fields if f.required}

    def get(self, name: str) -> Optional[TemplateField]:
        return next((f for f in self.fields if f.name == name), None)


def specs_from_rows(rows: list[dict]) -> list[TemplateSpec]:
    return [TemplateSpec.from_row(r) for r in rows]


# --- deterministic RNG (matches the asset generators' LCG) -------------------


def _hash(s: str) -> int:
    h = 2166136261
    for ch in s:
        h ^= ord(ch)
        h = (h * 16777619) & 0xFFFFFFFF
    return h


class _Rng:
    def __init__(self, seed: int):
        self.s = (seed & 0xFFFFFFFF) or 0x9E3779B9

    def next(self) -> float:
        self.s = (self.s * 1664525 + 1013904223) & 0xFFFFFFFF
        return self.s / 0x100000000


# --- selection ---------------------------------------------------------------

# Field names the deterministic adapter fills straight from a generated post.
_DETERMINISTIC = {"title", "body", "images"}


def available_fields(*, has_body: bool, has_image: bool) -> set[str]:
    names = {"title"}  # every post has a title
    if has_body:
        names.add("body")
    if has_image:
        names.add("images")
    return names


def _satisfiable(field: TemplateField, available: set[str], can_fill: bool) -> bool:
    """Can we produce a value for this field?

    Deterministic fields (title/body/image) are always fine. With an LLM fill
    pass, any text/number/enum/list field is fillable too — but asset fields
    (lottie/svg) need a real asset we can't synthesize, so they're never
    satisfiable unless deterministically available (an image we generated).
    """
    if field.name in available:
        return True
    if field.type == "asset":
        return False
    return can_fill


def needs_fill(spec: TemplateSpec) -> bool:
    """True if the template requires content the deterministic adapter can't
    supply — i.e. an LLM fill pass is needed before rendering."""
    return any(f.required and f.name not in _DETERMINISTIC for f in spec.fields)


# Per-level vibe preference: summaries punchy, deep dives calm/structured.
_LEVEL_VIBE = {
    1: {"energetic": 1.0, "playful": 0.8, "structured": 0.3, "calm": 0.2},
    2: {"structured": 0.8, "energetic": 0.6, "calm": 0.6, "playful": 0.6},
    3: {"calm": 1.0, "structured": 0.9, "energetic": 0.2, "playful": 0.2},
}
# Intended body size per level (chars) — drives capacity fit.
_TARGET_CHARS = {1: 200, 2: 500, 3: 1100}


def _capacity_fit(spec: TemplateSpec, target_chars: int) -> float:
    body = spec.get("body")
    if body is None or body.max is None:
        return 0.5  # no body field — neutral
    if body.max >= target_chars:
        return 1.0
    return max(0.0, body.max / target_chars)


def _score(spec: TemplateSpec, level: int, target: int, recent: list[str]) -> float:
    s = 1.5 * _LEVEL_VIBE.get(level, {}).get(spec.vibe, 0.4)
    s += 1.0 * _capacity_fit(spec, target)
    s -= 0.6 * (1.0 if spec.template_id in recent else 0.0)
    return s


def _weighted_pick(items: list[TemplateSpec], weights: list[float], rng: _Rng) -> TemplateSpec:
    total = sum(weights)
    if total <= 0:
        return items[0]
    r = rng.next() * total
    acc = 0.0
    for it, w in zip(items, weights):
        acc += w
        if r <= acc:
            return it
    return items[-1]


def select_template(
    *,
    content_type: str,
    level: int,
    body_len: int,
    has_image: bool,
    catalog: list[TemplateSpec],
    recent: Optional[list[str]] = None,
    post_id: str,
    can_fill: bool = False,
    top_k: int = 4,
) -> Optional[TemplateSpec]:
    """Pick a template for a post, or None if nothing eligible.

    Hard filter: content_type compatible AND every required field is satisfiable
    (deterministically, or via the LLM fill pass when ``can_fill``). Soft rank:
    level→vibe + capacity fit, minus a recency penalty. Then a seeded (post_id)
    weighted pick over the top-K for reproducible variety.
    """
    recent = recent or []
    avail = available_fields(has_body=body_len > 0, has_image=has_image)
    cands = [
        t for t in catalog
        if content_type in t.content_types
        and all(_satisfiable(f, avail, can_fill) for f in t.fields if f.required)
    ]
    if not cands:
        return None

    target = _TARGET_CHARS.get(level, 500)
    # Sort by score desc, then template_id for a stable tie-break.
    ranked = sorted(cands, key=lambda t: (-_score(t, level, target, recent), t.template_id))
    top = ranked[: min(top_k, len(ranked))]
    weights = [max(0.01, _score(t, level, target, recent)) for t in top]
    return _weighted_pick(top, weights, _Rng(_hash(post_id)))


# --- input adaptation --------------------------------------------------------


def _clip(text: str, max_len: Optional[int]) -> str:
    if not max_len or len(text) <= max_len:
        return text
    slice_ = text[: max_len - 1]
    cut = slice_.rfind(" ")
    base = slice_[:cut] if cut > max_len * 0.6 else slice_
    return base.rstrip() + "…"


def build_inputs(
    spec: TemplateSpec,
    *,
    title: str,
    body: str = "",
    image_url: Optional[str] = None,
) -> dict:
    """Map generated post content onto the template's field-spec. Only fills
    fields it can source; optional fields it can't fill are left unset (the
    engine renders without them)."""
    out: dict = {}
    for f in spec.fields:
        if f.name == "title":
            out["title"] = _clip(title, f.max)
        elif f.name == "body" and body:
            out["body"] = _clip(body, f.max)
        elif f.name == "images" and image_url:
            out["images"] = [{"url": image_url, "alt": _clip(title, 120)}]
    return out


# --- validation (mirrors the web engine's validate.ts) -----------------------


def _clamp(field: TemplateField, value):
    if value is None:
        return None
    t = field.type
    if t in ("text", "rich", "color"):
        s = str(value)
        return _clip(s, field.max) if field.max else s
    if t == "number":
        try:
            n = float(value)
        except (TypeError, ValueError):
            return None
        if field.min is not None:
            n = max(field.min, n)
        if field.max is not None:
            n = min(field.max, n)
        return int(n) if n == int(n) else n
    if t == "enum":
        s = str(value)
        if field.values and s not in field.values:
            return field.values[0]
        return s
    if t == "list":
        if not isinstance(value, list):
            return []
        arr = value[: field.max] if field.max else value
        out = []
        for item in arr:
            if field.of:
                obj = item if isinstance(item, dict) else {}
                out.append({sub.name: _clamp(sub, obj.get(sub.name)) for sub in field.of})
            elif field.item:
                out.append(_clamp(field.item, item))
            else:
                out.append(item)
        return out
    return value  # asset references pass through


def validate_inputs(spec: TemplateSpec, raw: dict) -> dict:
    """Clamp raw (e.g. LLM-produced) inputs to the field-spec and drop any keys
    the template doesn't declare. Length/count limits come from the spec."""
    return {f.name: _clamp(f, raw[f.name]) for f in spec.fields if f.name in raw}


# --- field-spec description (the schema the LLM fills) -----------------------


def _type_hint(field: TemplateField) -> str:
    if field.type in ("text", "rich"):
        return f"text ≤{field.max} chars" if field.max else "text"
    if field.type == "number":
        return "number"
    if field.type == "enum" and field.values:
        return "one of: " + ", ".join(field.values)
    if field.type == "color":
        return "hex color"
    return field.type


def _describe(field: TemplateField) -> str:
    req = " (required)" if field.required else ""
    if field.type == "list":
        count = f"{field.min or 0}–{field.max or 'several'}"
        if field.of:
            shape = ", ".join(f"{s.name}: {_type_hint(s)}" for s in field.of)
            return f"- {field.name}: array of {count} objects, each {{ {shape} }}{req}"
        item_hint = _type_hint(field.item) if field.item else "short text"
        return f"- {field.name}: array of {count} {item_hint}{req}"
    return f"- {field.name}: {_type_hint(field)}{req}"


def describe_fields(spec: TemplateSpec) -> str:
    """Render the content fields as a compact schema for the fill prompt. Skips
    asset fields (images/svg/lottie) and the accent override — those aren't
    LLM-generated."""
    lines = [
        _describe(f)
        for f in spec.fields
        if f.type != "asset" and f.name != "accentColor"
    ]
    return "\n".join(lines)
