import unreal

from ayon_unreal.api.pipeline import ls, imprint
from ayon_core.pipeline import InventoryAction


def find_content_plugin_asset(asset_name):
    # List all assets in the project content folder
    asset_registry = unreal.AssetRegistryHelpers.get_asset_registry()
    # Get all target assets
    # Create an ARFilter to find assets with the given name
    # for the future development of filtering
    asset_filter = unreal.ARFilter(
        class_names=[],  # Empty means all classes
        package_paths=[],  # Empty means all paths
        recursive_classes=True,
        recursive_paths=True,
        soft_object_paths=[],
        tags_and_values={},
    )

    # Find all assets that match the asset_name
    all_assets = asset_registry.get_assets(asset_filter)
    target_assets = {
        unreal.Paths.split(package.package_path)[0]
        for package in all_assets
        if asset_name.lower() in str(package.asset_name).lower()
    }

    # Find assets in the /Game folder with the exact name
    # Use ARFilter for the future development of filtering
    game_content_filter = unreal.ARFilter(
        class_names=[],
        package_paths=["/Game"],  # Limit to /Game folder
        recursive_classes=True,
        recursive_paths=True,
        soft_object_paths=[],
        tags_and_values={},
    )
    game_assets = asset_registry.get_assets(game_content_filter)
    game_content = {
        unreal.Paths.split(package.package_path)[0]
        for package in game_assets
        if package.asset_name == asset_name
    }
    target_assets -= game_content
    if target_assets:
        return target_assets[0]

    return None


class DeleteUnusedAssets(InventoryAction):
    """Update containerpPath for the assets migrating to content plugin
    """

    label = "Update Container Path"
    icon = "arrow-up"

    def process(self, containers):
        pass
    excluded_families = ["animation", "camera", "layout"]

    # Get all the containers in the Unreal Project
    all_containers = ls()

    for container in all_containers:
        container_dir = container.get("namespace")
        if container.get("family") in excluded_families:
            unreal.log_warning(
                f"Container {container_dir} is not supported.")
            continue
        asset_name = container.get("asset_name")
        updated_container_dir = find_content_plugin_asset(asset_name)
        if updated_container_dir:
            container_name = container.get("container_name")
            imprint(
                f"{container_dir}/{container_name}",
                {"namespace": updated_container_dir}
            )
