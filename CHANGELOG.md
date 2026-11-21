# Changelog

## [Unreleased]
### Added
- "No category" switch on the Categories page: entries without a category can now be switched off too, so turning on a single category sends only that category's entries (before, uncategorized entries were always sent)
- Only the entry text is required when adding a word, phrase or quote; "Meaning or note" and "Example" are optional (English entries are still filled from the dictionary when possible)
- Phone keyboards start the "Add a word, phrase or quote" box with a capital letter
- **Listen** on every entry: dictionary recordings when available, otherwise the phone's own voice in the entry's language (Chinese, Hindi, Japanese, ... from the script; French, Spanish, German, ... from the category name)
- 🔊 next to every example (in the list and in the quiz) reads the example aloud
- Pronunciation line for every English entry, phrases and sentences included (offline IPA from the CMU Pronouncing Dictionary), and pinyin with tone marks for Chinese; existing entries get it automatically
- Opening an entry in the list shows it as an amber flashcard: the entry on the front, a fold line, then the meaning

- Canadian English voice: English entries and examples are read by a Canadian voice when the device has one (natural-sounding voices first, then American); a new **Voice** setting lets each device pick any English voice, and dictionary recordings prefer the North American one
- **Select and delete several entries at once** on the Words page: Select → tick entries (or "Select all", which follows the current search and category) → Delete
- **Natural voices**: four human-sounding English voices made on the server with Azure AI Speech – Clara (Canadian woman, default), Liam (Canadian man), Ava (American woman) and Andrew (American man). Pick one in Settings → Voice (▶ plays a sample); it reads entries and examples on every device. Each recording is made once and stored, so repeat listens are instant and free. The phone's own voice remains available and is the automatic fallback
- Selecting entries: tapping the checkbox itself now ticks it (before, only tapping the entry's text worked)
- App updates now show on the first open after a deploy: the new version installs fresh files (not copies from the browser cache), the app reloads itself once the update is ready (never while you are typing), and it checks for updates whenever it is brought back to the screen

### Changed
- Starter lists are now empty, ready-made categories: adding one creates the category only, with no pre-filled entries, so everyone starts with their own words. Entries already imported by existing accounts are not touched

## [2.1.0] – 2026-11-14
### Added
- Any language and any short text: entries up to 500 characters (sentences, quotes, poems, formulas) with line breaks and right-to-left support; existing PostgreSQL databases are widened automatically
- Reminders rotate through all due entries
- New starter lists: Motivation, Math Formulas, Poems (public domain), French, Spanish, Chinese and Hindi basics
- Amber theme and flashcards app icon
- Wiktionary fallback for dictionary look-ups (phrases and idioms)
- Starter lists: Vocabulary, Phrasal Verbs, Idioms and a new Casual list; lists are matched by a fixed key, so renaming one never creates duplicate categories
- "Forgot password?" – emailed one-time reset link (1 hour), stored as a SHA-256 hash, rate-limited to 3 per hour
- Resetting the password signs out every other device (session version in the token)
- Helpful hint when signing up with an email that already has an account
- Existing databases get new columns automatically on start-up

## [2.0.0] – 2026-11-14
### Added
- Multi-user accounts with secure sessions
- Words with automatic meaning, example and pronunciation
- Categories (many-to-many) with per-category notification switches
- Per-user notification schedule: frequency, hours, days, daily limit, pause, time zone
- Web push notifications and a 15-minute scheduler (GitHub Actions)
- Spaced-repetition quiz and optional quiz-style notifications
- Progress page, starter word lists, iPhone install guide
- Admin statistics with retention
- Tests, linting and CI; Docker and docker compose

## [1.0.0]
- Personal command-line version: SQLite database and ntfy notifications
