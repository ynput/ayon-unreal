
from ayon_server.settings import BaseSettingsModel, SettingsField


class U_interchangeModel(BaseSettingsModel):
    enabled: bool = SettingsField(False, title="enabled")

    pipeline_path_static_mesh: str = SettingsField(
    "/Game/Interchange/CustomPipeline.CustomPipeline", title="path to static mesh pipeline",
        description=("Path to the Interchange pipeline asset."
                    "Rightclick asset and copy refrence path.")
        )
    pipeline_path_textures: str = SettingsField(
    "/Game/Interchange/CustomPipeline.CustomPipeline", title="path to texture pipeline",
        description=("Path to the Interchange pipeline asset."
                    "Rightclick asset and copy refrence path.")
        )




class U_importModel(BaseSettingsModel):
    #_layout = "expanded"
    _isGroup: bool = True

    interchange: U_interchangeModel = SettingsField(
        default_factory=U_interchangeModel,
        title="Interchange pipeline"
    )

    use_nanite: bool = SettingsField( True,
        title="Use nanite", description=("Import with nanite enabled. This setting works when interchange pipeline is not used."
                                         "When using the interchange pipeline, set this in the pipeline asset"))

    show_dialog: bool = SettingsField( False,
        title="Show import dialog")


