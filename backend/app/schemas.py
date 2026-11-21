"""Request / response shapes for the API."""

from datetime import datetime
from zoneinfo import available_timezones

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class SignupIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    timezone: str = "UTC"


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class ForgotPasswordIn(BaseModel):
    email: EmailStr


class ResetPasswordIn(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    password: str = Field(min_length=8, max_length=128)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    email: str
    timezone: str
    is_admin: bool = False


class CategoryIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    color: str = "#4F46E5"
    notify: bool = True


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=60)
    color: str | None = None
    notify: bool | None = None


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    color: str
    notify: bool
    word_count: int = 0


class WordIn(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    meaning: str = ""  # optional; left blank -> auto-filled from the dictionary when possible
    example: str = ""  # optional
    category_ids: list[int] = []


class WordIds(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=2000)


class WordUpdate(BaseModel):
    text: str | None = Field(default=None, min_length=1, max_length=500)
    meaning: str | None = None
    example: str | None = None
    category_ids: list[int] | None = None


class CategoryRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    color: str


class WordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    text: str
    meaning: str
    example: str
    phonetic: str
    audio_url: str
    lang: str = "en-US"  # for the Listen button (browser text-to-speech)
    box: int
    due_at: datetime
    times_correct: int
    times_wrong: int
    created_at: datetime
    categories: list[CategoryRef]


class SettingsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    timezone: str
    notify_every_minutes: int
    active_start_hour: int
    active_end_hour: int
    active_days: str
    daily_limit: int
    quiz_notifications: bool
    notify_uncategorized: bool = True
    paused_until: datetime | None

    @field_validator("notify_uncategorized", mode="before")
    @classmethod
    def null_means_on(cls, v: bool | None) -> bool:
        return v is not False  # accounts made before this setting existed have NULL


class SettingsIn(BaseModel):
    timezone: str | None = None
    notify_every_minutes: int | None = Field(default=None, ge=15, le=1440)
    active_start_hour: int | None = Field(default=None, ge=0, le=23)
    active_end_hour: int | None = Field(default=None, ge=1, le=24)
    active_days: str | None = Field(default=None, pattern=r"^[0-6]{0,7}$")
    daily_limit: int | None = Field(default=None, ge=1, le=50)
    quiz_notifications: bool | None = None
    notify_uncategorized: bool | None = None
    voice: str | None = Field(default=None, pattern=r"^(ca-female|ca-male|us-female|us-male|device)$")

    @field_validator("timezone")
    @classmethod
    def valid_tz(cls, v: str | None) -> str | None:
        if v is not None and v not in available_timezones():
            raise ValueError("Unknown time zone")
        return v


class PauseIn(BaseModel):
    hours: int = Field(ge=0, le=24 * 30)  # 0 = resume now


class AnswerIn(BaseModel):
    word_id: int
    knew: bool


class PushKeys(BaseModel):
    p256dh: str
    auth: str


class PushSubscriptionIn(BaseModel):
    endpoint: str
    keys: PushKeys
