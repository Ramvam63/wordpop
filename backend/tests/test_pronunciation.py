from app.models import Word
from app.notifications import build_payload
from app.pronunciation import language_of, local_phonetic


def test_language_from_script_and_category():
    assert language_of("你好") == "zh-CN"
    assert language_of("नमस्ते") == "hi-IN"
    assert language_of("ありがとう") == "ja-JP"
    assert language_of("Bonjour", ["French Basics"]) == "fr-FR"
    assert language_of("¿Dónde está?", ["My Spanish"]) == "es-ES"
    assert language_of("give up") == "en-US"


def test_english_phrases_get_ipa():
    assert local_phonetic("Obviously", "en-US") == "/ˈɑbviəsli/"
    ipa = local_phonetic("Don't give up!", "en-US")
    assert ipa.startswith("/") and ipa.endswith("/") and "gɪv" in ipa


def test_chinese_gets_pinyin():
    assert local_phonetic("你好！", "zh-CN") == "nǐ hǎo"


def test_no_guessing_for_unknown_text():
    assert local_phonetic("Petit à petit, l'oiseau fait son nid", "en-US") == ""
    assert local_phonetic("a² + b² = c²", "en-US") == ""
    assert local_phonetic("Bonjour", "fr-FR") == ""  # only English and Chinese have a phonetic line


def test_long_phonetic_is_left_out_of_notifications():
    w = Word(id=1, text="A long sentence", meaning="m", phonetic="/" + "ə" * 80 + "/")
    assert build_payload(None, w)["body"].startswith("Do you remember")
