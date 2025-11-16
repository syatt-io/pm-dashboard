"""Utility to map Jira epic color names to hex codes."""

# Jira epic color mapping
# Based on Atlassian's epic color palette
EPIC_COLOR_MAP = {
    # Blues
    "blue": "#0052CC",
    "bold blue": "#0747A6",
    "subtle blue": "#4C9AFF",

    # Teals
    "teal": "#00875A",
    "bold teal": "#006644",
    "subtle teal": "#79F2C0",

    # Greens
    "green": "#36B37E",
    "bold green": "#00875A",

    # Yellows
    "yellow": "#FFAB00",

    # Oranges
    "orange": "#FF8B00",
    "bold orange": "#FF5630",

    # Purples
    "purple": "#6554C0",
    "bold purple": "#403294",

    # Reds
    "red": "#DE350B",
    "subtle red": "#FFEBE6",

    # Grays
    "gray": "#97A0AF",
    "grey": "#97A0AF",

    # Default
    "": "#6554C0",  # Default to purple if not specified
    None: "#6554C0",
}


def get_epic_color_hex(color_name: str | None) -> str:
    """
    Convert epic color name to hex code.

    Args:
        color_name: Color name from CSV (e.g., "Subtle Blue", "Bold Purple")

    Returns:
        Hex color code (e.g., "#4C9AFF")
    """
    if not color_name:
        return EPIC_COLOR_MAP[None]

    # Normalize to lowercase for lookup
    normalized = color_name.lower().strip()

    return EPIC_COLOR_MAP.get(normalized, EPIC_COLOR_MAP[None])
