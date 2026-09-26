"""Cheap, model-agnostic cleanup of raw model output. Each rule should be justified by dev-set evidence."""
import re
import zlib

from variants import tables_variant

FENCE_RE = re.compile(r"^\s*```(?:markdown|md)?\s*\n(.*?)\n```\s*$", re.S)
PAGE_ECHO_RE = re.compile(r"^\s*(?:\*\*)?Page \d+:?(?:\*\*)?\s*\n", re.I)


SECTION_RE = re.compile(r"^[ \t]*(?:\*\*)?<<<[^>\n]{1,30}>>>(?:\*\*)?[ \t]*$", re.M)  # v7 section labels, incl. typos like <<<FURNITITURE>>>


def strip_sections(md):
    return re.sub(r"\n{3,}", "\n\n", SECTION_RE.sub("", md))


PLACEHOLDER_RE = re.compile(r"\s*\[(?:text\s+)?(?:clear|illegible|unclear|unreadable|blurry|blurred)[^\]]*\]", re.I)


def is_degenerate(md):
    """Repetition loop: long output that compresses to almost nothing, or a flood of placeholder tokens."""
    if len(md) > 3000 and len(zlib.compress(md.encode())) / len(md.encode()) < 0.06:
        return True
    return len(PLACEHOLDER_RE.findall(md)) > 15


DISPLAY_BRACKET_RE = re.compile(r"(?<!\\)\\\[(.*?)(?<!\\)\\\]", re.S)  # \[ ... \]   (not the \\[2pt] row-spacing form)
INLINE_PAREN_RE = re.compile(r"(?<!\\)\\\((.*?)(?<!\\)\\\)", re.S)  # \( ... \)


def normalize_math(md):
    r"""Dev ground truth stores display math as $$...$$ and inline math as $...$; the README's \[ \] / \( \) forms
    are converted so a delimiter-based scorer finds the formulas."""
    md = DISPLAY_BRACKET_RE.sub(lambda m: "$$\n" + m.group(1).strip() + "\n$$", md)
    return INLINE_PAREN_RE.sub(lambda m: "$" + m.group(1).strip() + "$", md)


def postprocess(md):
    md = strip_sections(md).strip()
    m = FENCE_RE.match(md)  # whole answer wrapped in a ```markdown fence
    if m:
        md = m.group(1)
    md = PAGE_ECHO_RE.sub("", md)  # model echoing our "Page N:" labels
    md = normalize_math(md)
    md = PLACEHOLDER_RE.sub("", md)  # "[illegible]"-style tokens never appear in the ground truth
    md = re.sub(r"\n{3,}", "\n\n", md)
    return tables_variant(md.strip())  # tables in the ground truth's <table><tbody> style: small TEDS gain on dev
