# Changelog

## [2.1.0] – 2026-11-14
### Added
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
