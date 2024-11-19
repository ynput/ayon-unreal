from ayon_server.settings import BaseSettingsModel, SettingsField
from .imageio import UnrealImageIOModel
from .import_settings import UnrealImportModel
from .pre_launch_settings import UnrealPreLaunchSetting


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
        {"value": "json", "label": "json"},
        {"value": "fbx", "label": "fbx"},
        {"value": "abc", "label": "abc"}
    ]


class UnrealSettings(BaseSettingsModel):
    imageio: UnrealImageIOModel = SettingsField(
        default_factory=UnrealImageIOModel,
        title="Color Management (ImageIO)"
    )
    prelaunch_settings: UnrealPreLaunchSetting = SettingsField(
        default_factory=UnrealPreLaunchSetting,
        title="Prelaunch Settings"
    )
    loaded_asset_dir: str = SettingsField(
        "{folder[path]}/{product[name]}_{version[version]}",
        title="Asset directories for loaded assets",
        description="Asset directories to store the loaded assets"
    )
    loaded_layout_dir: str = SettingsField(
        "{folder[path]}/{product[name]}",
        title="Directories for loaded layouts",
        description="Directories to store the loaded layouts"
    )
    import_settings: UnrealImportModel = SettingsField(
        default_factory=UnrealImportModel,
        title="Import settings"
    )
    level_sequences_for_layouts: bool = SettingsField(
        False,
        title="Generate level sequences when loading layouts"
    )
    remove_loaded_assets: bool = SettingsField(
        False,
        title="Remove loaded assets when deleting layouts"
    )
    delete_unmatched_assets: bool = SettingsField(
        False,
        title="Delete assets that are not matched",
        description=(
            "When enabled removes all unmatched assets "
            "present in the current layout when performing "
            "'Load Layout (JSON) on existing'"
        )
    )
    abc_conversion_preset: str = SettingsField(
        "maya",
        title="Alembic Conversion Setting Presets",
        enum_resolver=_abc_conversion_presets_enum,
        description="Presets for converting the loaded alembic "
                    "with correct UV and transform"
    )
    force_loaded: bool = SettingsField(
        False,
        title="Enable user override layout representation",
        description="Loading assets by override layout representation type"
    )
    folder_representation_type: str = SettingsField(
        "json",
        title="Override layout representation by",
        enum_resolver=_loaded_asset_enum,
        description="The overriding folder representation type during loading"
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
    "loaded_asset_dir": "{folder[path]}/{product[name]}_{version[version]}",
    "loaded_layout_dir": "{folder[path]}/{product[name]}",
    "level_sequences_for_layouts": True,
    "remove_loaded_assets": False,
    "delete_unmatched_assets": False,
    "abc_conversion_preset": "maya",
    "force_loaded": False,
    "folder_representation_type": "json",
    "render_queue_path": "/Game/Ayon/renderQueue",
    "render_config_path": "/Game/Ayon/DefaultMovieRenderQueueConfig.DefaultMovieRenderQueueConfig",
    "preroll_frames": 0,
    "render_format": "exr",
    "project_setup": {
        "dev_mode": False
    }
}
