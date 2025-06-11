import unreal

from ayon_core.pipeline import InventoryAction
from ayon_unreal.api.pipeline import imprint


def find_content_plugin_asset(container_dir):
    """Search if the asset exists in the content plugin

    Args:
        container_dir (str): directory of the container

    Returns:
        str: asset, asset path
    """
    # List all assets in the project content folder
    search_dir = container_dir.replace("/Game", "")
    asset_registry = unreal.AssetRegistryHelpers.get_asset_registry()
    # Get all target assets
    target_assets = {
        package.get_asset()
        for package in
        asset_registry.get_all_assets()
        if search_dir in str(package.package_path)
    }

    # asset in game content
    game_content = {
        game_asset.get_asset()
        for game_asset in
        asset_registry.get_assets_by_path('/Game', recursive=True)
        if game_asset.get_asset().get_path_name() == container_dir
    }

    target_assets = target_assets.difference(game_content)
    if target_assets:
        target_asset = list(target_assets)[-1]
        target_asset_path = target_asset.get_path_name()
        return target_asset_path

    return None


class UpdateContainerPath(InventoryAction):
    """Update container Path for the assets migrating to content plugin
    """

    label = "Update Container Path"
    icon = "arrow-up"

    def process(self, containers):
        excluded_families = ["animation", "camera", "layout"]
        for container in containers:
            container_dir = container.get("namespace")
            if container.get("family") in excluded_families:
                unreal.log_warning(
                    f"Container {container_dir} is not supported.")
                continue
            target_container_dir = find_content_plugin_asset(container_dir)
            if target_container_dir:
                target_container_dir = unreal.Paths.get_path(target_container_dir)
                container_name = container.get("container_name")
                data = {"namespace": target_container_dir}
                imprint(f"{target_container_dir}/{container_name}", data)

                asset_content = unreal.EditorAssetLibrary.list_assets(
                    target_container_dir, recursive=True, include_folder=False
                )
                for a in asset_content:
                    unreal.EditorAssetLibrary.save_asset(a)
