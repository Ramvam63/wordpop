from app.models import Word
from app.notifications import build_payload
from app.pronunciation import is_single_word, language_of, local_phonetic


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


def test_only_single_words_count():
    for text in ("Obviously", "Cross-functional", "don't", "  serendipity  "):
        assert is_single_word(text, "en-US"), text
    for text in ("give up", "Everyone in this room", "Hello!", "C = 2πr", "180°"):
        assert not is_single_word(text, "en-US"), text
    assert is_single_word("谢谢", "zh-CN") and not is_single_word("你好，谢谢！", "zh-CN")


def test_old_sentence_pronunciations_are_cleared(user_client, session_factory):
    """Entries saved when sentences still got a line lose it the next time the list loads."""
    wid = user_client.post("/api/words", json={"text": "Bring everybody together", "meaning": "m"}).json()["id"]
    with session_factory() as db:
        db.get(Word, wid).phonetic = "/brɪŋ ˈɛvriˌbɑdi təˈgɛðər/"
        db.commit()
    assert user_client.get("/api/words").json()[0]["phonetic"] == ""
