"""Setting model for Unreal Engine Creators."""
from ayon_server.settings import (
    BaseSettingsModel,
    SettingsField,
)


class ExtractReviewFFmpegModel(BaseSettingsModel):
    video_filters: list[str] = SettingsField(
        default_factory=list,
        title="Video filters"
    )
    audio_filters: list[str] = SettingsField(
        default_factory=list,
        title="Audio filters"
    )
    input: list[str] = SettingsField(
        default_factory=list,
        title="Input arguments"
    )
    output: list[str] = SettingsField(
        default_factory=list,
        title="Output arguments"
    )


class ExtractIntermediateRepresentationModel(BaseSettingsModel):
    ext: str = SettingsField("", title="Output extension")
    tags: list[str] = SettingsField(default_factory=list, title="Tags")
    custom_tags: list[str] = SettingsField(default_factory=list, title="Custom Tags")
    ffmpeg_args: ExtractReviewFFmpegModel = SettingsField(
        default_factory=ExtractReviewFFmpegModel,
        title="FFmpeg arguments"
    )


class PublishersModel(BaseSettingsModel):
    ExtractIntermediateRepresentation: ExtractIntermediateRepresentationModel = SettingsField(
        default_factory=ExtractIntermediateRepresentationModel,
        title="Extract Intermediate Representation"
    )


DEFAULT_PUBLISH_SETTINGS = {
    "ExtractIntermediateRepresentation": {
        "ext": "mp4",
        "tags": [],
        "custom_tags": [],
        "ffmpeg_args": {
            "video_filters": [],
            "audio_filters": [],
            "input": [
                "-apply_trc gamma22"
            ],
            "output": [
                "-pix_fmt yuv420p",
                "-crf 18",
                "-c:a aac",
                "-b:a 192k",
                "-g 1",
                "-movflags faststart"
            ]
        },
    }
}
