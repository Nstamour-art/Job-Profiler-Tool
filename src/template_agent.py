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
    prompt = (
        f'User customization request: "{raw}"\n\n'
        "Extract any font name, font size, or color preferences from the above request "
        "and return the JSON object."
    )
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


def _select_theme_interactively(template_path: str) -> str:
    """Prompt the user for a theme and return its name."""
    try:
        with open(template_path, encoding="utf-8") as f:
            current = ThemeConfig.model_validate(yaml.safe_load(f))
        print(f"\nCurrent template: {current.name.capitalize()}")
    except (FileNotFoundError, yaml.YAMLError, ValueError):
        pass

    while True:
        choice = input(_MENU).strip()
        if choice in ("1", "2", "3", "4"):
            name = _THEME_NAMES[int(choice) - 1]
            if name == "creative":
                print("\n  \u26a0  Creative uses a two-column sidebar. Some older ATS systems")
                print("     may read columns left-to-right and interleave content.\n")
            return name
        print("  Please enter 1, 2, 3, or 4.")


def _apply_initial_customization(
    theme_name: str,
    provider,
    parser_models: list[str],
    llm_cfg: dict,
) -> tuple[ThemeConfig, list[str], str, TemplateOverrides | None]:
    """Get initial user request and apply overrides."""
    base = PRESETS[theme_name]
    customizations: list[str] = []

    raw = input(
        "\nAnything to customize? "
        "(font name, size, accent color — or press Enter for defaults)\n> "
    ).strip()

    if raw:
        try:
            overrides = _extract_overrides(theme_name, raw, provider, parser_models, llm_cfg)
            base = merge_overrides(base, overrides)
            if overrides.font:
                customizations.append(f"font: {overrides.font}")
            if overrides.body_pt is not None:
                customizations.append(f"body {overrides.body_pt}pt")
            if overrides.heading_pt is not None:
                customizations.append(f"headings {overrides.heading_pt}pt")
            if overrides.accent_color:
                customizations.append(f"accent: {overrides.accent_color}")
            return base, customizations, raw, overrides
        except Exception as exc:
            print(f"  Could not extract customization ({exc}). Using base theme defaults.\n")

    return base, customizations, raw, None


def _handle_edit_flow(
    theme_name: str,
    original_raw: str,
    provider,
    parser_models: list[str],
    llm_cfg: dict,
) -> tuple[ThemeConfig | None, list[str] | None, str, TemplateOverrides | None]:
    """Process a user correction/edit request."""
    correction = input("What would you like to change?\n> ").strip()
    combined = (
        f"Original input: {original_raw}\n"
        f"User correction: {correction}\n"
        "Apply the correction and return updated JSON."
    )
    try:
        overrides = _extract_overrides(theme_name, combined, provider, parser_models, llm_cfg)
        base = merge_overrides(PRESETS[theme_name], overrides)
        customs = []
        if overrides.font:
            customs.append(f"font: {overrides.font}")
        if overrides.body_pt is not None:
            customs.append(f"body {overrides.body_pt}pt")
        if overrides.heading_pt is not None:
            customs.append(f"headings {overrides.heading_pt}pt")
        if overrides.accent_color:
            customs.append(f"accent: {overrides.accent_color}")
        return base, customs, combined, overrides
    except Exception as exc:  # pylint: disable=broad-exception-caught
        print(f"  Re-extraction failed ({exc}). Keeping previous result.\n")
        return None, None, original_raw, None


def run_template_wizard(config: dict, provider_name: str) -> ThemeConfig:
    """Present theme menu, extract optional overrides, confirm, write template.yaml."""
    provider = get_provider(provider_name, config["llm"])
    _, parser_models = resolve_models(provider_name, config["llm"])
    llm_cfg = config["llm"]
    template_path = config.get("paths", {}).get("template_yaml", "template.yaml")

    theme_name = _select_theme_interactively(template_path)
    base, customizations, original_raw, current_overrides = _apply_initial_customization(
        theme_name, provider, parser_models, llm_cfg
    )

    while True:
        response = input(_format_confirmation(base, customizations)).strip().lower()
        if response == "yes":
            break
        if response == "skip":
            base, customizations, current_overrides = PRESETS[theme_name], [], None
            break
        if response == "edit":
            new_base, new_customs, original_raw, new_overrides = _handle_edit_flow(
                theme_name, original_raw, provider, parser_models, llm_cfg
            )
            if new_base:
                base, customizations, current_overrides = new_base, new_customs, new_overrides
            continue
        print("  Please type 'yes', 'edit', or 'skip'.")

    # Write template.yaml — store the TemplateOverrides fields (English strings, not RGB)
    final_overrides = current_overrides.model_dump(exclude_defaults=True) if current_overrides else {}

    with open(template_path, "w", encoding="utf-8") as f:
        yaml.dump({"theme": base.name, "overrides": final_overrides}, f, allow_unicode=True)

    print(f"\nTemplate saved. Using {base.name.capitalize()} for your documents.\n")
    return base
