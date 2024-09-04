import unreal
from pathlib import Path

from ayon_core.pipeline import InventoryAction



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
            bindings = []
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
                ar = unreal.AssetRegistryHelpers.get_asset_registry()
                # Add animation to the sequencer
                binding = None
                for p in sequence.get_possessables():
                    if p.get_possessed_object_class().get_name() == "SkeletalMeshActor":
                        binding = p
                        break
                bindings.append(binding)
                anim_section = None
                for binding in bindings:
                    tracks = binding.get_tracks()
                    track = None
                    track = tracks[0] if tracks else binding.add_track(
                        unreal.MovieSceneSkeletalAnimationTrack)

                    sections = track.get_sections()

                    if not sections:
                        anim_section = track.add_section()
                    else:
                        anim_section = sections[0]
                        sec_params = anim_section.get_editor_property('params')
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

                anim_section.set_range(
                    sequence.get_playback_start(),
                    sequence.get_playback_end())

                sec_params = anim_section.get_editor_property('params')
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
