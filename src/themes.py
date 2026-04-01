"""
Resume theme system.

ThemeConfig holds all styling parameters. Four named presets are available.
merge_overrides applies user-specified field changes on top of a base theme.
resolve_color maps English color names to RGB lists.
"""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field, field_validator


class ThemeConfig(BaseModel):
    """Complete styling configuration for a resume (colors, fonts, layout, margins)."""
    name: str = "classic"
    layout: str = "standard"          # "standard" | "sidebar"
    font: str = "Arial"
    body_pt: float = 10.0
    heading_pt: float = 12.0
    name_pt: float = 14.0
    accent_color: list[int] = Field(default_factory=lambda: [0, 0, 0])
    sidebar_color: list[int] = Field(default_factory=lambda: [45, 45, 45])
    margin_top: float = 0.6
    margin_bottom: float = 0.6
    margin_left: float = 0.75
    margin_right: float = 0.75
    heading_rule: bool = True
    heading_underline: bool = False
    name_align: str = "center"         # "center" | "left"

    @field_validator("accent_color", "sidebar_color")
    @classmethod
    def _validate_rgb(cls, v: list[int]) -> list[int]:
        if len(v) != 3 or not all(0 <= c <= 255 for c in v):
            raise ValueError(f"RGB must be a list of 3 integers in [0, 255], got {v}")
        return v


class TemplateOverrides(BaseModel):
    """Fields extracted from natural language. None/empty means not mentioned."""
    font: str = ""
    body_pt: Optional[float] = None
    heading_pt: Optional[float] = None
    name_pt: Optional[float] = None
    accent_color: str = ""             # English color name, resolved to RGB after extraction


CLASSIC = ThemeConfig(name="classic")

MODERN = ThemeConfig(
    name="modern",
    layout="standard",
    font="Calibri",
    body_pt=10.5,
    heading_pt=11.0,
    name_pt=18.0,
    accent_color=[26, 58, 92],
    margin_top=1.0,
    margin_bottom=1.0,
    margin_left=1.0,
    margin_right=1.0,
    heading_rule=False,
    heading_underline=True,
    name_align="left",
)

CREATIVE = ThemeConfig(
    name="creative",
    layout="sidebar",
    font="Georgia",
    body_pt=10.0,
    heading_pt=10.5,
    name_pt=13.0,
    accent_color=[45, 45, 45],
    sidebar_color=[45, 45, 45],
    margin_top=0.5,
    margin_bottom=0.5,
    margin_left=0.0,
    margin_right=0.5,
    heading_rule=False,
    heading_underline=True,
    name_align="left",
)

MINIMAL = ThemeConfig(
    name="minimal",
    layout="standard",
    font="Helvetica Neue",
    body_pt=10.0,
    heading_pt=9.0,
    name_pt=20.0,
    accent_color=[170, 170, 170],
    margin_top=1.15,
    margin_bottom=1.15,
    margin_left=1.15,
    margin_right=1.15,
    heading_rule=False,
    heading_underline=False,
    name_align="left",
)

PRESETS: dict[str, ThemeConfig] = {
    "classic": CLASSIC,
    "modern": MODERN,
    "creative": CREATIVE,
    "minimal": MINIMAL,
}

_COLOR_MAP: dict[str, list[int]] = {
    "black": [0, 0, 0],
    "navy": [26, 58, 92],
    "dark blue": [0, 0, 139],
    "blue": [0, 82, 204],
    "dark green": [0, 100, 0],
    "green": [34, 139, 34],
    "teal": [0, 128, 128],
    "dark red": [139, 0, 0],
    "red": [200, 0, 0],
    "burgundy": [128, 0, 32],
    "purple": [128, 0, 128],
    "dark purple": [75, 0, 130],
    "grey": [100, 100, 100],
    "gray": [100, 100, 100],
    "dark grey": [64, 64, 64],
    "charcoal": [54, 54, 54],
}


def resolve_color(name: str, fallback: list[int]) -> list[int]:
    """Map an English color name to an RGB list. Returns fallback if unknown."""
    return _COLOR_MAP.get(name.lower().strip(), fallback)


def merge_overrides(base: ThemeConfig, overrides: TemplateOverrides) -> ThemeConfig:
    """Apply non-empty override fields on top of base theme. Returns a new ThemeConfig."""
    data = base.model_dump()
    if overrides.font:
        data["font"] = overrides.font
    if overrides.body_pt is not None:
        data["body_pt"] = overrides.body_pt
    if overrides.heading_pt is not None:
        data["heading_pt"] = overrides.heading_pt
    if overrides.name_pt is not None:
        data["name_pt"] = overrides.name_pt
    if overrides.accent_color:
        data["accent_color"] = resolve_color(overrides.accent_color, base.accent_color)
    return ThemeConfig(**data)
