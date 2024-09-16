import unreal
from ayon_core.pipeline import InventoryAction
from ayon_unreal.api.lib import (
    update_skeletal_mesh,
    import_animation_sequence
)
from ayon_unreal.api.pipeline import (
    get_frame_range_from_folder_attributes,
    get_camera_tracks
)

class ConnectFbxAnimation(InventoryAction):
    """Add Animation Sequence to Level Sequence when the skeletal Mesh
    already binds into the Sequence. Applied only for animation and
    layout product type
    """

    label = "Connect Fbx Animation to Level Sequence"
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
                    f"Container {container_dir} is not supported."
                )
                continue
        sequence = self.get_level_sequence(containers)
        if not sequence:
            raise RuntimeError(
                "No level sequence found in layout asset directory. "
                "Please select the layout container."
            )
        self.import_camera(containers, sequence)
        self.import_animation(containers, sequence)
        self.save_layout_asset(containers)

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

    def import_animation(self, containers, sequence):
        anim_path = next((
            container.get("namespace") for container in containers
            if container.get("family") == "animation"), None)
        start_frame, end_frame = get_frame_range_from_folder_attributes()
        # use the clipIn/Out value for the frameStart and frameEnd
        frameStart = next((
            int(container.get("frameStart", start_frame)) for container in containers
            if container.get("family") == "animation"), None)
        frameEnd = next((
            int(container.get("frameEnd", end_frame)) for container in containers
            if container.get("family") == "animation"), None)
        if anim_path:
            asset_content = unreal.EditorAssetLibrary.list_assets(
                anim_path, recursive=False, include_folder=False
            )
            self.import_animation_sequence(
                asset_content, sequence, frameStart, frameEnd)

    def import_camera(self, containers, sequence):
        start_frame, end_frame = get_frame_range_from_folder_attributes()
        # use the clipIn/Out value for the frameStart and frameEnd
        frameStart = next((
            int(container.get("frameStart", start_frame)) for container in containers
            if container.get("family") == "camera"), None)
        frameEnd = next((
            int(container.get("frameEnd", end_frame)) for container in containers
            if container.get("family") == "camera"), None)
        # Add a camera cut track to the sequence
        camera_cut_track = sequence.add_master_track(unreal.MovieSceneCameraCutTrack)

        # Add a section to the camera cut track
        camera_cut_section = camera_cut_track.add_section()
        camera_cut_section.set_range(frameStart, frameEnd)  # Set the range for the camera cut

        # # Bind the camera to the camera cut section
        # camera_cut_section.set_camera_binding_id(camera_binding.get_binding_id())

    def import_animation_sequence(self, asset_content, sequence, frameStart, frameEnd):
        import_animation_sequence(asset_content, sequence, frameStart, frameEnd)

    def save_layout_asset(self, containers):
        layout_path = next((
            container.get("namespace") for container in containers
            if container.get("family") == "layout"), None)
        asset_content = unreal.EditorAssetLibrary.list_assets(
            layout_path, recursive=False, include_folder=False
        )
        for asset in asset_content:
            unreal.EditorAssetLibrary.save_asset(asset)

class ConnectAlembicAnimation(ConnectFbxAnimation):
    """Add Animation Sequence to Level Sequence when the skeletal Mesh
    already binds into the Sequence. Applied only for animation and
    layout product type.
    This is done in hacky way which replace the loaded fbx skeletal mesh with the alembic one
    in the current update. It will be removed after support the alembic export of rig product
    type.
    """

    label = "Connect Alembic Animation to Level Sequence"
    icon = "arrow-up"
    color = "red"
    order = 1

    def import_animation_sequence(self, asset_content, sequence, frameStart, frameEnd):
        update_skeletal_mesh(asset_content, sequence)
        import_animation_sequence(asset_content, sequence, frameStart, frameEnd)
