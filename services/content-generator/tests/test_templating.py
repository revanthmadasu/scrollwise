"""Template selection + adaptation, and the posts/templates persistence round-trip."""
import json
import tempfile
import uuid
from pathlib import Path

import pytest

from generators.models import ContentType, Level, Post
from generators.template_fill import TemplateFiller
from generators.templating import (
    TemplateField,
    TemplateSpec,
    build_inputs,
    describe_fields,
    needs_fill,
    select_template,
    specs_from_rows,
    validate_inputs,
)
from storage.repository import Repository
from tests.fakes import FakeLLMClient, fill_responder


def spec(tid, vibe, ctypes, fields):
    return TemplateSpec(
        template_id=tid, vibe=vibe, content_types=ctypes,
        fields=[TemplateField(**f) for f in fields],
    )


CATALOG = [
    spec("plain", "calm", ["text"], [{"name": "title", "type": "text", "required": True}, {"name": "body", "type": "rich", "max": 300}]),
    spec("cover", "energetic", ["text", "image_post"], [{"name": "title", "type": "text", "required": True, "max": 60}]),
    spec("stats", "structured", ["text"], [{"name": "title", "type": "text", "required": True}, {"name": "stats", "type": "list", "required": True}]),
    spec("photo", "energetic", ["image_post"], [{"name": "title", "type": "text", "required": True}, {"name": "images", "type": "list"}]),
    spec("deep", "calm", ["text"], [{"name": "title", "type": "text", "required": True}, {"name": "body", "type": "rich", "max": 2000}]),
]


# --- selection --------------------------------------------------------------

def test_filters_by_content_type():
    chosen = select_template(content_type="image_post", level=1, body_len=120,
                             has_image=True, catalog=CATALOG, post_id="p1")
    # Only `cover` and `photo` accept image_post.
    assert chosen.template_id in {"cover", "photo"}


def test_required_field_infeasible_excludes_template():
    # `stats` requires a stats field we can't fill — never selected, over many seeds.
    picks = {
        select_template(content_type="text", level=2, body_len=400, has_image=False,
                        catalog=CATALOG, post_id=f"p{i}").template_id
        for i in range(50)
    }
    assert "stats" not in picks


def test_none_when_no_eligible():
    assert select_template(content_type="video", level=1, body_len=100,
                           has_image=False, catalog=CATALOG, post_id="p") is None


def test_deterministic_for_same_post():
    a = select_template(content_type="text", level=3, body_len=1000, has_image=False, catalog=CATALOG, post_id="same")
    b = select_template(content_type="text", level=3, body_len=1000, has_image=False, catalog=CATALOG, post_id="same")
    assert a.template_id == b.template_id


def test_recency_penalised():
    # Two templates with identical score, so the recency penalty is decisive.
    twin = [
        spec("a", "calm", ["text"], [{"name": "title", "type": "text", "required": True}, {"name": "body", "type": "rich", "max": 2000}]),
        spec("b", "calm", ["text"], [{"name": "title", "type": "text", "required": True}, {"name": "body", "type": "rich", "max": 2000}]),
    ]
    # top_k=1 makes the pick the top-ranked candidate. With 'a' recent, 'b' wins.
    chosen = select_template(content_type="text", level=3, body_len=1500, has_image=False,
                             catalog=twin, recent=["a"], post_id="x", top_k=1)
    assert chosen.template_id == "b"


def test_capacity_fit_prefers_high_capacity_for_deep():
    # A deep post (long target) should rank the high-capacity `deep` over `plain`.
    chosen = select_template(content_type="text", level=3, body_len=1500, has_image=False,
                             catalog=CATALOG, post_id="deepish", top_k=1)
    assert chosen.template_id == "deep"


# --- adaptation -------------------------------------------------------------

def test_build_inputs_maps_and_clips():
    s = spec("t", "calm", ["text"], [{"name": "title", "type": "text", "max": 10}, {"name": "body", "type": "rich", "max": 20}])
    out = build_inputs(s, title="A very long title indeed", body="Short body here.")
    assert out["title"].endswith("…") and len(out["title"]) <= 10
    assert out["body"] == "Short body here."


def test_build_inputs_image_only_when_present_and_wanted():
    s = spec("t", "calm", ["image_post"], [{"name": "title", "type": "text"}, {"name": "images", "type": "list"}])
    with_img = build_inputs(s, title="T", image_url="http://x/y.png")
    assert with_img["images"][0]["url"] == "http://x/y.png"
    assert "images" not in build_inputs(s, title="T")  # no url → not filled


def test_build_inputs_skips_unfillable_fields():
    s = spec("t", "calm", ["text"], [{"name": "title", "type": "text"}, {"name": "stats", "type": "list"}])
    out = build_inputs(s, title="T", body="B")
    assert "stats" not in out


# --- persistence ------------------------------------------------------------

@pytest.fixture
def repo():
    with tempfile.TemporaryDirectory() as tmp:
        r = Repository(str(Path(tmp) / "t.db"))
        yield r
        r.close()


def _post(**kw):
    base = dict(
        post_id=str(uuid.uuid4()), topic_id="t", module_id="m", subtopic_id="s",
        offset_module=0, offset_subtopic=0, offset_seq=2, level=Level.STANDARD,
        content_type=ContentType.TEXT, title="A title", body="A body",
    )
    base.update(kw)
    return Post(**base)


def test_post_template_round_trip(repo):
    repo.save_post(_post(template_id="cover", template_inputs={"title": "Hi", "body": "x"}))
    got = repo.list_posts("t")[0]
    assert got.template_id == "cover"
    assert got.template_inputs == {"title": "Hi", "body": "x"}


def test_post_without_template_defaults(repo):
    repo.save_post(_post())
    got = repo.list_posts("t")[0]
    assert got.template_id is None
    assert got.template_inputs == {}


def test_list_approved_templates_filters_and_parses(repo):
    repo._execute(
        "CREATE TABLE templates (template_id TEXT, name TEXT, vibe TEXT, status TEXT, "
        "version INTEGER, compatible_content_types TEXT, fields TEXT)"
    )
    repo._execute(
        "INSERT INTO templates VALUES (?,?,?,?,?,?,?)",
        ("cover", "Cover", "energetic", "approved", 2, json.dumps(["text"]),
         json.dumps([{"name": "title", "type": "text", "required": True}])),
    )
    repo._execute(
        "INSERT INTO templates VALUES (?,?,?,?,?,?,?)",
        ("draft1", "Draft", "calm", "draft", 1, json.dumps(["text"]), json.dumps([])),
    )
    repo._commit()

    rows = repo.list_approved_templates()
    assert [r["template_id"] for r in rows] == ["cover"]
    specs = specs_from_rows(rows)
    assert specs[0].content_types == ["text"]
    assert specs[0].required_fields == {"title"}


def test_list_approved_templates_missing_table_is_empty(repo):
    # Fresh generator DB never had the API-owned templates table.
    assert repo.list_approved_templates() == []


# --- LLM fill pass ----------------------------------------------------------

STATS_ROW = {
    "template_id": "infographic", "vibe": "structured", "content_types": ["text"], "version": 1,
    "fields": [
        {"name": "title", "type": "text", "required": True, "max": 70},
        {"name": "stats", "type": "list", "required": True, "min": 1, "max": 3, "of": [
            {"name": "label", "type": "text", "max": 24, "required": True},
            {"name": "value", "type": "text", "max": 12, "required": True},
            {"name": "unit", "type": "text", "max": 8},
        ]},
    ],
}
LOTTIE_ROW = {
    "template_id": "lottie", "vibe": "playful", "content_types": ["text"], "version": 1,
    "fields": [
        {"name": "title", "type": "text", "required": True},
        {"name": "lottie", "type": "asset", "asset": "lottie", "required": True},
    ],
}


def test_needs_fill():
    assert needs_fill(TemplateSpec.from_row(STATS_ROW)) is True
    plain = TemplateSpec.from_row({"template_id": "p", "content_types": ["text"],
                                   "fields": [{"name": "title", "type": "text", "required": True},
                                              {"name": "body", "type": "rich"}]})
    assert needs_fill(plain) is False


def test_can_fill_expands_eligibility():
    cat = [TemplateSpec.from_row(STATS_ROW)]
    # Without a fill pass the stats template is infeasible…
    assert select_template(content_type="text", level=2, body_len=400, has_image=False,
                           catalog=cat, post_id="p", can_fill=False) is None
    # …but with one it becomes selectable.
    chosen = select_template(content_type="text", level=2, body_len=400, has_image=False,
                             catalog=cat, post_id="p", can_fill=True)
    assert chosen.template_id == "infographic"


def test_asset_required_never_eligible_even_with_fill():
    cat = [TemplateSpec.from_row(LOTTIE_ROW)]
    # A required lottie asset can't be synthesized, fill or not.
    assert select_template(content_type="text", level=1, body_len=100, has_image=False,
                           catalog=cat, post_id="p", can_fill=True) is None


def test_validate_inputs_clamps_and_drops():
    s = TemplateSpec.from_row(STATS_ROW)
    raw = {
        "title": "x" * 100,                       # over 70 → clipped
        "stats": [{"label": "L" * 40, "value": "12345678901234", "unit": "kg"}] * 5,  # 5 → 3 items, label/value clipped
        "junk": "ignored",                        # not in spec → dropped
    }
    out = validate_inputs(s, raw)
    assert "junk" not in out
    assert len(out["title"]) <= 70
    assert len(out["stats"]) == 3
    assert len(out["stats"][0]["label"]) <= 24
    assert len(out["stats"][0]["value"]) <= 12


def test_describe_fields_lists_structure():
    desc = describe_fields(TemplateSpec.from_row(STATS_ROW))
    assert "stats:" in desc and "label" in desc and "value" in desc


def test_filler_produces_validated_inputs():
    filler = TemplateFiller(FakeLLMClient(fill_responder))
    out = filler.fill(TemplateSpec.from_row(STATS_ROW), title="T", body="Some content with figures.")
    assert "stats" in out and len(out["stats"]) >= 1
    assert out["stats"][0]["label"] and out["stats"][0]["value"]
    # Keys outside the field-spec (the responder's kitchen sink) are dropped.
    assert set(out.keys()) <= {"title", "stats"}
