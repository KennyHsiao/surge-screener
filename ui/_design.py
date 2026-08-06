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
    "text.disabled": "#7f8799",
})

BORDER_TOKENS: Mapping[str, str] = MappingProxyType({
    "border.default": "#394154",
    "border.focus": "#7fe3f0",
})

INTERACTIVE_TOKENS: Mapping[str, str] = MappingProxyType({
    "interactive.primary": "#ef4444",
    "interactive.hover": "#fb7185",
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
