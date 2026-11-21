"""Pronunciation help that works offline, for every entry.

- language_of(): a best guess of the entry's language as a BCP-47 tag ("en-US", "zh-CN",
  "fr-FR", ...). The browser's text-to-speech uses it for the Listen button.
- local_phonetic(): an IPA line for English (CMU Pronouncing Dictionary via eng_to_ipa) or
  pinyin with tone marks for Chinese. Used when the online dictionary has nothing - phrases,
  sentences and quotes - so most entries show a pronunciation line.

Both are fast and need no network, so they can run whenever an entry is listed or saved.
"""

import re
import warnings
from collections.abc import Iterable
from functools import lru_cache

# Writing systems that identify the language on their own.
_SCRIPTS = [
    (re.compile(r"[぀-ヿ]"), "ja-JP"),  # Japanese kana (checked before Chinese)
    (re.compile(r"[一-鿿㐀-䶿]"), "zh-CN"),
    (re.compile(r"[가-힯]"), "ko-KR"),
    (re.compile(r"[ऀ-ॿ]"), "hi-IN"),
    (re.compile(r"[؀-ۿ]"), "ar-SA"),
    (re.compile(r"[֐-׿]"), "he-IL"),
    (re.compile(r"[Ѐ-ӿ]"), "ru-RU"),
    (re.compile(r"[Ͱ-Ͽ]"), "el-GR"),
    (re.compile(r"[฀-๿]"), "th-TH"),
]

# Latin-script languages are recognised from the entry's category name,
# e.g. "French Basics", "My Spanish", "Deutsch".
_CATEGORY_HINTS = {
    "fr-FR": ("french", "français", "francais"),
    "es-ES": ("spanish", "español", "espanol"),
    "de-DE": ("german", "deutsch"),
    "it-IT": ("italian", "italiano"),
    "pt-PT": ("portuguese", "português", "portugues"),
    "nl-NL": ("dutch", "nederlands"),
    "tr-TR": ("turkish", "türkçe"),
}

_ENGLISH_WORD = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")
_ACCENTED = re.compile(r"[À-ÖØ-öø-ÿĀ-ž]")
_MATH = re.compile(r"[=+×÷^√∑∫∞≈≠≤≥²³¹⁰-⁹]")


def language_of(text: str, category_names: Iterable[str] = ()) -> str:
    for pattern, lang in _SCRIPTS:
        if pattern.search(text):
            return lang
    names = " ".join(category_names).lower()
    for lang, hints in _CATEGORY_HINTS.items():
        if any(h in names for h in hints):
            return lang
    return "en-US"


@lru_cache(maxsize=1)
def _english():
    with warnings.catch_warnings():  # the library has old-style regex strings
        warnings.simplefilter("ignore", SyntaxWarning)
        import eng_to_ipa
    return eng_to_ipa


def _english_ipa(text: str) -> str:
    if _ACCENTED.search(text):
        return ""  # é, à, ñ...: almost certainly French, Spanish etc. - don't guess
    if _MATH.search(text):
        return ""  # a formula: letters there are symbols, not words
    words = _ENGLISH_WORD.findall(text)
    if not words:
        return ""  # e.g. a math formula
    ipa = _english().convert(" ".join(words)).split()
    unknown = sum(1 for w in ipa if w.endswith("*"))
    if unknown * 3 > len(ipa):
        return ""  # many unknown words: probably not English, so show nothing
    return "/" + " ".join(w.rstrip("*") for w in ipa) + "/"


def _pinyin(text: str) -> str:
    from pypinyin import Style, pinyin

    chinese = re.findall(r"[一-鿿㐀-䶿]+", text)
    return " ".join(s[0] for part in chinese for s in pinyin(part, style=Style.TONE))


def local_phonetic(text: str, lang: str) -> str:
    """An IPA line for English, pinyin for Chinese, otherwise ""."""
    try:
        if lang == "en-US":
            return _english_ipa(text)
        if lang == "zh-CN":
            return _pinyin(text)
    except Exception:  # pronunciation is a nice-to-have; never fail saving an entry
        return ""
    return ""
