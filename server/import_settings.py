from ayon_server.settings import BaseSettingsModel, SettingsField


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


class UnrealImportModel(BaseSettingsModel):  
    #_layout = "expanded"  
    _isGroup: bool = True  

    interchange: UnrealInterchangeModel = SettingsField(  
        default_factory=UnrealInterchangeModel,  
        title="Interchange pipeline"  
    )  

    use_nanite: bool = SettingsField(True,  
        title="Use nanite", 
        description=(  
            "Import with nanite enabled. This setting works when interchange "  
            "pipeline is not used. When using the interchange pipeline, set "  
            "this in the pipeline asset"  
        ))  

    show_dialog: bool = SettingsField(False, title="Show import dialog")  


