from ayon_server.settings import BaseSettingsModel, SettingsField


class UnrealPreLaunchSetting(BaseSettingsModel):
    """Install PySide2/6 Qt binding to unreal's python packages."""

    use_dependency: bool = SettingsField(
        False,
        title="Use Offline Package Source",
        description=(
            "Install PySide package from a local folder or URL "
            "instead of downloading from the internet."
        )
    )
    dependency_path: str = SettingsField(
        "",
        title="Offline Package Source Path",
        description=(
            "Path to a local folder or URL containing the PySide "
            "package files (e.g., .whl, .tar.gz)."
        )
    )
    arbitrary_site_package_location: bool = SettingsField(
        False, title="Install to Launcher Data Path",
        description=(
            "Use a dedicated folder in AYON launcher local data folder "
            "`AYON_LAUNCHER_LOCAL_DIR` as the target install location "
            "for dependencies, and add it to Unreal's Python path. "
            "This avoids modifying the system, engine, or user-specific "
            "Python environments."
        )
    )


DEFAULT_PRELAUNCH_SETTINGS = {
    "use_dependency": False,
    "dependency_path": "",
    "arbitrary_site_package_location": False
}
