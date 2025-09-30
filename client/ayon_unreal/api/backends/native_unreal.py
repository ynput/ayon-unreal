from ayon_unreal.api.backends.base import UnrealBackend
import unreal

from ayon_unreal.api.constants import UNREAL_VERSION

def create_base_asset_container(container_name):
    container_path = "/Game/Ayon/AyonContainerTypes"
    container_full_path = f"{container_path}/{container_name}"
    asset_exists = unreal.EditorAssetLibrary.does_asset_exist(container_full_path)

    if asset_exists:
        return unreal.load_asset(container_full_path)

    asset_tools = unreal.AssetToolsHelpers.get_asset_tools()

    blueprint_factory = unreal.BlueprintFactory()
    blueprint_factory.set_editor_property(
        "ParentClass", unreal.PrimaryDataAsset
    )

    new_blueprint = asset_tools.create_asset(
        container_name,
        container_path,
        None,
        blueprint_factory,
    )
    unreal.EditorAssetLibrary.save_loaded_asset(new_blueprint)
    return new_blueprint

class NativeUnrealBackend(UnrealBackend):
    @staticmethod
    def install():
        create_base_asset_container('AyonAssetContainer')
        create_base_asset_container('AyonPublishInstance')

    @staticmethod
    def ls():
        ar = unreal.AssetRegistryHelpers.get_asset_registry()
        container_class = unreal.load_class(None, '/Game/Ayon/AyonContainerTypes/AyonAssetContainer.AyonAssetContainer_C')
        class_path = unreal.TopLevelAssetPath(container_class.get_path_name())
        # UE 5.1 changed how class name is specified
        ayon_containers = ar.get_assets_by_class(class_path, True)
        print(ayon_containers)

        return ayon_containers

    @staticmethod
    def ls_inst():
        ar = unreal.AssetRegistryHelpers.get_asset_registry()
        # UE 5.1 changed how class name is specified
        class_name = (
            ["/Game/Ayon/AyonContainerTypes", "AyonPublishInstance"]
            if (UNREAL_VERSION.major == 5 and UNREAL_VERSION.minor > 0)
            else "AyonPublishInstance"
        )  # noqa
        instances = ar.get_assets_by_class(class_name, True)

        return instances


    @staticmethod
    def create_container(container: str, path: str) -> unreal.Object:
        data_asset_class = unreal.load_class(
            None, "/Game/Ayon/AyonContainerTypes/AyonAssetContainer.AyonAssetContainer_C"
        )
        print(f"Creating Ayon Container {container}")
        tools = unreal.AssetToolsHelpers().get_asset_tools()

        return tools.create_asset(
            asset_name=container,
            package_path=f"/{path}",
            asset_class=data_asset_class,
            factory=unreal.DataAssetFactory(),
        )

    @staticmethod
    def create_publish_instance(instance: str, path:str) -> unreal.Object:
        data_asset_class = unreal.load_class(
            None, "/Game/Ayon/AyonContainerTypes/AyonPublishInstance.AyonPublishInstance_C"
        )
        print(f"Creating Ayon Container {instance}")
        tools = unreal.AssetToolsHelpers().get_asset_tools()

        return tools.create_asset(
            asset_name=instance,
            package_path=f"/{path}",
            asset_class=data_asset_class,
            factory=unreal.DataAssetFactory(),
        )

