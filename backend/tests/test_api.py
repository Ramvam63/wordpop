def test_health(client):
    assert client.get("/api/health").json()["status"] == "ok"


def test_signup_login_and_me(client):
    r = client.post("/api/auth/signup", json={"email": "A@Example.com", "password": "password1"})
    assert r.status_code == 201
    assert r.json()["email"] == "a@example.com"

    assert client.post("/api/auth/signup", json={"email": "a@example.com", "password": "password1"}).status_code == 409

    client.post("/api/auth/logout")
    client.cookies.clear()
    assert client.get("/api/auth/me").status_code == 401

    assert client.post("/api/auth/login", json={"email": "a@example.com", "password": "nope"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "a@example.com", "password": "password1"}).status_code == 200
    assert client.get("/api/auth/me").json()["email"] == "a@example.com"


def test_short_password_rejected(client):
    r = client.post("/api/auth/signup", json={"email": "b@example.com", "password": "123"})
    assert r.status_code == 422


def test_add_word_with_autofill_and_categories(user_client):
    cat = user_client.post("/api/categories", json={"name": "IELTS"}).json()

    r = user_client.post("/api/words", json={"text": "serendipity", "category_ids": [cat["id"]]})
    assert r.status_code == 201, r.text
    word = r.json()
    assert word["meaning"].startswith("finding something good")
    assert word["phonetic"]
    assert [c["name"] for c in word["categories"]] == ["IELTS"]

    # duplicate (case-insensitive)
    assert user_client.post("/api/words", json={"text": "Serendipity"}).status_code == 409
    # unknown word with no meaning -> ask the user to type one
    assert user_client.post("/api/words", json={"text": "qwzx"}).status_code == 422
    # filter by category
    assert len(user_client.get(f"/api/words?category_id={cat['id']}").json()) == 1
    cats = user_client.get("/api/categories").json()
    assert cats[0]["word_count"] == 1


def test_words_are_private_per_user(client):
    client.post("/api/auth/signup", json={"email": "one@example.com", "password": "password1"})
    w = client.post("/api/words", json={"text": "apple", "meaning": "a fruit"}).json()
    client.cookies.clear()
    client.post("/api/auth/signup", json={"email": "two@example.com", "password": "password1"})
    assert client.get("/api/words").json() == []
    assert client.delete(f"/api/words/{w['id']}").status_code == 404


def test_edit_and_delete_word(user_client):
    w = user_client.post("/api/words", json={"text": "apple", "meaning": "a fruit"}).json()
    r = user_client.patch(f"/api/words/{w['id']}", json={"meaning": "a round fruit"})
    assert r.json()["meaning"] == "a round fruit"
    assert user_client.delete(f"/api/words/{w['id']}").status_code == 204
    assert user_client.get("/api/words").json() == []


def test_category_toggle_and_delete_keeps_words(user_client):
    cat = user_client.post("/api/categories", json={"name": "Movies"}).json()
    user_client.post("/api/words", json={"text": "plot", "meaning": "story", "category_ids": [cat["id"]]})
    r = user_client.patch(f"/api/categories/{cat['id']}", json={"notify": False})
    assert r.json()["notify"] is False
    assert user_client.delete(f"/api/categories/{cat['id']}").status_code == 204
    words = user_client.get("/api/words").json()
    assert len(words) == 1 and words[0]["categories"] == []


def test_settings_and_pause(user_client):
    s = user_client.get("/api/me/settings").json()
    assert s["timezone"] == "America/Toronto"
    r = user_client.put(
        "/api/me/settings",
        json={"notify_every_minutes": 120, "active_start_hour": 8, "active_days": "01234"},
    )
    assert r.json()["notify_every_minutes"] == 120
    assert user_client.put("/api/me/settings", json={"timezone": "Mars/Base"}).status_code == 422
    assert user_client.put("/api/me/settings", json={"notify_every_minutes": 1}).status_code == 422
    assert user_client.post("/api/me/pause", json={"hours": 24}).json()["paused_until"]
    assert user_client.post("/api/me/pause", json={"hours": 0}).json()["paused_until"] is None


def test_quiz_flow_updates_spaced_repetition_and_progress(user_client):
    user_client.post("/api/words", json={"text": "apple", "meaning": "a fruit"})
    user_client.post("/api/words", json={"text": "brave", "meaning": "not afraid"})

    q = user_client.get("/api/quiz/next").json()
    r = user_client.post("/api/quiz/answer", json={"word_id": q["id"], "knew": True}).json()
    assert r["box"] == 1 and r["times_correct"] == 1

    q2 = user_client.get(f"/api/quiz/next?exclude_id={q['id']}").json()
    assert q2["id"] != q["id"]
    r2 = user_client.post("/api/quiz/answer", json={"word_id": q2["id"], "knew": False}).json()
    assert r2["box"] == 0 and r2["times_wrong"] == 1

    p = user_client.get("/api/me/progress").json()
    assert p["total_words"] == 2
    assert p["reviews_total"] == 2
    assert p["accuracy"] == 50
    assert p["streak_days"] == 1
    assert p["hardest"][0]["text"] == q2["text"]


def test_starter_list_import_is_idempotent(user_client):
    lists = user_client.get("/api/starter-lists").json()
    assert [l["name"] for l in lists] == [
        "Vocabulary", "Phrasal Verbs", "Idioms", "Casual", "Motivation", "Math Formulas", "Poems",
        "French Basics", "Spanish Basics", "Chinese Basics", "Hindi Basics",
    ]
    first = user_client.post("/api/starter-lists/vocabulary/import").json()
    assert first["added"] == first["total"] > 0
    again = user_client.post("/api/starter-lists/vocabulary/import").json()
    assert again["added"] == 0
    cats = user_client.get("/api/categories").json()
    assert cats[0]["name"] == "Vocabulary" and cats[0]["word_count"] == first["total"]


def test_renamed_starter_list_reuses_the_old_category(user_client):
    """Someone who added "IELTS Essentials" before it became "Vocabulary" gets no duplicate."""
    old = user_client.post("/api/categories", json={"name": "IELTS Essentials"}).json()
    user_client.post("/api/words", json={"text": "mitigate", "meaning": "reduce", "category_ids": [old["id"]]})
    r = user_client.post("/api/starter-lists/vocabulary/import").json()
    assert r["category_id"] == old["id"] and r["added"] == r["total"] - 1
    cats = user_client.get("/api/categories").json()
    assert [c["name"] for c in cats] == ["Vocabulary"]


def test_starter_list_keeps_a_name_the_user_chose(user_client):
    r = user_client.post("/api/starter-lists/idioms/import").json()
    user_client.patch(f"/api/categories/{r['category_id']}", json={"name": "My idioms"})
    again = user_client.post("/api/starter-lists/idioms/import").json()
    assert again["category_id"] == r["category_id"] and again["added"] == 0
    assert [c["name"] for c in user_client.get("/api/categories").json()] == ["My idioms"]


def test_admin_stats_requires_admin(client):
    client.post("/api/auth/signup", json={"email": "user@example.com", "password": "password1"})
    assert client.get("/api/admin/stats").status_code == 403
    client.cookies.clear()
    client.post("/api/auth/signup", json={"email": "admin@example.com", "password": "password1"})
    stats = client.get("/api/admin/stats").json()
    assert stats["users_total"] == 2


def test_push_subscribe(user_client):
    sub = {"endpoint": "https://push.example/abc", "keys": {"p256dh": "k", "auth": "a"}}
    assert user_client.post("/api/push/subscribe", json=sub).status_code == 201
    assert user_client.post("/api/push/subscribe", json=sub).status_code == 201  # no duplicate error


def test_delete_account(user_client):
    user_client.post("/api/words", json={"text": "apple", "meaning": "a fruit"})
    assert user_client.delete("/api/auth/me").status_code == 204
    assert user_client.get("/api/auth/me").status_code == 401


def test_frontend_is_served(client):
    r = client.get("/")
    assert r.status_code == 200 and "WordPop" in r.text
    assert client.get("/sw.js").status_code == 200


def test_every_starter_list_imports_cleanly(user_client):
    """All lists (incl. Chinese, Hindi, poems with line breaks, formulas) fit the 500-char limit."""
    for item in user_client.get("/api/starter-lists").json():
        r = user_client.post(f"/api/starter-lists/{item['key']}/import")
        assert r.status_code == 200 and r.json()["added"] == item["count"], item["key"]
    words = user_client.get("/api/words").json()
    assert any(w["text"] == "你好" for w in words) and any(w["text"] == "नमस्ते" for w in words)
