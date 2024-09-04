import unreal
import json
from pathlib import Path
from ayon_api import get_representation_by_id

from ayon_core.pipeline import (
    InventoryAction,
    get_current_project_name,
    get_representation_path
)


def read_representation_data(lib_path):
    representation_ids = []

    with open(lib_path, "r") as fp:
        data = json.load(fp)
    for element in data:
        representation_ids.append(element["representation"])
    return representation_ids


class SwitchAnimatedAssets(InventoryAction):
    """Switch Animated Assets from the static ones.
    """

    label = "Switch animated assets"
    icon = "arrow-up"
    color = "red"
    order = 1

    def process(self, containers):
        allowed_families = ["animation", "layout"]
        sequence = None
        for container in containers:
            container_dir = container.get("namespace")
            if container.get("family") not in allowed_families:
                unreal.log_warning(
                    f"Container {container_dir} is not supported.")
                continue
        sequence = self.get_level_sequence(containers)
        if not sequence:
            raise RuntimeError(
                "No level sequence found in layout asset directory")
        self._import_animation(containers, sequence)


    def _import_animation(self, containers, sequence):
        anim_path = next((
            container.get("namespace") for container in containers
            if container.get("family") == "animation"), None)
        if anim_path:
            asset_content = unreal.EditorAssetLibrary.list_assets(
                anim_path, recursive=False, include_folder=False
            )

            animation = None

            for a in asset_content:
                unreal.EditorAssetLibrary.save_asset(a)
                imported_asset_data = unreal.EditorAssetLibrary.find_asset_data(a)
                imported_asset = unreal.AssetRegistryHelpers.get_asset(
                    imported_asset_data)
                if imported_asset.__class__ == unreal.AnimSequence:
                    animation = imported_asset
                    break

            if sequence:
                # Add animation to the sequencer

                ar = unreal.AssetRegistryHelpers.get_asset_registry()
                tracks = sequence.get_tracks()
                seq_track = None
                for track in tracks:
                    if str(track).count("MovieSceneSkeletalAnimationTrack"):
                        seq_track = track
                    else:
                        seq_track = sequence.add_track(
                    unreal.MovieSceneSkeletalAnimationTrack)

                sections = seq_track.get_sections()
                unreal.log(sections)
                unreal.log(sections)
                section = None
                if not sections:
                    section = seq_track.add_section()
                else:
                    section = sections[0]

                    sec_params = section.get_editor_property('params')
                    curr_anim = sec_params.get_editor_property('animation')

                    if curr_anim:
                        # Checks if the animation path has a container.
                        # If it does, it means that the animation is
                        # already in the sequencer.
                        anim_path = str(Path(
                            curr_anim.get_path_name()).parent
                        ).replace('\\', '/')

                        _filter = unreal.ARFilter(
                            class_names=["AyonAssetContainer"],
                            package_paths=[anim_path],
                            recursive_paths=False)
                        containers = ar.get_assets(_filter)

                        if len(containers) > 0:
                            return

                section.set_range(
                    sequence.get_playback_start(),
                    sequence.get_playback_end())
                sec_params = section.get_editor_property('params')
                sec_params.set_editor_property('animation', animation)


    def get_level_sequence(self, containers):
        ar = unreal.AssetRegistryHelpers.get_asset_registry()
        layout_path = next((
            container.get("namespace") for container in containers
            if container.get("family") == "layout"), None)
        if not layout_path:
            return None
        asset_content = unreal.EditorAssetLibrary.list_assets(
            layout_path, recursive=False, include_folder=False
        )
        for asset in asset_content:
            data = ar.get_asset_by_object_path(asset)
            if data.asset_class_path.asset_name == "LevelSequence":
                return data.get_asset()
