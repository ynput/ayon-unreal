from ayon_server.settings import BaseSettingsModel, SettingsField


class UnrealPreLaunchSetting(BaseSettingsModel):
    #_layout = "expanded"
    _isGroup: bool = True

    use_dependency: bool = SettingsField(
        False,
        title="Use Dependency Path",
        description=(
            "Use Dependency Path to pip install PySide before launching unreal."
        )
    )
    dependency_path: str = SettingsField(
        "",
        title="Dependency Path",
        description=(
            "Dependency Path to pip install PySide before launching unreal."
        )
    )

    use_venv: bool = SettingsField(False, title="Use Virtual Environment")