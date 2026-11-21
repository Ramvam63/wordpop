import csv
import io

from app import csv_io


def _rows(body: bytes) -> list[list[str]]:
    text = body.decode("utf-8")
    assert text.startswith("﻿")  # so Excel opens Chinese, Hindi, accents correctly
    return list(csv.reader(io.StringIO(text[1:])))


def test_export_round_trip(user_client):
    cat = user_client.post("/api/categories", json={"name": "CCP"}).json()
    user_client.post("/api/words", json={"text": "Obviously", "meaning": "clearly, without doubt",
                                         "example": 'She said "obviously".', "category_ids": [cat["id"]]})
    user_client.post("/api/words", json={"text": "谢谢", "meaning": "thank you"})
    user_client.post("/api/words", json={"text": "-b ± √(b² - 4ac)", "meaning": "quadratic formula"})

    r = user_client.get("/api/words/export")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert "attachment; filename=\"wordpop-" in r.headers["content-disposition"]
    rows = _rows(r.content)
    assert rows[0] == ["text", "meaning", "example", "categories"]
    assert rows[1] == ["Obviously", "clearly, without doubt", 'She said "obviously".', "CCP"]
    assert rows[3][0] == "'-b ± √(b² - 4ac)"  # a spreadsheet won't run it as a formula

    # one category only
    only = _rows(user_client.get(f"/api/words/export?category_id={cat['id']}").content)
    assert [r[0] for r in only[1:]] == ["Obviously"]

    # Re-importing the export into a fresh account gives the same entries back
    exported = r.content.decode("utf-8")
    user_client.post("/api/auth/logout")
    user_client.post("/api/auth/signup", json={"email": "second@example.com", "password": "password1"})
    result = user_client.post("/api/words/import", json={"csv": exported}).json()
    assert result["added"] == 3 and result["categories_created"] == ["CCP"] and result["errors"] == []
    words = {w["text"]: w for w in user_client.get("/api/words").json()}
    assert set(words) == {"Obviously", "谢谢", "-b ± √(b² - 4ac)"}
    assert words["Obviously"]["example"] == 'She said "obviously".'
    assert [c["name"] for c in words["Obviously"]["categories"]] == ["CCP"]


def test_import_skips_duplicates_and_reports_problems(user_client):
    user_client.post("/api/words", json={"text": "brave", "meaning": "not afraid"})
    body = "Word,Translation,Category\nBrave,valiente,Spanish\nbonjour,hello,French; Travel\n,no text,\n" + \
           "x" * 501 + ",too long,\n\nmerci,thank you,french\n"
    r = user_client.post("/api/words/import", json={"csv": body}).json()
    assert r["added"] == 2 and r["duplicates"] == 1
    assert r["categories_created"] == ["French", "Travel"]  # "french" reuses "French"
    assert [e["line"] for e in r["errors"]] == [4, 5]
    words = {w["text"]: w for w in user_client.get("/api/words").json()}
    assert words["bonjour"]["meaning"] == "hello"
    assert sorted(c["name"] for c in words["bonjour"]["categories"]) == ["French", "Travel"]


def test_import_without_header_semicolons_and_into_a_category(user_client):
    target = user_client.post("/api/categories", json={"name": "Imported"}).json()
    body = "serendipity;a happy accident;Meeting her was serendipity\ngive up;stop trying;\n"
    r = user_client.post("/api/words/import", json={"csv": body, "category_id": target["id"]}).json()
    assert r["added"] == 2 and r["errors"] == []
    for w in user_client.get("/api/words").json():
        assert [c["name"] for c in w["categories"]] == ["Imported"]
    assert user_client.post("/api/words/import", json={"csv": "a,b", "category_id": 9999}).status_code == 404


def test_single_column_list_and_empty_file(user_client):
    r = user_client.post("/api/words/import", json={"csv": "text\napple\nbanana\n"}).json()
    assert r["added"] == 2
    assert user_client.post("/api/words/import", json={"csv": "\n\n"}).status_code == 422


def test_reader_unit():
    parsed = csv_io.read_csv("﻿text\tmeaning\nhola\thello\n")
    assert [(r.text, r.meaning) for r in parsed.rows] == [("hola", "hello")]
