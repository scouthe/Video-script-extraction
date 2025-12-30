from ...utils.text import clean_text, split_paragraphs


def postprocess_text(text: str) -> list[str]:
    cleaned = clean_text(text)
    paragraphs = split_paragraphs(cleaned)
    return paragraphs if paragraphs else [cleaned]
