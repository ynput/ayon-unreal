from ayon_server.settings import BaseSettingsModel, SettingsField


def _loaded_asset_enum():
    return [
        {"value": "json", "label": "json"},
        {"value": "fbx", "label": "fbx"},
        {"value": "abc", "label": "abc"}
    ]


def _abc_conversion_presets_enum():
    return [
        {"value": "maya", "label": "maya"},
        {"value": "3dsmax", "label": "3dsmax"},
        {"value": "custom", "label": "custom"},
    ]


class UnrealInterchangeModel(BaseSettingsModel):
    """Define Interchange Pipeline Asset Paths"""
    enabled: bool = SettingsField(False, title="enabled")
    pipeline_path_static_mesh: str = SettingsField(
        "/Game/Interchange/CustomPipeline.CustomPipeline",
        title="path to static mesh pipeline",
        description="Path to the Interchange pipeline asset."
                    "Right-click asset and copy reference path.")
    pipeline_path_textures: str = SettingsField(
        "/Game/Interchange/CustomPipeline.CustomPipeline",
        title="path to texture pipeline",
        description="Path to the Interchange pipeline asset."
                    "Right-click asset and copy reference path.")


class CustomAlembicPresetsModel(BaseSettingsModel):
    flip_u: bool = SettingsField(False, title="Flip U")
    flip_v: bool = SettingsField(True, title="Flip V")
    rot_x: float = SettingsField(90.0, title="Rotation X")
    rot_y: float = SettingsField(0.0, title="Rotation Y")
    rot_z: float = SettingsField(0.0, title="Rotation Z")
    scl_x: float = SettingsField(1.0, title="Scale X")
    scl_y: float = SettingsField(-1.0, title="Scale Y")
    scl_z: float = SettingsField(1.0, title="Scale Z")


class UnrealImportModel(BaseSettingsModel):
    #_layout = "expanded"
    _isGroup: bool = True

    loaded_asset_dir: str = SettingsField(
        "{folder[path]}/{product[name]}_{version[version]}",
        title="Asset directories for loaded assets",
        description="Asset directories to store the loaded assets",

    )

    interchange: UnrealInterchangeModel = SettingsField(
        default_factory=UnrealInterchangeModel,
        title="Interchange pipeline",
        section="Load Fbx Settings"
    )

    use_nanite: bool = SettingsField(True,
        title="Use nanite",
        description=(
            "Import with nanite enabled. This setting works when interchange "
            "pipeline is not used. When using the interchange pipeline, set "
            "this in the pipeline asset"
        )
    )

    show_dialog: bool = SettingsField(False, title="Show import dialog")

    abc_conversion_preset: str = SettingsField(
        "maya",
        title="Alembic Conversion Setting Presets",
        description="Presets for converting the loaded alembic "
                    "with correct UV and transform",
        enum_resolver=_abc_conversion_presets_enum,
        conditionalEnum=True,
        section="Load Alembic Settings"
    )
    custom: CustomAlembicPresetsModel = SettingsField(
        title="Custom Alembic Conversion Setting Presets",
        description="Custom Presets for converting the loaded alembic",
        default_factory=CustomAlembicPresetsModel,
    )
    loaded_layout_dir: str = SettingsField(
        "{folder[path]}/{product[name]}",
        title="Directories for loaded layouts",
        description="Directories to store the loaded layouts",
        section="Load Layout Settings"
    )

    level_sequences_for_layouts: bool = SettingsField(
        True,
        title="Generate level sequences when loading layouts"
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

DEFAULT_IMPORT_SETTINGS = {
    "loaded_asset_dir": "{folder[path]}/{product[name]}_{version[version]}",
    "interchange": {
        "enabled": False,
        "pipeline_path_static_mesh": "/Game/Interchange/CustomPipeline.CustomPipeline",
        "pipeline_path_textures": "/Game/Interchange/CustomPipeline.CustomPipeline",
    },
    "use_nanite": True,
    "show_dialog": False,
    "abc_conversion_preset": "maya",
    "loaded_layout_dir": "{folder[path]}/{product[name]}",
    "level_sequences_for_layouts": True,
    "force_loaded": False,
    "folder_representation_type": "json",
    "remove_loaded_assets": False,
    "delete_unmatched_assets": False,
}
