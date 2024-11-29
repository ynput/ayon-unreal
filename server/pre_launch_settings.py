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

    arbitrary_site_package_location: bool = SettingsField(
        False, title="Use local user space location for dependencies",
        description=("Use user space location for dependencies "
                              "instead of installing them directly to "
                              "Unreal install location.")
    )


    DEFAULT_PRELAUNCH_SETTINGS = {
        "use_dependency": False,
        "dependency_path": "",
        "arbitrary_site_package_location": False

    }
