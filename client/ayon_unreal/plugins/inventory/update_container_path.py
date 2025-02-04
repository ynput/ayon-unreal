import unreal

from ayon_unreal.api.pipeline import ls, imprint
from ayon_core.pipeline import InventoryAction


def find_content_plugin_asset(asset_name):
    # List all assets in the project content folder
    asset_registry = unreal.AssetRegistryHelpers.get_asset_registry()
    # Get all target assets
    target_assets = {
        unreal.Paths.split(package.package_path)[0]
        for package in
        asset_registry.get_all_assets()
        if asset_name in str(package.asset_name)
    }

    # asset in game content
    game_content = {
        unreal.Paths.split(game_asset.get_asset().get_path_name())[0]
        for game_asset in
        asset_registry.get_assets_by_path('/Game', recursive=True)
        if game_asset.get_asset().get_name() == asset_name
    }

    target_assets = target_assets.difference(game_content)
    if target_assets:
        print("target_assets", list(target_assets)[0])
        return list(target_assets)[-1]

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
            asset_name = container.get("asset_name")
            updated_container_dir = find_content_plugin_asset(asset_name)
            if updated_container_dir:
                container_name = container.get("container_name")
                imprint(
                    f"{updated_container_dir}/{asset_name}/{container_name}",
                    {"namespace": f"{updated_container_dir}/{asset_name}"}
                )
