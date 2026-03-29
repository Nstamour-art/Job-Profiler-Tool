"""
Interactive template selection wizard.

Presents four named themes, accepts optional natural language customization via
parser_model, confirms with the user, and writes template.yaml.
"""
from __future__ import annotations

import yaml

from src.themes import ThemeConfig, TemplateOverrides, PRESETS, merge_overrides
from src.llm import _call_with_retry
from src.prompts import TEMPLATE_EXTRACT_OVERRIDES
from src.providers import get_provider, resolve_models


_MENU = """\

Choose a resume template:

  1. Classic   — Arial, black on white, centered headings with ruled borders
  2. Modern    — Calibri, navy accent, left-aligned name, underlined headings
  3. Creative  — Georgia serif, dark sidebar layout  (\u26a0  some ATS may misread columns)
  4. Minimal   — Helvetica Neue, no borders, grey section labels, generous margins

Enter 1\u20134: """

_THEME_NAMES = ["classic", "modern", "creative", "minimal"]


def _extract_overrides(
    theme_name: str,
    raw: str,
    provider,
    parser_models: list[str],
    llm_cfg: dict,
) -> TemplateOverrides:
    system = TEMPLATE_EXTRACT_OVERRIDES.format(theme=theme_name)
    prompt = f'User customization request: "{raw}"\n\nExtract any font name, font size, or color preferences from the above request and return the JSON object.'
    return _call_with_retry(TemplateOverrides, provider, llm_cfg, system, prompt, parser_models)


def _format_confirmation(theme: ThemeConfig, customizations: list[str]) -> str:
    r, g, b = theme.accent_color
    heading_style = (
        "Left-aligned, underlined" if theme.heading_underline
        else "Centered, ruled" if theme.heading_rule
        else "Plain labels"
    )
    lines = [
        "\nHere's your template configuration:\n",
        f"  Theme:       {theme.name.capitalize()}",
        f"  Font:        {theme.font}, {theme.body_pt}pt body",
        f"  Accent:      [{r}, {g}, {b}]",
        f"  Headings:    {heading_style}",
        f"  Margins:     {theme.margin_top}\" top/bottom, {theme.margin_left}\" left/right",
    ]
    if customizations:
        lines.append(f"\n  Customizations: {'; '.join(customizations)}")
    lines.append("\nDoes this look right? (yes / edit / skip)\n> ")
    return "\n".join(lines)


def run_template_wizard(config: dict, provider_name: str) -> ThemeConfig:
    """Present theme menu, extract optional overrides, confirm, write template.yaml."""
    provider = get_provider(provider_name, config["llm"])
    _, parser_models = resolve_models(provider_name, config["llm"])
    llm_cfg = config["llm"]
    template_path = config.get("paths", {}).get("template_yaml", "template.yaml")

    # Show current template if file already exists
    try:
        with open(template_path, encoding="utf-8") as f:
            current = ThemeConfig.model_validate(yaml.safe_load(f))
        print(f"\nCurrent template: {current.name.capitalize()}")
    except FileNotFoundError:
        pass

    # Theme selection
    while True:
        choice = input(_MENU).strip()
        if choice in ("1", "2", "3", "4"):
            theme_name = _THEME_NAMES[int(choice) - 1]
            if theme_name == "creative":
                print("\n  \u26a0  Creative uses a two-column sidebar. Some older ATS systems")
                print("     may read columns left-to-right and interleave content.\n")
            break
        print("  Please enter 1, 2, 3, or 4.")

    base = PRESETS[theme_name]
    customizations: list[str] = []

    # Optional customization
    raw_custom = input(
        "\nAnything to customize? (font name, size, accent color — or press Enter for defaults)\n> "
    ).strip()

    raw_accent_color: str = ""
    if raw_custom:
        try:
            overrides = _extract_overrides(theme_name, raw_custom, provider, parser_models, llm_cfg)
            raw_accent_color = overrides.accent_color or ""
            base = merge_overrides(base, overrides)
            if overrides.font:
                customizations.append(f"font: {overrides.font}")
            if overrides.body_pt is not None:
                customizations.append(f"body {overrides.body_pt}pt")
            if overrides.heading_pt is not None:
                customizations.append(f"headings {overrides.heading_pt}pt")
            if overrides.accent_color:
                customizations.append(f"accent: {overrides.accent_color}")
        except Exception as exc:
            print(f"  Could not extract customization ({exc}). Using base theme defaults.\n")

    # Confirmation loop
    original_raw = raw_custom
    while True:
        response = input(_format_confirmation(base, customizations)).strip().lower()
        if response == "yes":
            break
        elif response == "skip":
            base = PRESETS[theme_name]
            raw_accent_color = ""
            customizations = []
            break
        elif response == "edit":
            correction = input("What would you like to change?\n> ").strip()
            combined = (
                f"Original input: {original_raw}\n"
                f"User correction: {correction}\n"
                "Apply the correction and return updated JSON."
            )
            try:
                overrides = _extract_overrides(theme_name, combined, provider, parser_models, llm_cfg)
                raw_accent_color = overrides.accent_color or ""
                base = merge_overrides(PRESETS[theme_name], overrides)
                customizations = []
                if overrides.font:
                    customizations.append(f"font: {overrides.font}")
                if overrides.body_pt is not None:
                    customizations.append(f"body {overrides.body_pt}pt")
                if overrides.heading_pt is not None:
                    customizations.append(f"headings {overrides.heading_pt}pt")
                if overrides.accent_color:
                    customizations.append(f"accent: {overrides.accent_color}")
                original_raw = combined
            except Exception as exc:
                print(f"  Re-extraction failed ({exc}). Keeping previous result.\n")
        else:
            print("  Please type 'yes', 'edit', or 'skip'.")

    # Write template.yaml — store only the overrides that differ from base preset
    base_preset = PRESETS[theme_name]
    saved_overrides: dict = {}
    if base.font != base_preset.font:
        saved_overrides["font"] = base.font
    if base.body_pt != base_preset.body_pt:
        saved_overrides["body_pt"] = base.body_pt
    if base.heading_pt != base_preset.heading_pt:
        saved_overrides["heading_pt"] = base.heading_pt
    if raw_accent_color:
        saved_overrides["accent_color"] = raw_accent_color

    with open(template_path, "w", encoding="utf-8") as f:
        yaml.dump({"theme": base.name, "overrides": saved_overrides}, f, allow_unicode=True)

    print(f"\nTemplate saved. Using {base.name.capitalize()} for your documents.\n")
    return base
