"""Pure, immutable UX-1A design tokens and colour helpers."""

from __future__ import annotations

import math
from types import MappingProxyType
from typing import Mapping


SURFACE_TOKENS: Mapping[str, str] = MappingProxyType({
    "surface.canvas": "#0e1117",
    "surface.panel": "#1a1f2b",
    "surface.elevated": "#232938",
})

TEXT_TOKENS: Mapping[str, str] = MappingProxyType({
    "text.primary": "#e6e9ef",
    "text.secondary": "#8b93a7",
    "text.disabled": "#8b93a7",
    "text.on-primary": "#ffffff",
})

BORDER_TOKENS: Mapping[str, str] = MappingProxyType({
    "border.default": "#394154",
    "border.focus": "#7fe3f0",
})

INTERACTIVE_TOKENS: Mapping[str, str] = MappingProxyType({
    "interactive.primary": "#2563eb",
    "interactive.hover": "#1d4ed8",
    "interactive.active": "#1e40af",
    "interactive.accent": "#60a5fa",
    "interactive.control": "#3b82f6",
    "interactive.disabled": "#6b7280",
})

FEEDBACK_TOKENS: Mapping[str, str] = MappingProxyType({
    "feedback.info": "#636efa",
    "feedback.success": "#00cc96",
    "feedback.warning": "#ffa15a",
    "feedback.error": "#ef553b",
})

SIGNAL_TOKENS: Mapping[str, str] = MappingProxyType({
    "signal.bullish": "#00cc96",
    "signal.neutral": "#ffa15a",
    "signal.bearish": "#ef553b",
    "signal.avoid": "#ef4444",
})

COLOR_TOKENS: Mapping[str, str] = MappingProxyType({
    **SURFACE_TOKENS,
    **TEXT_TOKENS,
    **BORDER_TOKENS,
    **INTERACTIVE_TOKENS,
    **FEEDBACK_TOKENS,
    **SIGNAL_TOKENS,
})


_THEME_SURFACES = ("canvas", "panel", "elevated")
_PRIMARY_BUTTON_SELECTOR = (
    ':where([data-testid="stButton"] button[kind="primary"], '
    '[data-testid="stFormSubmitButton"] button[kind="primaryFormSubmit"], '
    '[data-testid="stDownloadButton"] button[kind="primary"]):not(:disabled)'
    ':not([disabled]):not([aria-disabled="true"])'
)
_PRIMARY_BUTTON_CASES = ("primary", "form_submit", "download")
_LINK_BUTTON_SELECTOR = (
    '[data-testid="stLinkButton"] a[kind="primary"]:not([disabled])'
    ':not([aria-disabled="true"])'
)
_PRIMARY_ACTION_DISABLED_SELECTOR = (
    ':is([data-testid="stButton"] button[kind="primary"]:disabled, '
    '[data-testid="stButton"] button[kind="primary"][aria-disabled="true"], '
    '[data-testid="stFormSubmitButton"] button[kind="primaryFormSubmit"]:disabled, '
    '[data-testid="stFormSubmitButton"] '
    'button[kind="primaryFormSubmit"][aria-disabled="true"], '
    '[data-testid="stDownloadButton"] button[kind="primary"]:disabled, '
    '[data-testid="stDownloadButton"] '
    'button[kind="primary"][aria-disabled="true"], '
    '[data-testid="stLinkButton"] a[kind="primary"][disabled], '
    '[data-testid="stLinkButton"] a[kind="primary"][aria-disabled="true"])'
)
_PRIMARY_DISABLED_BUTTON_SELECTOR = (
    ':is([data-testid="stButton"] button[kind="primary"]:disabled, '
    '[data-testid="stFormSubmitButton"] button[kind="primaryFormSubmit"]:disabled, '
    '[data-testid="stDownloadButton"] button[kind="primary"]:disabled)'
)
_MARKDOWN_LINK_SELECTOR = (
    '[data-testid="stMarkdownContainer"] '
    'a:not([aria-label="Link to heading"])'
)
_SLIDER_TRACK_SELECTOR = (
    '[data-testid="stSlider"] [data-baseweb="slider"] '
    '> *:first-child > *:first-child > *:last-child'
)
# Streamlit owns the value-dependent gradient stops. Replacing that gradient
# would freeze every production slider at the fixture value. This opaque
# underlay plus fixed filter preserves those dynamic stops while mapping the
# selected and 25%-alpha unselected pixels to control/disabled roles.
_SLIDER_TRACK_BASE = "#373d42"
_SLIDER_TRACK_FILTER = (
    "brightness(1.333054) saturate(0.917118) hue-rotate(1.668758deg)"
)
_FOCUS_DECLARATIONS = (
    ("outline-color", COLOR_TOKENS["border.focus"]),
    ("outline-style", "solid"),
    ("outline-width", "3px"),
    ("outline-offset", "2px"),
    ("box-shadow", "none"),
)
_THEME_RULES = (
    (
        _PRIMARY_BUTTON_SELECTOR,
        (
            ("background-color", COLOR_TOKENS["interactive.primary"]),
            ("color", COLOR_TOKENS["text.on-primary"]),
            ("border-color", COLOR_TOKENS["interactive.control"]),
            ("border-style", "solid"),
            ("border-width", "1px"),
        ),
        _PRIMARY_BUTTON_CASES,
        ("default",),
    ),
    (
        _PRIMARY_BUTTON_SELECTOR + ":hover",
        (
            ("background-color", COLOR_TOKENS["interactive.hover"]),
            ("border-color", COLOR_TOKENS["interactive.control"]),
        ),
        _PRIMARY_BUTTON_CASES,
        ("hover",),
    ),
    (
        _PRIMARY_BUTTON_SELECTOR + ":active",
        (
            ("background-color", COLOR_TOKENS["interactive.active"]),
            ("border-color", COLOR_TOKENS["interactive.control"]),
        ),
        _PRIMARY_BUTTON_CASES,
        ("active",),
    ),
    (
        _LINK_BUTTON_SELECTOR,
        (
            ("background-color", COLOR_TOKENS["interactive.primary"]),
            ("color", COLOR_TOKENS["text.on-primary"]),
            ("border-color", COLOR_TOKENS["interactive.control"]),
            ("border-style", "solid"),
            ("border-width", "1px"),
        ),
        ("link_button",),
        ("default",),
    ),
    (
        _LINK_BUTTON_SELECTOR + ":hover",
        (
            ("background-color", COLOR_TOKENS["interactive.hover"]),
            ("border-color", COLOR_TOKENS["interactive.control"]),
        ),
        ("link_button",),
        ("hover",),
    ),
    (
        _LINK_BUTTON_SELECTOR + ":active",
        (
            ("background-color", COLOR_TOKENS["interactive.active"]),
            ("border-color", COLOR_TOKENS["interactive.control"]),
        ),
        ("link_button",),
        ("active",),
    ),
    (
        _PRIMARY_BUTTON_SELECTOR + ":focus-visible",
        _FOCUS_DECLARATIONS,
        _PRIMARY_BUTTON_CASES,
        ("focus-visible",),
    ),
    (
        _LINK_BUTTON_SELECTOR + ":focus-visible",
        _FOCUS_DECLARATIONS,
        ("link_button",),
        ("focus-visible",),
    ),
    (
        _PRIMARY_ACTION_DISABLED_SELECTOR,
        (
            ("background-color", COLOR_TOKENS["interactive.disabled"]),
            ("border-color", COLOR_TOKENS["interactive.disabled"]),
            ("color", COLOR_TOKENS["text.disabled"]),
            ("pointer-events", "none"),
        ),
        ("disabled",),
        ("disabled",),
    ),
    (
        _PRIMARY_DISABLED_BUTTON_SELECTOR,
        (("pointer-events", "auto"),),
        ("disabled",),
        ("disabled",),
    ),
    (
        '[data-testid="stButton"] button[kind="tertiary"]',
        (("color", COLOR_TOKENS["interactive.accent"]),),
        ("tertiary",),
        ("default",),
    ),
    (
        '[data-testid="stButton"] button[kind="tertiary"]:hover',
        (("color", COLOR_TOKENS["interactive.accent"]),),
        ("tertiary",),
        ("hover",),
    ),
    (
        '[data-testid="stButton"] button[kind="tertiary"]:active',
        (("color", COLOR_TOKENS["interactive.accent"]),),
        ("tertiary",),
        ("active",),
    ),
    (
        '[data-testid="stButton"] button[kind="tertiary"]:focus-visible',
        _FOCUS_DECLARATIONS,
        ("tertiary",),
        ("focus-visible",),
    ),
    (
        '[data-testid="stTabs"] [role="tab"][aria-selected="true"]',
        (("color", COLOR_TOKENS["interactive.accent"]),),
        ("tabs",),
        ("selected",),
    ),
    (
        '[data-testid="stTabs"] [data-baseweb="tab-highlight"]',
        (("background-color", COLOR_TOKENS["interactive.accent"]),),
        ("tabs",),
        ("selected",),
    ),
    (
        '[data-testid="stTabs"] [role="tab"]:hover',
        (("color", COLOR_TOKENS["interactive.accent"]),),
        ("tabs",),
        ("hover",),
    ),
    (
        '[data-testid="stTabs"] [role="tab"]:focus-visible',
        (
            ("color", COLOR_TOKENS["interactive.accent"]),
            ("box-shadow", "none"),
        ),
        ("tabs",),
        ("focus-visible",),
    ),
    (
        '[data-testid="stTabs"]:has([role="tab"]:focus-visible)',
        _FOCUS_DECLARATIONS,
        ("tabs",),
        ("focus-visible",),
    ),
    (
        _MARKDOWN_LINK_SELECTOR + ":link",
        (
            ("color", COLOR_TOKENS["interactive.accent"]),
            ("text-decoration", "underline"),
        ),
        ("markdown_link",),
        ("default",),
    ),
    (
        _MARKDOWN_LINK_SELECTOR + ":visited",
        (
            ("color", COLOR_TOKENS["interactive.accent"]),
            ("text-decoration", "underline"),
        ),
        ("markdown_link",),
        ("visited-static",),
    ),
    (
        _MARKDOWN_LINK_SELECTOR + ":hover",
        (
            ("color", COLOR_TOKENS["interactive.accent"]),
            ("text-decoration", "underline"),
        ),
        ("markdown_link",),
        ("hover",),
    ),
    (
        _MARKDOWN_LINK_SELECTOR + ":focus-visible",
        (
            ("color", COLOR_TOKENS["interactive.accent"]),
            ("text-decoration", "underline"),
            *_FOCUS_DECLARATIONS,
        ),
        ("markdown_link",),
        ("focus-visible",),
    ),
    (
        '[data-testid="stCheckbox"] '
        'span:has(+ input[type="checkbox"]:checked:not(:disabled))',
        (
            ("background-color", COLOR_TOKENS["interactive.control"]),
            ("border-color", COLOR_TOKENS["interactive.control"]),
            ("background-image", "none"),
            ("position", "relative"),
        ),
        ("checkbox",),
        ("checked",),
    ),
    (
        '[data-testid="stCheckbox"] '
        'span:has(+ input[type="checkbox"]:checked:not(:disabled))::after',
        (
            ("content", '\"\"'),
            ("position", "absolute"),
            ("left", "5px"),
            ("top", "1px"),
            ("width", "5px"),
            ("height", "10px"),
            ("border-color", COLOR_TOKENS["text.on-primary"]),
            ("border-style", "solid"),
            ("border-width", "0 2px 2px 0"),
            ("transform", "rotate(45deg)"),
        ),
        ("checkbox",),
        ("checked",),
    ),
    (
        '[data-testid="stCheckbox"] '
        'div:has(+ input[type="checkbox"]:checked:not(:disabled))',
        (
            ("background-color", COLOR_TOKENS["interactive.control"]),
            ("border-color", COLOR_TOKENS["interactive.control"]),
        ),
        ("toggle",),
        ("checked",),
    ),
    (
        '[data-testid="stCheckbox"] '
        'div:has(+ input[type="checkbox"]:checked:not(:disabled)) > div',
        (("background-color", COLOR_TOKENS["text.on-primary"]),),
        ("toggle",),
        ("checked",),
    ),
    (
        '[data-testid="stCheckbox"] label:has(input[type="checkbox"]:focus-visible)',
        _FOCUS_DECLARATIONS,
        ("checkbox", "toggle"),
        ("focus-visible",),
    ),
    (
        '[data-testid="stRadio"] [data-baseweb="radio"] > '
        'div:has(+ input[type="radio"]:checked:not(:disabled))',
        (
            ("background-color", COLOR_TOKENS["interactive.control"]),
            ("border-color", COLOR_TOKENS["interactive.control"]),
        ),
        ("radio", "radio_horizontal"),
        ("checked",),
    ),
    (
        '[data-testid="stRadio"] [data-baseweb="radio"] > '
        'div:has(+ input[type="radio"]:checked:not(:disabled)) > div',
        (("background-color", COLOR_TOKENS["text.on-primary"]),),
        ("radio", "radio_horizontal"),
        ("checked",),
    ),
    (
        '[data-testid="stRadio"] [data-baseweb="radio"]:'
        'has(input[type="radio"]:focus-visible) > div:first-child',
        (("box-shadow", "none"),),
        ("radio", "radio_horizontal"),
        ("focus-visible",),
    ),
    (
        '[data-testid="stRadio"]:'
        'has(input[type="radio"]:focus-visible)',
        _FOCUS_DECLARATIONS,
        ("radio", "radio_horizontal"),
        ("focus-visible",),
    ),
    (
        '[data-testid="stSlider"] [role="slider"]',
        (("background-color", COLOR_TOKENS["interactive.control"]),),
        ("slider",),
        ("selected",),
    ),
    (
        _SLIDER_TRACK_SELECTOR,
        (
            ("background-color", _SLIDER_TRACK_BASE),
            ("filter", _SLIDER_TRACK_FILTER),
        ),
        ("slider",),
        ("selected",),
    ),
    (
        '[data-testid="stSlider"] [data-testid="stSliderThumbValue"]',
        (("color", COLOR_TOKENS["interactive.accent"]),),
        ("slider",),
        ("selected",),
    ),
    (
        '[data-testid="stSlider"] [role="slider"]:focus-visible',
        (("box-shadow", "none"),),
        ("slider",),
        ("focus-visible",),
    ),
    (
        '[data-testid="stSlider"]:has([role="slider"]:focus-visible)',
        _FOCUS_DECLARATIONS,
        ("slider",),
        ("focus-visible",),
    ),
    (
        '[data-testid="stSelectbox"] [data-baseweb="select"] > div',
        (("border-color", COLOR_TOKENS["interactive.control"]),),
        ("selectbox",),
        ("selected",),
    ),
    (
        '[data-testid="stSelectbox"] [role="combobox"]:focus-visible',
        (("box-shadow", "none"),),
        ("selectbox",),
        ("focus-visible",),
    ),
    (
        '[data-testid="stSelectbox"]:'
        'has([role="combobox"]:focus-visible)',
        _FOCUS_DECLARATIONS,
        ("selectbox",),
        ("focus-visible",),
    ),
    (
        '[data-testid="stAlertContentInfo"] '
        '[data-testid="stMarkdownContainer"] p',
        (("color", COLOR_TOKENS["text.primary"]),),
        ("alerts",),
        ("default",),
    ),
    (
        '[data-testid="stAlertContentSuccess"] '
        '[data-testid="stMarkdownContainer"] p',
        (("color", COLOR_TOKENS["text.primary"]),),
        ("alerts",),
        ("default",),
    ),
    (
        '[data-testid="stAlertContentWarning"] '
        '[data-testid="stMarkdownContainer"] p',
        (("color", COLOR_TOKENS["text.primary"]),),
        ("alerts",),
        ("default",),
    ),
    (
        '[data-testid="stAlertContentError"] '
        '[data-testid="stMarkdownContainer"] p',
        (("color", COLOR_TOKENS["text.primary"]),),
        ("alerts",),
        ("default",),
    ),
)


def _theme_owners(cases: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(
        sorted(
            f"ux1b_owner_{surface}_{case}"
            for case in cases
            for surface in _THEME_SURFACES
        )
    )


THEME_SELECTOR_CONTRACT = tuple(
    MappingProxyType({
        "selector": selector,
        "property": property_name,
        "owners": _theme_owners(cases),
        "states": states,
        "important": value.casefold().endswith("!important"),
    })
    for selector, declarations, cases, states in _THEME_RULES
    for property_name, value in declarations
)

_GLOBAL_THEME_CSS = "<style>\n" + "\n".join(
    selector
    + " { "
    + " ".join(f"{name}: {value};" for name, value in declarations)
    + " }"
    for selector, declarations, _cases, _states in _THEME_RULES
) + "\n</style>"


def build_global_theme_css() -> str:
    """Return the fixed, component-scoped UX-1B semantic theme CSS."""

    return _GLOBAL_THEME_CSS


# Chip foregrounds are deliberately brighter than some legacy chart colours.
# At 0x22 fill opacity every value below reaches 4.5:1 on both current surfaces.
CHIP_FILL_ALPHA = 0x22 / 0xFF
CHIP_COLORS: Mapping[str, str] = MappingProxyType({
    "info": "#7fe3f0",
    "success": "#00cc96",
    "warning": "#ffa15a",
    "error": "#fb7185",
    "bullish": "#00cc96",
    "neutral": "#ffa15a",
    "bearish": "#fb7185",
    "avoid": "#fb7185",
    "loss": "#f87171",
    "purple": "#c084fc",
    "cyan": "#7fe3f0",
    "muted": "#aab2c5",
})

_TOKEN_TO_CHIP: Mapping[str, str] = MappingProxyType({
    "feedback.info": CHIP_COLORS["info"],
    "feedback.success": CHIP_COLORS["success"],
    "feedback.warning": CHIP_COLORS["warning"],
    "feedback.error": CHIP_COLORS["error"],
    "signal.bullish": CHIP_COLORS["bullish"],
    "signal.neutral": CHIP_COLORS["neutral"],
    "signal.bearish": CHIP_COLORS["bearish"],
    "signal.avoid": CHIP_COLORS["avoid"],
    "text.secondary": CHIP_COLORS["muted"],
    "chip.info": CHIP_COLORS["info"],
    "chip.success": CHIP_COLORS["success"],
    "chip.warning": CHIP_COLORS["warning"],
    "chip.error": CHIP_COLORS["error"],
    "chip.loss": CHIP_COLORS["loss"],
    "chip.purple": CHIP_COLORS["purple"],
    "chip.cyan": CHIP_COLORS["cyan"],
    "chip.muted": CHIP_COLORS["muted"],
})
CHIP_TOKEN_NAMES = frozenset(_TOKEN_TO_CHIP)

# Fixed values kept public by ui._shared remain valid inputs, but are projected
# to the accessible component palette before they enter an HTML attribute.
_LEGACY_TO_CHIP: Mapping[str, str] = MappingProxyType({
    "#00cc96": CHIP_COLORS["success"],
    "#ef553b": CHIP_COLORS["error"],
    "#f87171": CHIP_COLORS["loss"],
    "#ef4444": CHIP_COLORS["avoid"],
    "#ffa15a": CHIP_COLORS["warning"],
    "#636efa": CHIP_COLORS["info"],
    "#ab63fa": CHIP_COLORS["purple"],
    "#19d3f3": CHIP_COLORS["cyan"],
    "#8b93a7": CHIP_COLORS["muted"],
})
_APPROVED_CHIP_VALUES: Mapping[str, str] = MappingProxyType({
    value.casefold(): value for value in CHIP_COLORS.values()
})


def resolve_chip_color(value: object) -> str:
    """Return a fixed chip foreground; unknown inputs always become muted."""
    if not isinstance(value, str):
        return CHIP_COLORS["muted"]
    try:
        candidate = str(value).strip()
        if candidate in _TOKEN_TO_CHIP:
            return _TOKEN_TO_CHIP[candidate]
        normalized = candidate.casefold()
        if normalized in _LEGACY_TO_CHIP:
            return _LEGACY_TO_CHIP[normalized]
        if normalized in _APPROVED_CHIP_VALUES:
            return _APPROVED_CHIP_VALUES[normalized]
    except Exception:
        return CHIP_COLORS["muted"]
    return CHIP_COLORS["muted"]


def _rgb(hex_color: str) -> tuple[int, int, int]:
    if (
        not isinstance(hex_color, str)
        or len(hex_color) != 7
        or not hex_color.startswith("#")
    ):
        raise ValueError("colour must use #RRGGBB")
    try:
        values = tuple(int(hex_color[index:index + 2], 16) for index in (1, 3, 5))
    except ValueError as exc:
        raise ValueError("colour must use #RRGGBB") from exc
    return values  # type: ignore[return-value]


def composite_hex(foreground: str, background: str, alpha: float) -> str:
    """Composite an sRGB foreground over a background and return #rrggbb."""
    if isinstance(alpha, bool) or not isinstance(alpha, (int, float)):
        raise TypeError("alpha must be numeric")
    opacity = float(alpha)
    if not math.isfinite(opacity) or not 0.0 <= opacity <= 1.0:
        raise ValueError("alpha must be between zero and one")
    fg = _rgb(foreground)
    bg = _rgb(background)
    blended = tuple(round(opacity * front + (1.0 - opacity) * back)
                    for front, back in zip(fg, bg))
    return "#" + "".join(f"{channel:02x}" for channel in blended)


def _linear_channel(channel: int) -> float:
    value = channel / 255.0
    return value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4


def relative_luminance(color: str) -> float:
    """Return WCAG relative luminance for one #RRGGBB colour."""
    red, green, blue = (_linear_channel(channel) for channel in _rgb(color))
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast_ratio(foreground: str, background: str) -> float:
    """Return the WCAG contrast ratio between two #RRGGBB colours."""
    first = relative_luminance(foreground)
    second = relative_luminance(background)
    lighter, darker = max(first, second), min(first, second)
    return (lighter + 0.05) / (darker + 0.05)
