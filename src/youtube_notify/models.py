import enum

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, HttpUrl


class ContentType(enum.StrEnum):
    VIDEO = "video"
    LIVESTREAM = "livestream"
    SHORT = "short"


class Channel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1, description="YouTube channel identifier.")
    name: str = Field(min_length=1, description="YouTube channel display name.")

    def __repr__(self) -> str:
        return f"Channel(id={self.id}, name={self.name})"


class Content(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1, description="YouTube video identifier.")
    title: str = Field(min_length=1, description="Video title.")
    published_at: AwareDatetime = Field(
        description="Timezone-aware publication timestamp."
    )
    thumbnail_url: HttpUrl = Field(description="Primary video thumbnail URL.")
    description: str = Field(description="Video description text.")
    content_type: ContentType = Field(description="Content type.")
    channel: Channel = Field(description="Owning channel metadata.")

    def __repr__(self) -> str:
        return f"Content(id={self.id}, title={self.title}, published_at={self.published_at}, thumbnail_url={self.thumbnail_url}, description={self.description}, channel={self.channel})"
