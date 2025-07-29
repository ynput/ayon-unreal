from ayon_server.settings import BaseSettingsModel, SettingsField
from .imageio import UnrealImageIOModel
from .import_settings import UnrealImportModel, DEFAULT_IMPORT_SETTINGS
from .pre_launch_settings import UnrealPreLaunchSetting, DEFAULT_PRELAUNCH_SETTINGS
from .creators import CreatorsModel, DEFAULT_CREATOR_SETTINGS


def _render_format_enum():
    return [
        {"value": "png", "label": "PNG"},
        {"value": "exr", "label": "EXR"},
        {"value": "jpg", "label": "JPG"},
        {"value": "bmp", "label": "BMP"}
    ]


class RenderSetUp(BaseSettingsModel):
    render_queue_path: str = SettingsField(
        "",
        title="Render Queue Path",
        description="Path to Render Queue UAsset for farm publishing",
    )
    render_config_path: str = SettingsField(
        "",
        title="Render Config Path",
        description="Path to Render Configuration UAsset for farm publishing"
    )
    preroll_frames: int = SettingsField(
        0,
        title="Pre-roll frames"
    )
    render_format: str = SettingsField(
        "png",
        title="Render format",
        enum_resolver=_render_format_enum
    )


class ProjectSetup(BaseSettingsModel):
    allow_project_creation: bool = SettingsField(
        True,
        title="Allow project creation",
        description=(
            "Whether to create a new project when none is found. "
            "Disable when using external source control (Perforce)"
        )
    )
    dev_mode: bool = SettingsField(
        False,
        title="Dev mode"
    )


class UnrealSettings(BaseSettingsModel):
    imageio: UnrealImageIOModel = SettingsField(
        default_factory=UnrealImageIOModel,
        title="Color Management (ImageIO)"
    )
    prelaunch_settings: UnrealPreLaunchSetting = SettingsField(
        default_factory=UnrealPreLaunchSetting,
        title="Prelaunch Settings"
    )
    import_settings: UnrealImportModel = SettingsField(
        default_factory=UnrealImportModel,
        title="Import settings"
    )
    render_setup: RenderSetUp = SettingsField(
        default_factory=RenderSetUp,
        title="Render Setup",
    )
    project_setup: ProjectSetup = SettingsField(
        default_factory=ProjectSetup,
        title="Project Setup",
    )
    create: CreatorsModel = SettingsField(
        default_factory=CreatorsModel, title="Creators"
    )


DEFAULT_VALUES = {
    "prelaunch_settings": DEFAULT_PRELAUNCH_SETTINGS,
    "import_settings": DEFAULT_IMPORT_SETTINGS,
    "render_setup": {
        "render_queue_path": "/Game/Ayon/renderQueue",
        "render_config_path": "/Game/Ayon/DefaultMovieRenderQueueConfig.DefaultMovieRenderQueueConfig",
        "preroll_frames": 0,
        "render_format": "exr",
    },
    "project_setup": {
        "dev_mode": False
    },
    "create": DEFAULT_CREATOR_SETTINGS,
}
