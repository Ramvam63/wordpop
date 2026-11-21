// WordPop PWA – plain JavaScript, no build step.

const $view = document.getElementById("view");
const $tabbar = document.getElementById("tabbar");
const $toast = document.getElementById("toast");

const state = { user: null, categories: [], installDismissed: sessionStorageGet("installDismissed") };

// ---------- helpers ----------
function sessionStorageGet(k) { try { return sessionStorage.getItem(k); } catch { return null; } }
function sessionStorageSet(k, v) { try { sessionStorage.setItem(k, v); } catch { /* ignore */ } }

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

async function api(path, { method = "GET", body } = {}) {
  // The free server sleeps when unused; if a request is slow, say so instead of looking frozen.
  const slow = setTimeout(() => showWaking(true), 2500);
  let res;
  try {
    for (let attempt = 0; ; attempt++) {
      try {
        res = await fetch(path, {
          method,
          credentials: "same-origin",
          headers: body ? { "Content-Type": "application/json" } : {},
          body: body ? JSON.stringify(body) : undefined,
        });
      } catch (e) {
        if (attempt >= 5) throw new Error("Can't reach WordPop. Check your internet connection and try again.");
        showWaking(true);
        await new Promise((r) => setTimeout(r, 3000));
        continue;
      }
      // While waking up, the host may answer with its own HTML page instead of our JSON: wait and retry.
      const isJson = (res.headers.get("content-type") || "").includes("json") || res.status === 204;
      if (isJson || attempt >= 20) break;
      showWaking(true);
      await new Promise((r) => setTimeout(r, 4000));
    }
  } finally { clearTimeout(slow); showWaking(false); }
  if (res.status === 204) return null;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    if (res.status === 401 && !path.startsWith("/api/auth/")) { state.user = null; location.hash = "#/login"; }
    let msg = data.detail;
    if (Array.isArray(msg)) msg = msg.map((d) => d.msg.replace(/^Value error, /, "")).join(", ");
    const err = new Error(msg || `Something went wrong (${res.status})`);
    err.status = res.status;
    throw err;
  }
  return data;
}

let wakingEl;
function showWaking(on) {
  if (on && !wakingEl) {
    wakingEl = document.createElement("div");
    wakingEl.className = "waking";
    wakingEl.innerHTML = "<span class='spinner'></span> Waking up WordPop… the first load after a break takes a moment.";
    document.body.appendChild(wakingEl);
  } else if (!on && wakingEl) { wakingEl.remove(); wakingEl = null; }
}

let toastTimer;
function toast(msg) {
  $toast.textContent = msg; $toast.hidden = false;
  clearTimeout(toastTimer); toastTimer = setTimeout(() => ($toast.hidden = true), 2800);
}

function route() {
  const [path, query = ""] = location.hash.replace(/^#/, "").split("?");
  return { path: path || "/words", params: new URLSearchParams(query) };
}

const isIOS = () => /iPhone|iPad|iPod/.test(navigator.userAgent) || (navigator.platform === "MacIntel" && navigator.maxTouchPoints > 1);
const isStandalone = () => window.matchMedia("(display-mode: standalone)").matches || navigator.standalone === true;
const isIOSNonSafari = () => isIOS() && /CriOS|FxiOS|EdgiOS|OPiOS/.test(navigator.userAgent);
const pushSupported = () => "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;

function catChips(selected = [], name = "cat") {
  if (!state.categories.length) return `<p class="muted small">No categories yet – <a href="#/categories">create one</a>.</p>`;
  return `<div class="chips">${state.categories.map((c) =>
    `<button type="button" class="chip" data-${name}="${c.id}" aria-pressed="${selected.includes(c.id)}">
      <span class="dot" style="background:${esc(c.color)}"></span>${esc(c.name)}</button>`).join("")}</div>`;
}
function bindToggleChips(root, attr) {
  root.querySelectorAll(`[data-${attr}]`).forEach((b) =>
    b.addEventListener("click", () => b.setAttribute("aria-pressed", b.getAttribute("aria-pressed") !== "true")));
}
const pressedIds = (root, attr) => [...root.querySelectorAll(`[data-${attr}][aria-pressed="true"]`)].map((b) => Number(b.dataset[attr]));

async function loadCategories() { state.categories = await api("/api/categories"); }

// ---------- install guide (iPhone) ----------
function installGuide() {
  if (isIOSNonSafari()) {
    return `<div class="card install"><h1>Open in Safari</h1>
      <p>On iPhone, notifications only work when WordPop is opened in <b>Safari</b>.</p>
      <p class="muted">Copy this page's link and paste it into Safari.</p>
      <button class="secondary" id="copy-link">Copy link</button></div>`;
  }
  return `<div class="card install">
    <img src="/icons/icon-192.png" width="72" height="72" alt="" style="border-radius:16px" />
    <h1>Install WordPop on your iPhone</h1>
    <p class="muted">It takes 20 seconds and lets WordPop send you word reminders.</p>
    <ol>
      <li>Tap the <b>Share</b> button <span class="share-ico">⬆</span> at the bottom of Safari.</li>
      <li>Scroll down and tap <b>Add to Home Screen</b>, then <b>Add</b>.</li>
      <li>Open <b>WordPop</b> from your Home Screen and sign in there.</li>
    </ol>
    <p class="small muted">Tip: install first, then sign in inside the installed app – the app and Safari keep separate logins.</p>
    <button class="ghost" id="skip-install">Continue in the browser for now</button>
  </div>`;
}

// ---------- screens ----------
const screens = {};

screens["/login"] = async () => {
  if (isIOS() && !isStandalone() && !state.installDismissed) {
    $view.innerHTML = installGuide();
    document.getElementById("skip-install")?.addEventListener("click", () => {
      state.installDismissed = "1"; sessionStorageSet("installDismissed", "1"); render();
    });
    document.getElementById("copy-link")?.addEventListener("click", async () => {
      await navigator.clipboard.writeText(location.origin); toast("Link copied");
    });
    return;
  }
  let mode = sessionStorageGet("authMode") || "signup";
  const draw = () => {
    $view.innerHTML = `
      <div class="card stack">
        <h1>${mode === "signup" ? "Create your account" : "Welcome back"}</h1>
        <p class="muted">${mode === "signup" ? "Save words, phrases, quotes or poems in any language, and get reminders until you remember them." : "Sign in to see your words."}</p>
        <form id="auth" class="stack">
          <div><label for="email">Email</label><input id="email" type="email" autocomplete="email" required /></div>
          <div><label for="pw">Password</label>
            <input id="pw" type="password" minlength="8" required autocomplete="${mode === "signup" ? "new-password" : "current-password"}" />
            ${mode === "signup" ? '<p class="small muted">At least 8 characters.</p>' : ""}</div>
          ${mode === "login" ? '<p class="small" style="margin:0;text-align:right"><a href="#/forgot">Forgot password?</a></p>' : ""}
          <p class="error" id="err" hidden></p>
          <button class="block" type="submit">${mode === "signup" ? "Create account" : "Sign in"}</button>
        </form>
        <p class="center small">${mode === "signup" ? "Already have an account?" : "New here?"}
          <a href="#" id="switch">${mode === "signup" ? "Sign in" : "Create an account"}</a></p>
        <p class="center small muted"><a href="/privacy.html">Privacy</a></p>
      </div>`;
    document.getElementById("switch").onclick = (e) => {
      e.preventDefault(); mode = mode === "signup" ? "login" : "signup"; sessionStorageSet("authMode", mode); draw();
    };
    document.getElementById("auth").onsubmit = async (e) => {
      e.preventDefault();
      const err = document.getElementById("err"); err.hidden = true;
      const body = { email: email.value.trim(), password: pw.value };
      if (mode === "signup") body.timezone = Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
      try {
        state.user = await api(`/api/auth/${mode}`, { method: "POST", body });
        await loadCategories();
        location.hash = mode === "signup" ? "#/welcome" : "#/words";
      } catch (ex) {
        err.innerHTML = esc(ex.message) + (mode === "signup" && /already exists/.test(ex.message)
          ? ' – <a href="#" id="to-login">sign in</a> or <a href="#/forgot">reset your password</a>.' : "");
        err.hidden = false;
        document.getElementById("to-login")?.addEventListener("click", (e2) => {
          e2.preventDefault(); mode = "login"; sessionStorageSet("authMode", mode); draw(); email.value = body.email;
        });
      }
    };
  };
  draw();
};

screens["/forgot"] = async () => {
  $view.innerHTML = `
    <div class="card stack">
      <h1>Forgot your password?</h1>
      <p class="muted">Enter the email you signed up with. We'll send you a link to choose a new password.</p>
      <form id="forgot" class="stack">
        <div><label for="f-email">Email</label><input id="f-email" type="email" autocomplete="email" required /></div>
        <p class="error" id="err" hidden></p>
        <button class="block" type="submit">Send reset link</button>
      </form>
      <p class="center small"><a href="#/login">← Back to sign in</a></p>
    </div>`;
  document.getElementById("forgot").onsubmit = async (e) => {
    e.preventDefault();
    const btn = e.submitter; btn.disabled = true; btn.textContent = "Sending…";
    try {
      const r = await api("/api/auth/forgot-password", { method: "POST", body: { email: document.getElementById("f-email").value.trim() } });
      $view.innerHTML = `<div class="card stack center">
        <h1>Check your email 📬</h1>
        <p>${esc(r.message)}</p>
        <p class="small muted">The link expires in 1 hour. Not there? Check your spam folder, or try again in a few minutes.</p>
        <a href="#/login">← Back to sign in</a></div>`;
    } catch (ex) {
      const err = document.getElementById("err"); err.textContent = ex.message; err.hidden = false;
      btn.disabled = false; btn.textContent = "Send reset link";
    }
  };
};

screens["/reset"] = async ({ params }) => {
  const token = params.get("token");
  if (!token) { location.hash = "#/forgot"; return; }
  $view.innerHTML = `
    <div class="card stack">
      <h1>Choose a new password</h1>
      <form id="reset" class="stack">
        <div><label for="r-pw">New password</label><input id="r-pw" type="password" minlength="8" required autocomplete="new-password" />
          <p class="small muted">At least 8 characters.</p></div>
        <div><label for="r-pw2">Repeat new password</label><input id="r-pw2" type="password" minlength="8" required autocomplete="new-password" /></div>
        <p class="error" id="err" hidden></p>
        <button class="block" type="submit">Save new password</button>
      </form>
    </div>`;
  document.getElementById("reset").onsubmit = async (e) => {
    e.preventDefault();
    const err = document.getElementById("err"); err.hidden = true;
    const pw = document.getElementById("r-pw").value, pw2 = document.getElementById("r-pw2").value;
    if (pw !== pw2) { err.textContent = "The two passwords don't match."; err.hidden = false; return; }
    try {
      state.user = await api("/api/auth/reset-password", { method: "POST", body: { token, password: pw } });
      toast("Password changed ✓ You're signed in.");
      location.hash = "#/words";
    } catch (ex) {
      err.innerHTML = `${esc(ex.message)} <a href="#/forgot">Send a new link</a>`; err.hidden = false;
    }
  };
};

screens["/welcome"] = async () => {
  const lists = await api("/api/starter-lists");
  $view.innerHTML = `
    <h1>Let's get you started 👋</h1>
    <div class="card stack">
      <h2>Pick some categories</h2>
      <p class="muted small">Categories keep your entries organised. They start empty – you add your own words, phrases and quotes. You can create more anytime.</p>
      ${starterListHtml(lists)}
    </div>
    <a class="btn block" href="#/words">Continue</a>`;
  bindStarterButtons();
};

function starterListHtml(lists) {
  return lists.map((l) => `
    <div class="row between">
      <div class="grow"><span class="dot" style="background:${esc(l.color)}"></span> <b>${esc(l.name)}</b><br />
        <span class="small muted">${esc(l.description)}</span></div>
      <button class="secondary small" data-import="${esc(l.key)}">Add</button>
    </div>`).join("");
}
function bindStarterButtons() {
  $view.querySelectorAll("[data-import]").forEach((b) => b.addEventListener("click", async () => {
    b.disabled = true;
    try {
      const r = await api(`/api/starter-lists/${b.dataset.import}/import`, { method: "POST" });
      b.textContent = "Added ✓"; toast(r.created ? `“${r.name}” category added` : `You already have “${r.name}”`); await loadCategories();
    } catch (e) { b.disabled = false; toast(e.message); }
  }));
}

screens["/words"] = async ({ params }) => {
  await loadCategories();
  const filter = params.get("category");
  const words = await api(`/api/words${filter ? `?category_id=${encodeURIComponent(filter)}` : ""}`);
  $view.innerHTML = `
    <div class="card">
      <h2>Add a word, phrase or quote</h2>
      <form id="add" class="stack">
        <div class="row" style="align-items:flex-start"><textarea id="w-text" class="grow" rows="2" maxlength="500" placeholder="A word, phrase, sentence, quote or short poem – in any language" required autocomplete="off" autocapitalize="sentences" style="width:auto;min-height:48px"></textarea>
          <button type="button" class="secondary" id="lookup" title="English dictionary">Look up</button></div>
        <div><label for="w-meaning">Meaning or note <span class="muted small">(optional – English words can be filled automatically)</span></label>
          <textarea id="w-meaning" rows="2"></textarea></div>
        <div><label for="w-example">Example <span class="muted small">(optional)</span></label><input id="w-example" /></div>
        <div><label>Categories</label>${catChips([], "newcat")}</div>
        <p class="error" id="add-err" hidden></p>
        <button class="block" type="submit">Save word</button>
      </form>
    </div>
    <div id="notif-ask"></div>
    <div class="card">
      <div class="row between"><h2>Your words <span class="muted small">(${words.length})</span></h2></div>
      <div class="chips scroll-x" style="margin-bottom:8px">
        <a class="chip" aria-pressed="${!filter}" href="#/words">All</a>
        ${state.categories.map((c) => `<a class="chip" aria-pressed="${String(c.id) === filter}" href="#/words?category=${c.id}">
          <span class="dot" style="background:${esc(c.color)}"></span>${esc(c.name)}</a>`).join("")}
      </div>
      <input id="search" placeholder="Search…" type="search" style="margin-bottom:8px" />
      <div id="list">${words.length ? words.map(wordItem).join("") : `<p class="muted center">No words yet. Add your first one above.</p>`}</div>
    </div>`;

  bindToggleChips($view, "newcat");
  const text = document.getElementById("w-text"), meaning = document.getElementById("w-meaning"), example = document.getElementById("w-example");

  document.getElementById("lookup").onclick = async () => {
    if (!text.value.trim()) return text.focus();
    try {
      const r = await api(`/api/dictionary/${encodeURIComponent(text.value.trim())}`);
      meaning.value = r.meaning; if (!example.value) example.value = r.example || "";
      toast(r.phonetic ? `Found it ${r.phonetic}` : "Found it");
    } catch (e) { toast(e.message); }
  };

  document.getElementById("add").onsubmit = async (e) => {
    e.preventDefault();
    const err = document.getElementById("add-err"); err.hidden = true;
    const btn = e.submitter; btn.disabled = true; btn.textContent = "Saving…";
    try {
      await api("/api/words", { method: "POST", body: {
        text: text.value, meaning: meaning.value, example: example.value, category_ids: pressedIds($view, "newcat") } });
      toast("Saved ✓");
      const firstWord = words.length === 0;
      await screens["/words"]({ params });
      if (firstWord) maybeAskForNotifications();
    } catch (ex) { err.textContent = ex.message; err.hidden = false; btn.disabled = false; btn.textContent = "Save word"; }
  };

  document.getElementById("search").oninput = (e) => {
    const q = e.target.value.toLowerCase();
    $view.querySelectorAll(".word-item").forEach((el) => (el.hidden = !el.dataset.text.includes(q)));
  };
  bindWordItems(words, params);
  if (words.length) maybeAskForNotifications();
};

function boxLabel(box) { return box >= 5 ? "⭐ mastered" : box === 0 ? "new" : `level ${box}/5`; }

// ---------- listening ----------
// English is read by a Canadian voice when the device has one (the most natural-sounding
// first), or by the voice the person picked in Settings. Other languages use the device's
// voice for that language. Voices differ per device, so the choice is kept on the device.
const canSpeak = "speechSynthesis" in window;
const VOICE_KEY = "wordpop.voice";
const savedVoiceName = () => { try { return localStorage.getItem(VOICE_KEY) || ""; } catch { return ""; } };
const voices = () => (canSpeak ? speechSynthesis.getVoices() : []);
const norm = (lang) => (lang || "").replace("_", "-");
const NATURAL = /natural|neural|enhanced|premium|online|google/i;

// Higher is better: Canadian, then US (closest accent), then other English; natural voices first.
function englishRank(v) {
  const lang = norm(v.lang);
  return (lang === "en-CA" ? 100 : lang === "en-US" ? 50 : 10) + (NATURAL.test(v.name) ? 20 : 0) + (v.default ? 1 : 0);
}
function englishVoices() {
  return voices().filter((v) => norm(v.lang).startsWith("en")).sort((a, b) => englishRank(b) - englishRank(a));
}
function pickVoice(lang) {
  const base = lang.split("-")[0];
  if (base === "en") {
    const saved = savedVoiceName() && englishVoices().find((v) => v.name === savedVoiceName());
    return saved || englishVoices()[0];
  }
  const all = voices();
  return all.find((v) => norm(v.lang) === lang && NATURAL.test(v.name)) || all.find((v) => norm(v.lang) === lang) ||
    all.find((v) => norm(v.lang).startsWith(base));
}
// Speak English ourselves (instead of the dictionary's British/US recording) when a Canadian
// voice exists or the person chose a voice.
const preferVoiceForEnglish = () => Boolean(savedVoiceName()) || englishVoices().some((v) => norm(v.lang) === "en-CA");

function speak(text, lang) {
  const synth = window.speechSynthesis;
  synth.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = lang || "en-US";
  const voice = pickVoice(u.lang);
  if (voice) { u.voice = voice; u.lang = voice.lang; }
  u.rate = 0.92;
  synth.speak(u);
}
function exampleHtml(w, attr) {
  if (!w.example) return "";
  const btn = canSpeak ? ` <button class="ghost small say" ${attr} aria-label="Listen to the example">🔊</button>` : "";
  return `<i dir="auto">“${esc(w.example)}”</i>${btn}`;
}
function listen(w) {
  const english = (w.lang || "en").startsWith("en");
  if (w.audio_url && !(canSpeak && english && preferVoiceForEnglish())) {
    return new Audio(w.audio_url).play().catch(() => canSpeak && speak(w.text, w.lang));
  }
  if (canSpeak) speak(w.text, w.lang);
}
const canListen = (w) => Boolean(w.audio_url) || canSpeak;

const ACCENTS = { "en-CA": "Canadian", "en-US": "American", "en-GB": "British", "en-AU": "Australian", "en-IE": "Irish",
  "en-IN": "Indian", "en-NZ": "New Zealand", "en-ZA": "South African" };
function bindVoicePicker() {
  const select = document.getElementById("voice"), hint = document.getElementById("voice-hint");
  const fill = () => {
    const list = englishVoices(), saved = savedVoiceName();
    select.innerHTML = `<option value="">Automatic${list[0] ? ` – ${esc(list[0].name)}` : ""}</option>` + list.map((v) =>
      `<option value="${esc(v.name)}" ${v.name === saved ? "selected" : ""}>${esc(v.name)} (${ACCENTS[norm(v.lang)] || esc(v.lang)})</option>`).join("");
    hint.textContent = !list.length ? "Loading voices…" : list.some((v) => norm(v.lang) === "en-CA") ? ""
      : "No Canadian voice on this device yet, so the closest one is used. On iPhone: Settings → Accessibility → Spoken Content → Voices → English. On Android: Settings → Text-to-speech → install voice data.";
  };
  fill();
  speechSynthesis.onvoiceschanged = fill; // (replaces the previous visit's handler)
  select.onchange = () => {
    try { select.value ? localStorage.setItem(VOICE_KEY, select.value) : localStorage.removeItem(VOICE_KEY); } catch { /* private mode */ }
    speak("Hi! This is how your words will sound.", "en-US");
  };
  document.getElementById("voice-test").onclick = () => speak("Hi! This is how your words will sound.", "en-US");
}
if (canSpeak) speechSynthesis.getVoices(); // starts loading the voice list early (Chrome)

function wordItem(w) {
  return `<details class="word-item" data-id="${w.id}" data-text="${esc(w.text.toLowerCase())}">
    <summary><span class="word-head"><span class="word-text" dir="auto">${esc(w.text)}</span> <span class="muted small phonetic">${esc(w.phonetic)}</span></span>
      <span class="box-badge">${boxLabel(w.box)}</span></summary>
    <div class="stack card-back">
      ${w.meaning ? `<div class="keep-lines" dir="auto">${esc(w.meaning)}</div>` : ""}
      ${w.example ? `<div class="muted">${exampleHtml(w, `data-say-example="${w.id}"`)}</div>` : ""}
      ${w.categories.length ? `<div class="chips">${w.categories.map((c) => `<span class="chip"><span class="dot" style="background:${esc(c.color)}"></span>${esc(c.name)}</span>`).join("")}</div>` : ""}
      <div class="row card-actions">
        ${canListen(w) ? `<button class="ghost small" data-listen="${w.id}">🔊 Listen</button>` : ""}
        <button class="ghost small" data-edit="${w.id}">Edit</button>
        <button class="danger small" data-del="${w.id}">Delete</button>
      </div>
    </div></details>`;
}

function bindWordItems(words, params) {
  $view.querySelectorAll("[data-listen]").forEach((b) => (b.onclick = () => listen(words.find((x) => x.id === Number(b.dataset.listen)))));
  $view.querySelectorAll("[data-say-example]").forEach((b) => (b.onclick = () => {
    const w = words.find((x) => x.id === Number(b.dataset.sayExample)); speak(w.example, w.lang);
  }));
  $view.querySelectorAll("[data-del]").forEach((b) => (b.onclick = async () => {
    if (!confirmInline(b)) return;
    await api(`/api/words/${b.dataset.del}`, { method: "DELETE" }); toast("Deleted"); screens["/words"]({ params });
  }));
  $view.querySelectorAll("[data-edit]").forEach((b) => (b.onclick = () => {
    const w = words.find((x) => x.id === Number(b.dataset.edit));
    const box = b.closest(".stack");
    box.innerHTML = `
      <div><label>Text</label><textarea data-f="text" rows="2" maxlength="500">${esc(w.text)}</textarea></div>
      <div><label>Meaning or note</label><textarea data-f="meaning">${esc(w.meaning)}</textarea></div>
      <div><label>Example</label><input data-f="example" value="${esc(w.example)}" /></div>
      <div><label>Categories</label>${catChips(w.categories.map((c) => c.id), "editcat")}</div>
      <div class="row"><button class="small" data-save>Save</button><button class="ghost small" data-cancel>Cancel</button></div>`;
    bindToggleChips(box, "editcat");
    box.querySelector("[data-cancel]").onclick = () => screens["/words"]({ params });
    box.querySelector("[data-save]").onclick = async () => {
      const f = (n) => box.querySelector(`[data-f="${n}"]`).value;
      try {
        await api(`/api/words/${w.id}`, { method: "PATCH", body: { text: f("text"), meaning: f("meaning"), example: f("example"), category_ids: pressedIds(box, "editcat") } });
        toast("Saved ✓"); screens["/words"]({ params });
      } catch (e) { toast(e.message); }
    };
  }));
}

// Two-tap delete instead of a blocking browser dialog.
function confirmInline(btn) {
  if (btn.dataset.armed) return true;
  btn.dataset.armed = "1"; const old = btn.textContent; btn.textContent = "Tap again to delete";
  setTimeout(() => { delete btn.dataset.armed; btn.textContent = old; }, 3000);
  return false;
}

screens["/categories"] = async () => {
  const [settings] = await Promise.all([api("/api/me/settings"), loadCategories()]);
  const colors = ["#4F46E5", "#DC2626", "#16A34A", "#D97706", "#0891B2", "#DB2777", "#7C3AED", "#475569"];
  $view.innerHTML = `
    <h1>Categories</h1>
    <div class="card">
      <h2>New category</h2>
      <form id="new-cat" class="stack">
        <input id="cat-name" placeholder="e.g. Spanish, Poems, Math, Motivation" required maxlength="60" />
        <div class="chips" id="colors">${colors.map((c, i) => `<button type="button" class="chip" data-color="${c}" aria-pressed="${i === 0}" aria-label="Color ${c}"><span class="dot" style="background:${c}"></span></button>`).join("")}</div>
        <button class="block">Create</button>
      </form>
    </div>
    <div class="card">
      <h2>Notifications per category</h2>
      <p class="small muted">Only entries in a switched-on category are sent as reminders. “No category” covers entries you haven't put in any category.</p>
      <div class="row between word-item">
        <span class="grow row"><span class="dot" style="background:transparent;border:1px dashed currentColor"></span><b>No category</b></span>
        <label class="switch" title="Notifications"><input type="checkbox" id="notify-uncategorized" ${settings.notify_uncategorized ? "checked" : ""} aria-label="Notifications for entries without a category" /><span></span></label>
      </div>
      ${state.categories.length ? state.categories.map((c) => `
        <div class="row between word-item">
          <a class="grow row" href="#/words?category=${c.id}" style="color:inherit;text-decoration:none">
            <span class="dot" style="background:${esc(c.color)}"></span><b>${esc(c.name)}</b>
            <span class="muted small">${c.word_count} ${c.word_count === 1 ? "entry" : "entries"}</span></a>
          <label class="switch" title="Notifications"><input type="checkbox" data-notify="${c.id}" ${c.notify ? "checked" : ""} aria-label="Notifications for ${esc(c.name)}" /><span></span></label>
          <button class="danger small" data-delcat="${c.id}" aria-label="Delete ${esc(c.name)}">✕</button>
        </div>`).join("") : `<p class="muted">No categories yet.</p>`}
    </div>`;

  const colorBtns = $view.querySelectorAll("[data-color]");
  colorBtns.forEach((b) => (b.onclick = () => colorBtns.forEach((x) => x.setAttribute("aria-pressed", x === b))));
  document.getElementById("new-cat").onsubmit = async (e) => {
    e.preventDefault();
    const color = $view.querySelector('[data-color][aria-pressed="true"]').dataset.color;
    try { await api("/api/categories", { method: "POST", body: { name: document.getElementById("cat-name").value, color } }); toast("Category created"); screens["/categories"](); }
    catch (ex) { toast(ex.message); }
  };
  document.getElementById("notify-uncategorized").onchange = async (e) => {
    await api("/api/me/settings", { method: "PUT", body: { notify_uncategorized: e.target.checked } });
    toast(e.target.checked ? "Reminders on for entries without a category" : "Reminders off for entries without a category");
  };
  $view.querySelectorAll("[data-notify]").forEach((i) => (i.onchange = async () => {
    await api(`/api/categories/${i.dataset.notify}`, { method: "PATCH", body: { notify: i.checked } });
    toast(i.checked ? "Reminders on" : "Reminders off for this category");
  }));
  $view.querySelectorAll("[data-delcat]").forEach((b) => (b.onclick = async () => {
    if (!confirmInline(b)) return;
    await api(`/api/categories/${b.dataset.delcat}`, { method: "DELETE" }); toast("Category deleted (words kept)"); screens["/categories"]();
  }));
};

screens["/quiz"] = async ({ params }) => {
  await loadCategories();
  let category = params.get("category") || "";
  let wordId = params.get("word");
  let lastId = null, done = 0;

  const next = async () => {
    const q = new URLSearchParams();
    if (category) q.set("category_id", category);
    if (wordId) { q.set("word_id", wordId); wordId = null; }
    if (lastId) q.set("exclude_id", lastId);
    const w = await api(`/api/quiz/next?${q}`);
    draw(w);
  };

  const draw = (w) => {
    $view.innerHTML = `
      <div class="row between"><h1>Quiz</h1>
        <select id="qcat" style="width:auto"><option value="">All words</option>
          ${state.categories.map((c) => `<option value="${c.id}" ${String(c.id) === category ? "selected" : ""}>${esc(c.name)}</option>`).join("")}</select></div>
      ${!w ? `<div class="card center pad"><p>No words to practise yet.</p><a class="btn" href="#/words">Add words</a></div>` : `
      <div class="card quiz-card">
        <p class="muted small">${done ? `${done} reviewed this session · ` : ""}${boxLabel(w.box)}</p>
        <p class="quiz-word${w.text.length > 40 ? " long" : ""}" dir="auto">${esc(w.text)}</p>
        <p class="muted">${esc(w.phonetic)} ${canListen(w) ? `<button class="ghost small" id="listen" aria-label="Listen">🔊</button>` : ""}</p>
        <div id="answer" hidden>
          ${w.meaning ? `<p class="quiz-meaning" dir="auto">${esc(w.meaning)}</p>` : `<p class="muted small">No meaning or note added – did you remember it? You can add one with “Edit” on the Words page.</p>`}
          ${w.example ? `<p class="muted">${exampleHtml(w, 'id="say-example"')}</p>` : ""}
          <div class="quiz-actions">
            <button class="bad" id="forgot">✗ Forgot</button>
            <button class="good" id="knew">✓ I knew it</button>
          </div>
        </div>
        <button class="block brown" id="reveal" style="margin-top:1rem">Show meaning</button>
      </div>
      <p class="center small muted">Think of the meaning first, then check. Words you forget come back sooner.</p>`}`;
    document.getElementById("qcat").onchange = (e) => { category = e.target.value; lastId = null; next(); };
    if (!w) return;
    document.getElementById("listen")?.addEventListener("click", () => listen(w));
    document.getElementById("say-example")?.addEventListener("click", () => speak(w.example, w.lang));
    document.getElementById("reveal").onclick = (e) => { e.target.hidden = true; document.getElementById("answer").hidden = false; };
    const answer = async (knew) => {
      await api("/api/quiz/answer", { method: "POST", body: { word_id: w.id, knew } });
      done++; lastId = w.id; next();
    };
    document.getElementById("knew").onclick = () => answer(true);
    document.getElementById("forgot").onclick = () => answer(false);
  };
  await next();
};

screens["/progress"] = async () => {
  const p = await api("/api/me/progress");
  const max = Math.max(1, ...p.last_7_days.map((d) => d.reviews));
  const dayName = (iso) => new Date(iso + "T12:00:00").toLocaleDateString(undefined, { weekday: "short" });
  $view.innerHTML = `
    <h1>Your progress</h1>
    <div class="tiles">
      <div class="tile"><div class="num">${p.streak_days} 🔥</div><div class="lbl">day streak</div></div>
      <div class="tile"><div class="num">${p.mastered}</div><div class="lbl">words mastered</div></div>
      <div class="tile"><div class="num">${p.total_words}</div><div class="lbl">words saved</div></div>
      <div class="tile"><div class="num">${p.accuracy ?? "–"}${p.accuracy != null ? "%" : ""}</div><div class="lbl">answers correct</div></div>
    </div>
    <div class="card">
      <h2>Reviews in the last 7 days</h2>
      <div class="bars" role="img" aria-label="Reviews per day: ${p.last_7_days.map((d) => `${dayName(d.date)} ${d.reviews}`).join(", ")}">
        ${p.last_7_days.map((d) => `<div class="bar-col" tabindex="0"><span class="tip">${dayName(d.date)}: ${d.reviews} reviews</span>
          <div class="bar" style="height:${(d.reviews / max) * 100}%"></div></div>`).join("")}
      </div>
      <div class="bar-labels">${p.last_7_days.map((d) => `<span>${dayName(d.date)}</span>`).join("")}</div>
    </div>
    <div class="card">
      <h2>Where your words are</h2>
      <table class="simple">
        <tr><td>New</td><td>${p.new}</td></tr>
        <tr><td>Learning</td><td>${p.learning}</td></tr>
        <tr><td>Mastered ⭐</td><td>${p.mastered}</td></tr>
        <tr><td>Due for review now</td><td>${p.due_now}</td></tr>
      </table>
      ${p.due_now ? `<a class="btn block" href="#/quiz" style="margin-top:12px">Review ${p.due_now} due words</a>` : ""}
    </div>
    ${p.hardest.length ? `<div class="card"><h2>Hardest words</h2><table class="simple">
      ${p.hardest.map((h) => `<tr><td>${esc(h.text)}</td><td>forgot ${h.times_wrong}×</td></tr>`).join("")}</table></div>` : ""}`;
};

screens["/settings"] = async () => {
  const [s, lists] = await Promise.all([api("/api/me/settings"), api("/api/starter-lists")]);
  const zones = (Intl.supportedValuesOf?.("timeZone") ?? [s.timezone]);
  if (!zones.includes(s.timezone)) zones.unshift(s.timezone);
  const hours = (from, to) => Array.from({ length: to - from + 1 }, (_, i) => i + from);
  const fmtH = (h) => (h === 24 ? "Midnight" : new Date(2000, 0, 1, h).toLocaleTimeString([], { hour: "numeric" }));
  const dayNames = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const paused = s.paused_until && new Date(s.paused_until) > new Date();

  $view.innerHTML = `
    <h1>Settings</h1>
    <div class="card stack">
      <h2>Notifications</h2>
      <div id="push-status"></div>
    </div>
    <div class="card stack">
      <h2>When to remind me</h2>
      <div><label for="every">How often</label><select id="every">
        ${[[30, "Every 30 minutes"], [60, "Every hour"], [120, "Every 2 hours"], [180, "Every 3 hours"], [240, "Every 4 hours"], [360, "3 times a day"], [720, "Twice a day"], [1440, "Once a day"]]
          .map(([v, l]) => `<option value="${v}" ${v === s.notify_every_minutes ? "selected" : ""}>${l}</option>`).join("")}
        ${[30, 60, 120, 180, 240, 360, 720, 1440].includes(s.notify_every_minutes) ? "" : `<option selected value="${s.notify_every_minutes}">Every ${s.notify_every_minutes} min</option>`}
      </select></div>
      <div class="row">
        <div class="grow"><label for="start">From</label><select id="start">${hours(0, 23).map((h) => `<option value="${h}" ${h === s.active_start_hour ? "selected" : ""}>${fmtH(h)}</option>`).join("")}</select></div>
        <div class="grow"><label for="end">Until</label><select id="end">${hours(1, 24).map((h) => `<option value="${h}" ${h === s.active_end_hour ? "selected" : ""}>${fmtH(h)}</option>`).join("")}</select></div>
      </div>
      <div><label>Days</label><div class="days">${dayNames.map((d, i) => `<button type="button" class="chip" data-day="${i}" aria-pressed="${s.active_days.includes(String(i))}">${d}</button>`).join("")}</div></div>
      <div><label for="limit">Maximum per day</label><select id="limit">${[3, 5, 8, 10, 15, 20, 30].concat(s.daily_limit).filter((v, i, a) => a.indexOf(v) === i).sort((a, b) => a - b)
        .map((v) => `<option ${v === s.daily_limit ? "selected" : ""}>${v}</option>`).join("")}</select></div>
      <div><label for="tz">Time zone</label><select id="tz">${zones.map((z) => `<option ${z === s.timezone ? "selected" : ""}>${esc(z)}</option>`).join("")}</select></div>
      <p class="error" id="set-err" hidden></p>
      <button class="block" id="save-settings">Save</button>
    </div>
    <div class="card stack">
      <h2>Take a break</h2>
      <p class="small muted">${paused ? `Paused until ${new Date(s.paused_until).toLocaleString([], { weekday: "short", hour: "numeric", minute: "2-digit" })}.` : "Pause reminders during exams, trips or busy days."}</p>
      <div class="row">${paused ? `<button class="secondary" data-pause="0">Resume now</button>` :
        `<button class="ghost" data-pause="3">3 hours</button><button class="ghost" data-pause="24">1 day</button><button class="ghost" data-pause="168">1 week</button>`}</div>
    </div>
    ${canSpeak ? `<div class="card stack">
      <h2>Voice</h2>
      <p class="small muted">The voice that reads English entries and examples on this device. “Automatic” picks a Canadian voice when your phone has one.</p>
      <div class="row"><select id="voice" class="grow" style="width:auto" aria-label="Voice"></select>
        <button class="ghost" id="voice-test" type="button">🔊 Test</button></div>
      <p class="small muted" id="voice-hint"></p>
    </div>` : ""}
    <div class="card stack"><h2>Ready-made categories</h2><p class="small muted">Add an empty category with one tap, then fill it with your own entries.</p>${starterListHtml(lists)}</div>
    <div class="card stack">
      <h2>Account</h2>
      <p class="small muted">Signed in as ${esc(state.user.email)}</p>
      ${state.user.is_admin ? `<a class="btn secondary block" href="#/admin">📊 App statistics (admin)</a>` : ""}
      <button class="ghost block" id="logout">Sign out</button>
      <button class="danger block" id="delete-account">Delete my account and all data</button>
      <p class="center small"><a href="/privacy.html">Privacy</a></p>
    </div>`;

  bindToggleChips($view, "day");
  bindStarterButtons();
  renderPushStatus();
  if (canSpeak) bindVoicePicker();

  document.getElementById("save-settings").onclick = async () => {
    const err = document.getElementById("set-err"); err.hidden = true;
    const start = Number(document.getElementById("start").value), end = Number(document.getElementById("end").value);
    if (end <= start) { err.textContent = "“Until” must be later than “From”."; err.hidden = false; return; }
    try {
      await api("/api/me/settings", { method: "PUT", body: {
        notify_every_minutes: Number(document.getElementById("every").value), active_start_hour: start, active_end_hour: end,
        active_days: pressedIds($view, "day").sort().join(""), daily_limit: Number(document.getElementById("limit").value),
        timezone: document.getElementById("tz").value } });
      toast("Settings saved ✓");
    } catch (e) { err.textContent = e.message; err.hidden = false; }
  };
  $view.querySelectorAll("[data-pause]").forEach((b) => (b.onclick = async () => {
    await api("/api/me/pause", { method: "POST", body: { hours: Number(b.dataset.pause) } });
    toast(b.dataset.pause === "0" ? "Reminders resumed" : "Reminders paused"); screens["/settings"]();
  }));
  document.getElementById("logout").onclick = async () => { await api("/api/auth/logout", { method: "POST" }); state.user = null; location.hash = "#/login"; };
  document.getElementById("delete-account").onclick = async (e) => {
    const b = e.currentTarget;
    if (!b.dataset.armed) { b.dataset.armed = "1"; b.textContent = "Tap again to permanently delete everything"; return; }
    await api("/api/auth/me", { method: "DELETE" }); state.user = null; toast("Account deleted"); location.hash = "#/login";
  };
};

screens["/admin"] = async () => {
  const s = await api("/api/admin/stats");
  const pct = (v) => (v == null ? "not enough data yet" : `${v}%`);
  $view.innerHTML = `
    <h1>App statistics</h1>
    <div class="tiles">
      <div class="tile"><div class="num">${s.users_total}</div><div class="lbl">users</div></div>
      <div class="tile"><div class="num">${s.active_last_7_days}</div><div class="lbl">active last 7 days</div></div>
    </div>
    <div class="card"><table class="simple">
      <tr><td>Sign-ups, last 7 days</td><td>${s.signups_last_7_days}</td></tr>
      <tr><td>Users with notifications on</td><td>${s.users_with_notifications}</td></tr>
      <tr><td>Users with 10+ words</td><td>${s.users_with_10_plus_words}</td></tr>
      <tr><td>Average words per user</td><td>${s.avg_words_per_user}</td></tr>
      <tr><td>Quiz answers, last 7 days</td><td>${s.reviews_last_7_days}</td></tr>
      <tr><td>Came back after 1 day</td><td>${pct(s.retention_day_1_pct)}</td></tr>
      <tr><td>Came back after 7 days</td><td>${pct(s.retention_day_7_pct)}</td></tr>
      <tr><td>Came back after 28 days</td><td>${pct(s.retention_day_28_pct)}</td></tr>
    </table></div>
    <a href="#/settings">← Back to settings</a>`;
};

// ---------- push notifications ----------
function b64ToUint8(b64) {
  const pad = "=".repeat((4 - (b64.length % 4)) % 4);
  const raw = atob((b64 + pad).replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from(raw, (c) => c.charCodeAt(0));
}

async function currentSubscription() {
  if (!pushSupported()) return null;
  const reg = await navigator.serviceWorker.ready;
  return reg.pushManager.getSubscription();
}

async function enablePush() {
  const permission = await Notification.requestPermission();
  if (permission !== "granted") { toast("Notifications were not allowed"); return false; }
  const { key } = await api("/api/push/public-key");
  const reg = await navigator.serviceWorker.ready;
  const sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b64ToUint8(key) });
  await api("/api/push/subscribe", { method: "POST", body: sub.toJSON() });
  toast("Notifications on ✓");
  return true;
}

async function renderPushStatus() {
  const el = document.getElementById("push-status"); if (!el) return;
  if (!pushSupported()) {
    el.innerHTML = isIOS() && !isStandalone()
      ? `<p>To get reminders on iPhone, add WordPop to your Home Screen first: tap <span class="share-ico">⬆</span> <b>Share</b> → <b>Add to Home Screen</b>, then open it from there.</p>`
      : `<p class="muted">This browser doesn't support notifications.</p>`;
    return;
  }
  const sub = await currentSubscription();
  if (Notification.permission === "denied") {
    el.innerHTML = `<p>Notifications are blocked. Turn them on in your phone's <b>Settings → Notifications → WordPop</b>.</p>`;
  } else if (sub) {
    el.innerHTML = `<p>✅ Notifications are on for this device.</p>
      <div class="row"><button class="secondary" id="test-push">Send me a word now</button><button class="ghost" id="off-push">Turn off</button></div>`;
    document.getElementById("test-push").onclick = async () => {
      try { const r = await api("/api/push/test", { method: "POST" }); toast(r.delivered ? "Sent – check your notifications" : "Couldn't deliver, try turning notifications off and on"); }
      catch (e) { toast(e.message); }
    };
    document.getElementById("off-push").onclick = async () => {
      await api("/api/push/unsubscribe", { method: "POST", body: sub.toJSON() }); await sub.unsubscribe(); renderPushStatus();
    };
  } else {
    el.innerHTML = `<p class="muted">Get your words as reminders on this device.</p><button class="block" id="on-push">Turn on notifications</button>`;
    document.getElementById("on-push").onclick = async () => { try { await enablePush(); } catch (e) { toast(e.message); } renderPushStatus(); };
  }
}

// Ask at a helpful moment (after adding a word), never on first load.
async function maybeAskForNotifications() {
  const box = document.getElementById("notif-ask");
  if (!box || !pushSupported() || Notification.permission !== "default" || sessionStorageGet("askedPush")) return;
  if (await currentSubscription()) return;
  box.innerHTML = `<div class="card notice stack"><b>🔔 Want reminders for your words?</b>
    <p class="small" style="margin:0">Allow notifications and WordPop will remind you of your words during the day. You choose how often in Settings.</p>
    <div class="row"><button id="ask-yes">Allow notifications</button><button class="ghost" id="ask-no">Not now</button></div></div>`;
  document.getElementById("ask-yes").onclick = async () => { try { await enablePush(); } catch (e) { toast(e.message); } box.innerHTML = ""; };
  document.getElementById("ask-no").onclick = () => { sessionStorageSet("askedPush", "1"); box.innerHTML = ""; };
}

// ---------- router ----------
async function render() {
  const r = route();
  const publicRoute = ["/login", "/forgot", "/reset"].includes(r.path);
  if (!state.user && !publicRoute) {
    try { state.user = await api("/api/auth/me"); }
    catch (e) {
      if (e.status === 401) { location.hash = "#/login"; return; }
      // Server unreachable: keep the user signed in and offer a retry instead of the login page.
      $view.innerHTML = `<div class="card center pad"><p>${esc(e.message)}</p><button onclick="location.reload()">Try again</button></div>`;
      return;
    }
  }
  if (state.user && r.path === "/login") { location.hash = "#/words"; return; }
  $tabbar.hidden = !state.user || publicRoute;
  $tabbar.querySelectorAll("a").forEach((a) => a.classList.toggle("active", r.path === `/${a.dataset.tab}`));
  const screen = screens[r.path] || screens["/words"];
  try { await screen(r); }
  catch (e) { $view.innerHTML = `<div class="card center pad"><p class="error">${esc(e.message)}</p><button onclick="location.reload()">Try again</button></div>`; }
  window.scrollTo(0, 0);
}

window.addEventListener("hashchange", render);
if ("serviceWorker" in navigator) {
  // When a new version of the app finishes installing, it takes over this page; reload once
  // so the person sees the update right away instead of on the next launch.
  const hadController = Boolean(navigator.serviceWorker.controller);
  let reloading = false;
  navigator.serviceWorker.addEventListener("controllerchange", () => {
    if (!hadController || reloading) return;
    reloading = true;
    // Never throw away something being typed: then reload when the app is next put away.
    const typing = ["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement?.tagName);
    if (!typing) location.reload();
    else document.addEventListener("visibilitychange", () => document.visibilityState === "hidden" && location.reload());
  });
  navigator.serviceWorker.register("/sw.js").then((reg) => reg.update()).catch(() => {});
  // A PWA can stay open in the background for days: look for an update whenever it comes back.
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") navigator.serviceWorker.getRegistration().then((r) => r?.update()).catch(() => {});
  });
}
// When a notification is tapped while the app is open, the service worker asks us to navigate.
navigator.serviceWorker?.addEventListener("message", (e) => { if (e.data?.type === "navigate") location.hash = e.data.url.replace(/^\/?/, ""); });
render();
