"""Setting model for Unreal Engine Creators."""
from ayon_server.settings import (
    BaseSettingsModel,
    SettingsField,
)


class BasicCreatorModel(BaseSettingsModel):
    enabled: bool = SettingsField(title="Enabled")
    default_variants: list[str] = SettingsField(
        default_factory=list,
        description="Default variants used for constructing a product name",
        title="Default Variants",
    )

class CreatorsModel(BaseSettingsModel):
    CreateCamera: BasicCreatorModel = SettingsField(
        default_factory=BasicCreatorModel,
        title="Create Camera"
    )

    CreateLayout: BasicCreatorModel = SettingsField(
        default_factory=BasicCreatorModel,
        title="Create Layout"
    )

    CreateRender: BasicCreatorModel = SettingsField(
        default_factory=BasicCreatorModel,
        title="Create Render"
    )

    CreateStaticMeshFBX: BasicCreatorModel = SettingsField(
        default_factory=BasicCreatorModel,
        title="Create Static Mesh"
    )

    CreateUAsset: BasicCreatorModel = SettingsField(
        default_factory=BasicCreatorModel,
        title="Create UAsset"
    )


DEFAULT_CREATOR_SETTINGS = {
    "CreateCamera": {
        "enabled": True,
        "default_variants": ["Main", "Hero"]
    },
    "CreateLayout": {
        "enabled": True,
        "default_variants": ["Main"]
    },
    "CreateRender": {
        "enabled": True,
        "default_variants": ["Main"]
    },
    "CreateStaticMeshFBX": {
        "enabled": True,
        "default_variants": ["Main"]
    },
    "CreateUAsset": {
        "enabled": True,
        "default_variants": ["Main"]
    }
}
