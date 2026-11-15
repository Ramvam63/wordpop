import httpx

from app import dictionary

FREE_DICT = [
    {
        "word": "curious",
        "phonetic": "/ˈkjʊə.ɹi.əs/",
        "phonetics": [{"text": "/ˈkjʊə.ɹi.əs/", "audio": "https://example.com/curious.mp3"}],
        "meanings": [
            {"partOfSpeech": "adjective", "definitions": [
                {"definition": "Eager to know or learn something.", "example": "She was curious about the box."}
            ]}
        ],
    }
]

WIKTIONARY = {
    "en": [
        {
            "partOfSpeech": "Verb",
            "language": "English",
            "definitions": [
                {"definition": ""},
                {
                    "definition": "(<i>transitive</i>) To <a href='/wiki/understand'>understand</a>, "
                                  "solve or work out.",
                    "parsedExamples": [{"example": "I can&#39;t <b>figure out</b> this puzzle."}],
                },
            ],
        }
    ],
    "fr": [{"partOfSpeech": "Verb", "definitions": [{"definition": "not English"}]}],
}


class FakeResponse:
    def __init__(self, status, payload=None):
        self.status_code, self._payload = status, payload

    def json(self):
        return self._payload


def test_parse_free_dictionary():
    r = dictionary.parse(FREE_DICT)
    assert r["meaning"].startswith("Eager")
    assert r["phonetic"] and r["audio_url"].endswith(".mp3")


def test_parse_wiktionary_strips_html_and_skips_empty():
    r = dictionary.parse_wiktionary(WIKTIONARY)
    assert r["meaning"] == "(transitive) To understand, solve or work out."
    assert r["example"] == "I can't figure out this puzzle."
    assert r["part_of_speech"] == "verb"


def test_falls_back_to_wiktionary_for_phrases(monkeypatch):
    calls = []

    def fake_get(url, **kw):
        calls.append(url)
        assert "User-Agent" in kw["headers"]
        if "dictionaryapi.dev" in url:
            return FakeResponse(404)
        return FakeResponse(200, WIKTIONARY)

    monkeypatch.setattr(httpx, "get", fake_get)
    r = dictionary.lookup("  figure   out ")
    assert r["meaning"].startswith("(transitive) To understand")
    assert "figure%20out" in calls[0] and "figure_out" in calls[1]


def test_network_errors_return_none(monkeypatch):
    def broken(url, **kw):
        raise httpx.ConnectError("no network")

    monkeypatch.setattr(httpx, "get", broken)
    assert dictionary.lookup("curious") is None
