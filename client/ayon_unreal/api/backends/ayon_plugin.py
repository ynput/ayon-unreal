from ayon_unreal.api.backends.base import UnrealBackend
from ayon_unreal.api.constants import UNREAL_VERSION
import unreal


class AyonPluginBackend(UnrealBackend):
    @staticmethod
    def install():
        pass

    @staticmethod
    def ls():
        ar = unreal.AssetRegistryHelpers.get_asset_registry()
        # UE 5.1 changed how class name is specified
        class_name = (
            ["/Script/Ayon", "AyonAssetContainer"]
            if UNREAL_VERSION.major == 5 and UNREAL_VERSION.minor > 0
            else "AyonAssetContainer"
        )  # noqa
        ayon_containers = ar.get_assets_by_class(class_name, True)

        return ayon_containers

    @staticmethod
    def ls_inst():
        ar = unreal.AssetRegistryHelpers.get_asset_registry()
        # UE 5.1 changed how class name is specified
        class_name = (
            ["/Script/Ayon", "AyonPublishInstance"]
            if (UNREAL_VERSION.major == 5 and UNREAL_VERSION.minor > 0)
            else "AyonPublishInstance"
        )  # noqa
        instances = ar.get_assets_by_class(class_name, True)

        return instances

    @staticmethod
    def containerise():
        pass

    @staticmethod
    def imprint(node, data):
        pass

    @staticmethod
    def create_container(container: str, path: str) -> unreal.Object:
        factory = unreal.AyonAssetContainerFactory()
        tools = unreal.AssetToolsHelpers().get_asset_tools()

        return tools.create_asset(container, path, None, factory)

    @staticmethod
    def create_publish_instance(instance: str, path:str) -> unreal.Object:
        factory = unreal.AyonPublishInstanceFactory()
        tools = unreal.AssetToolsHelpers().get_asset_tools()
        return tools.create_asset(instance, path, None, factory)

