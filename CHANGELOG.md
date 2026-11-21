# Changelog

## [Unreleased]
### Added
- "No category" switch on the Categories page: entries without a category can now be switched off too, so turning on a single category sends only that category's entries (before, uncategorized entries were always sent)
- Only the entry text is required when adding a word, phrase or quote; "Meaning or note" and "Example" are optional (English entries are still filled from the dictionary when possible)
- Phone keyboards start the "Add a word, phrase or quote" box with a capital letter

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
