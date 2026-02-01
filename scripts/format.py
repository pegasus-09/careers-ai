def format_text(text: str, title: bool = True) -> str:
    return text.replace("_", " ").title() if title else text.replace("_", " ")