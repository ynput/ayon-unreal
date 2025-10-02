import pathlib
import shutil
from ayon_applications import LaunchTypes, PreLaunchHook
from ayon_unreal.addon import UNREAL_ADDON_ROOT
import semver
import filecmp


class CopyBlueprints(PreLaunchHook):
    app_groups = {"unreal"}
    launch_types = {LaunchTypes.local}
    order = 1

    def execute(self):
        self.log.info("Running Copy Blueprints")
        unreal_version = semver.VersionInfo(*self.launch_context.env.get("AYON_UNREAL_VERSION").split('.'))
        if unreal_version >= semver.VersionInfo(5, 6, 0):
            self.log.info(f"Skipping Asset Copy for {str(unreal_version)}")
            return

        project_path = self.launch_context.env.get("AYON_UNREAL_PROJECT_PATH")
        if not project_path:
            raise RuntimeError("AYON_UNREAL_PROJECT_PATH not set.")
        project_path = pathlib.Path(project_path)
        container_path = project_path.joinpath(
            "Content", "Ayon", "AyonContainerTypes"
        )

        self.log.debug(f"Container Path {container_path}")
        unreal_version_text = f"UE_{unreal_version.major}.{unreal_version.minor}"
        unreal_addon_root = pathlib.Path(UNREAL_ADDON_ROOT)
        unreal_blueprint_path = unreal_addon_root.joinpath(
            'blueprints',
            unreal_version_text
        )
        blueprint_files = unreal_blueprint_path.glob('*.uasset')

        container_path.mkdir(exist_ok=True, parents=True)
        for blueprint_file in blueprint_files:
            dest = container_path.joinpath(blueprint_file.name)
            if dest.exists():
                if not filecmp.cmp(blueprint_file, dest):
                    shutil.copy(blueprint_file, dest)
                else:
                    continue
            else:
                shutil.copy(blueprint_file, dest)



