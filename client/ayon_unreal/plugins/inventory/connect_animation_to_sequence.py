import unreal
from ayon_core.pipeline import InventoryAction


class ConnectAnimationToLevelSequence(InventoryAction):
    """Add Animation Sequence to Level Sequence when the skeletal Mesh
    already binds into the Sequence. Applied only for animation and
    layout product type
    """

    label = "Connect Animation to Level Sequence"
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
        self.save_layout_asset(containers)

    def _import_animation(self, containers, sequence):
        anim_path = next((
            container.get("namespace") for container in containers
            if container.get("family") == "animation"), None)
        frameStart = next((
            int(container.get("frameStart")) for container in containers
            if container.get("family") == "animation"), None)
        frameEnd = next((
            int(container.get("frameEnd")) for container in containers
            if container.get("family") == "animation"), None)
        if anim_path:
            asset_content = unreal.EditorAssetLibrary.list_assets(
                anim_path, recursive=False, include_folder=False
            )
            extension = anim_path.split("/")[-1].rsplit("_")[-1]
            if extension == "fbx":
                self._import_animation_sequence(
                    asset_content, sequence, frameStart, frameEnd)
            elif extension == "abc":
                pass

    def _import_animation_sequence(self, asset_content, sequence, frameStart, frameEnd):
            bindings = []
            animation = None

            ar = unreal.AssetRegistryHelpers.get_asset_registry()
            for a in asset_content:
                imported_asset_data = ar.get_asset_by_object_path(a).get_asset()
                if imported_asset_data.get_class().get_name() == "AnimSequence":
                    animation = imported_asset_data
                    break
            if sequence:
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
                        anim_section = track.add_section()
                        anim_section = sections[-1]

                params = unreal.MovieSceneSkeletalAnimationParams()
                params.set_editor_property('Animation', animation)
                anim_section.set_editor_property('Params', params)
                anim_section.set_range(frameStart, frameEnd)
                self.set_sequence_frame_range(sequence, frameStart, frameEnd)

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

    def save_layout_asset(self, containers):
        layout_path = next((
            container.get("namespace") for container in containers
            if container.get("family") == "layout"), None)
        asset_content = unreal.EditorAssetLibrary.list_assets(
            layout_path, recursive=False, include_folder=False
        )
        for asset in asset_content:
            unreal.EditorAssetLibrary.save_asset(asset)

    def set_sequence_frame_range(self, sequence, frameStart, frameEnd):
        display_rate = sequence.get_display_rate()
        fps = float(display_rate.numerator) / float(display_rate.denominator)
        sequence.set_playback_start(frameStart)
        sequence.set_playback_end(frameEnd)
        sequence.set_work_range_start(frameStart / fps)
        sequence.set_work_range_end(frameEnd / fps)
