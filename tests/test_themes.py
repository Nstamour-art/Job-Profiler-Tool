import pytest
from src.themes import (
    ThemeConfig, TemplateOverrides,
    CLASSIC, MODERN, CREATIVE, MINIMAL, PRESETS,
    merge_overrides, resolve_color,
)


def test_classic_preset_defaults():
    assert CLASSIC.name == "classic"
    assert CLASSIC.layout == "standard"
    assert CLASSIC.font == "Arial"
    assert CLASSIC.body_pt == 10.0
    assert CLASSIC.heading_rule is True
    assert CLASSIC.heading_underline is False
    assert CLASSIC.name_align == "center"


def test_modern_preset():
    assert MODERN.name == "modern"
    assert MODERN.font == "Calibri"
    assert MODERN.accent_color == [26, 58, 92]
    assert MODERN.heading_underline is True
    assert MODERN.name_align == "left"


def test_creative_preset_sidebar():
    assert CREATIVE.layout == "sidebar"
    assert CREATIVE.font == "Georgia"


def test_minimal_preset():
    assert MINIMAL.name == "minimal"
    assert MINIMAL.heading_rule is False
    assert MINIMAL.heading_underline is False


def test_presets_dict_has_all_four():
    assert set(PRESETS.keys()) == {"classic", "modern", "creative", "minimal"}


def test_merge_overrides_applies_body_pt():
    overrides = TemplateOverrides(body_pt=12.0)
    result = merge_overrides(MODERN, overrides)
    assert result.body_pt == 12.0
    assert result.font == MODERN.font  # unchanged


def test_merge_overrides_applies_font():
    overrides = TemplateOverrides(font="Times New Roman")
    result = merge_overrides(CLASSIC, overrides)
    assert result.font == "Times New Roman"
    assert result.body_pt == CLASSIC.body_pt  # unchanged


def test_merge_overrides_applies_accent_color_by_name():
    overrides = TemplateOverrides(accent_color="dark green")
    result = merge_overrides(CLASSIC, overrides)
    assert result.accent_color == [0, 100, 0]


def test_merge_overrides_skips_none_body_pt():
    overrides = TemplateOverrides(body_pt=None)
    result = merge_overrides(MODERN, overrides)
    assert result.body_pt == MODERN.body_pt


def test_merge_overrides_skips_empty_font():
    overrides = TemplateOverrides(font="")
    result = merge_overrides(CLASSIC, overrides)
    assert result.font == CLASSIC.font


def test_resolve_color_known():
    assert resolve_color("navy", [0, 0, 0]) == [26, 58, 92]
    assert resolve_color("dark green", [0, 0, 0]) == [0, 100, 0]
    assert resolve_color("burgundy", [0, 0, 0]) == [128, 0, 32]


def test_resolve_color_unknown_returns_fallback():
    assert resolve_color("electric chartreuse", [1, 2, 3]) == [1, 2, 3]


def test_resolve_color_case_insensitive():
    assert resolve_color("Navy", [0, 0, 0]) == [26, 58, 92]
    assert resolve_color("DARK GREEN", [0, 0, 0]) == [0, 100, 0]


def test_theme_config_model_validate_from_dict():
    raw = {"name": "modern", "font": "Calibri", "body_pt": 11.0}
    theme = ThemeConfig.model_validate({**MODERN.model_dump(), **raw})
    assert theme.name == "modern"
    assert theme.body_pt == 11.0


def test_template_overrides_all_defaults_empty():
    o = TemplateOverrides()
    assert o.font == ""
    assert o.body_pt is None
    assert o.accent_color == ""


def test_merge_overrides_unknown_accent_color_falls_back_to_base():
    overrides = TemplateOverrides(accent_color="electric chartreuse")
    result = merge_overrides(MODERN, overrides)
    assert result.accent_color == MODERN.accent_color


def test_theme_config_rejects_invalid_rgb():
    with pytest.raises(Exception):
        ThemeConfig(accent_color=[300, 0, 0])
