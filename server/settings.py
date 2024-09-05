from ayon_server.settings import BaseSettingsModel, SettingsField
from .imageio import UnrealImageIOModel
from .import_settings import UnrealImportModel


class ProjectSetup(BaseSettingsModel):
    allow_project_creation: bool = SettingsField(
        True,
        title="Allow project creation",
        description="Whether to create a new project when none is found. Disable when using external source controll (Perforce)"
    )
    dev_mode: bool = SettingsField(
        False,
        title="Dev mode"
    )


def _abc_conversion_presets_enum():
    return [
        {"value": "maya", "label": "maya"},
        {"value": "custom", "label": "custom"}
    ]


def _render_format_enum():
    return [
        {"value": "png", "label": "PNG"},
        {"value": "exr", "label": "EXR"},
        {"value": "jpg", "label": "JPG"},
        {"value": "bmp", "label": "BMP"}
    ]


def _loaded_asset_enum():
    return [
        {"value": "fbx", "label": "fbx"},
        {"value": "abc", "label": "abc"}
    ]


class UnrealSettings(BaseSettingsModel):
    imageio: UnrealImageIOModel = SettingsField(
        default_factory=UnrealImageIOModel,
        title="Color Management (ImageIO)"
    )
    import_settings: UnrealImportModel = SettingsField(
        default_factory=UnrealImportModel,
        title="Import settings"
    )
    level_sequences_for_layouts: bool = SettingsField(
        False,
        title="Generate level sequences when loading layouts"
    )
    delete_unmatched_assets: bool = SettingsField(
        False,
        title="Delete assets that are not matched"
    )
    abc_conversion_preset: str = SettingsField(
        "maya",
        title="Alembic Conversion Setting Presets",
        enum_resolver=_abc_conversion_presets_enum,
        description="Presets for converting the loaded alembic "
                    "with correct UV and transform"
    )
    loaded_assets_extension: str = SettingsField(
        "fbx",
        title="Loaded Assets Extension",
        enum_resolver=_loaded_asset_enum,
        description="Extension for the loaded assets"
    )
    render_queue_path: str = SettingsField(
        "",
        title="Render Queue Path",
        description="Path to Render Queue UAsset for farm publishing"
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
    project_setup: ProjectSetup = SettingsField(
        default_factory=ProjectSetup,
        title="Project Setup",
    )


DEFAULT_VALUES = {
    "level_sequences_for_layouts": True,
    "delete_unmatched_assets": False,
    "abc_conversion_preset": "maya",
    "loaded_assets_extension": "fbx",
    "render_queue_path": "/Game/Ayon/renderQueue",
    "render_config_path": "/Game/Ayon/DefaultMovieRenderQueueConfig.DefaultMovieRenderQueueConfig",
    "preroll_frames": 0,
    "render_format": "exr",
    "project_setup": {
        "dev_mode": False
    }
}
