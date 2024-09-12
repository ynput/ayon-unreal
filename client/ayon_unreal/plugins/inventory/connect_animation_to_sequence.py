import unreal
from ayon_core.pipeline import InventoryAction
from ayon_unreal.api.lib import (
    update_skeletal_mesh,
    import_animation_sequence
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
        # use the clipIn/Out value for the frameStart and frameEnd
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
            self.import_animation_sequence(
                asset_content, sequence, frameStart, frameEnd)

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
