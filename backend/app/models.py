"""Database tables."""

from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


# Many-to-many: a word can belong to several categories.
word_categories = Table(
    "word_categories",
    Base.metadata,
    Column("word_id", ForeignKey("words.id", ondelete="CASCADE"), primary_key=True),
    Column("category_id", ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Bumped when the password changes; sessions carrying an older number are rejected.
    session_version: Mapped[int | None] = mapped_column(Integer, default=0, nullable=True)

    # Notification settings
    notify_every_minutes: Mapped[int] = mapped_column(Integer, default=60)
    active_start_hour: Mapped[int] = mapped_column(Integer, default=9)
    active_end_hour: Mapped[int] = mapped_column(Integer, default=21)
    active_days: Mapped[str] = mapped_column(String(7), default="0123456")  # Mon=0 .. Sun=6
    daily_limit: Mapped[int] = mapped_column(Integer, default=10)
    quiz_notifications: Mapped[bool] = mapped_column(Boolean, default=False)
    paused_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Scheduler bookkeeping
    last_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notified_today: Mapped[int] = mapped_column(Integer, default=0)
    notified_today_date: Mapped[str | None] = mapped_column(String(10))  # local YYYY-MM-DD

    words: Mapped[list["Word"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    categories: Mapped[list["Category"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    subscriptions: Mapped[list["PushSubscription"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("user_id", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(60))
    color: Mapped[str] = mapped_column(String(9), default="#4F46E5")
    notify: Mapped[bool] = mapped_column(Boolean, default=True)
    # Which starter list this category came from (e.g. "vocabulary"), so renaming a list
    # never creates duplicates. Empty for categories the user created.
    starter_key: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship(back_populates="categories")
    words: Mapped[list["Word"]] = relationship(
        secondary=word_categories, back_populates="categories"
    )


class Word(Base):
    __tablename__ = "words"
    __table_args__ = (UniqueConstraint("user_id", "text"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(String(120))
    meaning: Mapped[str] = mapped_column(Text)
    example: Mapped[str] = mapped_column(Text, default="")
    phonetic: Mapped[str] = mapped_column(String(120), default="")
    audio_url: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Spaced repetition (Leitner boxes)
    box: Mapped[int] = mapped_column(Integer, default=0)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    times_shown: Mapped[int] = mapped_column(Integer, default=0)
    times_correct: Mapped[int] = mapped_column(Integer, default=0)
    times_wrong: Mapped[int] = mapped_column(Integer, default=0)
    last_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # When this word was last sent as a notification (used to rotate reminders).
    last_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped[User] = relationship(back_populates="words")
    categories: Mapped[list[Category]] = relationship(
        secondary=word_categories, back_populates="words"
    )


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    endpoint: Mapped[str] = mapped_column(Text, unique=True)
    p256dh: Mapped[str] = mapped_column(String(255))
    auth: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship(back_populates="subscriptions")


class ReviewEvent(Base):
    """One answer in a quiz. Used for progress, streaks and retention analytics."""

    __tablename__ = "review_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    word_id: Mapped[int] = mapped_column(ForeignKey("words.id", ondelete="CASCADE"), index=True)
    knew: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class PasswordResetToken(Base):
    """One-time link for "Forgot password?". Only a SHA-256 hash of the token is stored,
    so a database leak cannot be used to reset anyone's password."""

    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
