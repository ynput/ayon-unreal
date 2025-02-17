import unreal

from ayon_core.pipeline import InventoryAction


def find_content_plugin_asset(container_name):
    # List all assets in the project content folder
    asset_registry = unreal.AssetRegistryHelpers.get_asset_registry()
    # Get all target assets
    target_assets = {
        package.get_asset()
        for package in
        asset_registry.get_all_assets()
        if container_name in str(package.asset_name)
    }

    # asset in game content
    game_content = {
        game_asset.get_asset()
        for game_asset in
        asset_registry.get_assets_by_path('/Game', recursive=True)
        if game_asset.get_asset().get_name() == container_name
    }

    target_assets = target_assets.difference(game_content)
    if target_assets:
        target_asset = list(target_assets)[-1]
        target_asset_path = target_asset.get_path_name()
        return target_asset, target_asset_path

    return None, None


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
            container_name = container.get("container_name")
            target_container, path = find_content_plugin_asset(container_name)
            if target_container:
                dst_path = unreal.Paths.get_path(path)
                unreal.EditorAssetLibrary.set_metadata_tag(
                    target_container, "namespace", f"{dst_path}"
                )
                asset_content = unreal.EditorAssetLibrary.list_assets(
                    container.get("namespace"), recursive=True, include_folder=False
                )
                for a in asset_content:
                    unreal.EditorAssetLibrary.save_asset(a)
