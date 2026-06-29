def truncate_text(text: object, max_length: int = 200) -> str:
    """Return a single-line preview that is safe for business logs."""
    if text is None:
        return ""

    value = " ".join(str(text).split())
    if len(value) <= max_length:
        return value

    return f"{value[:max_length].rstrip()}..."
