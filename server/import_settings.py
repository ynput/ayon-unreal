from ayon_server.settings import BaseSettingsModel, SettingsField


def _resolution_loading_enum():
    return [
        {"value": "project_first", "label": "Load in Project First"},
        {"value": "content_plugin_first", "label": "Load in Content Plugin First"}
    ]

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


    ## GLOBAL ASSET IMPORT

    show_dialog: bool = SettingsField(False, title="Show Import Dialog",
                                      description="Launch Interchange UI",
                                      section="ASSET IMPORT"
                                      )

    save_asset_after_import: bool = SettingsField(False, title="Save Asset After Import",
                                                  description="Will Save Asset in Unreal after import, may cause conflicts with Perforce",)


    loaded_asset_dir: str = SettingsField(
        "{folder[path]}/{product[name]}_{version[version]}",
        title="Asset directories for loaded assets",
        description="Asset directories to store the loaded assets",
    )

    ## ASSET INTERCHANGE

    use_asset_type_sub_folders: bool = SettingsField(True,
                                                 title="Use Asset Type Sub Folders",
                                                 description=("Use Asset Type Sub Folders (Materials, Static Meshes, etc) - when importing assets into Unreal"),
                                                 section="Asset Interchange Options"
                                                 )

    import_static_meshes: bool = SettingsField(True,
                                               title="Import Static Meshes",
                                               description=("Import Static Meshes into Unreal"),
                                                )


    combine_static_meshes: bool = SettingsField(False,
                                                title="Combine Static Meshes",
                                                description=(
                                                     "An import combine all meshes to a single uasset"),
                                                )

    bake_meshes: bool = SettingsField(True,
                                            title="Bake Meshes",
                                            description=(
                                                "Bake local transforms on too imported geometry"),
                                            )

    import_collisions: bool = SettingsField(False,
                                                title="Import Collisions",
                                                description=(
                                                    "Import Collisions with Static Meshes"),
                                                )

    import_skeletal_meshes: bool = SettingsField(False,
                                               title="Import Skeletal Meshes",
                                               description=("Import Skeletal Meshes into Unreal"),
                                               )

    import_animation: bool = SettingsField(False,
                                                 title="Import Animations",
                                                 description=("Import Animations into Unreal"),
                                                 )
    import_materials: bool = SettingsField(False,
                                           title="Import Materials",
                                           description=("Import Materials into Unreal"),
                                           )

    import_textures: bool = SettingsField(False,
                                           title="Import Textures",
                                           description=("Import Textures into Unreal"),
                                           )

    use_nanite: bool = SettingsField(True,
        title="Use Nanite",
        description=(
            "Import with nanite enabled. This setting works when interchange "
            "pipeline is not used. When using the interchange pipeline, set "
            "this in the pipeline asset"
        )
    )


    abc_conversion_preset: str = SettingsField(
        "maya",
        title="Alembic Conversion Setting Presets",
        description="Presets for converting the loaded alembic "
                    "with correct UV and transform",
        enum_resolver=_abc_conversion_presets_enum,
        conditional_enum=True,
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
        section="LAYOUT IMPORT"
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
    "asset_loading_location": "project",
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
