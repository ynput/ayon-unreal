# -*- coding: utf-8 -*-
"""Load UAsset."""
from pathlib import Path
import os
import shutil

from ayon_core.pipeline import AYON_CONTAINER_ID
from ayon_core.lib import BoolDef, EnumDef
from ayon_unreal.api import plugin
from ayon_unreal.api import pipeline as unreal_pipeline
import unreal  # noqa


class UAssetLoader(plugin.Loader):
    """Load UAsset."""

    product_types = {"uasset"}
    label = "Load UAsset"
    representations = {"uasset"}
    icon = "cube"
    color = "orange"

    extension = "uasset"

    loaded_asset_dir = "{folder[path]}/{product[name]}_{version[version]}"
    content_plugin_enabled = False
    content_plugin_path = []

    @classmethod
    def apply_settings(cls, project_settings):
        super(UAssetLoader, cls).apply_settings(project_settings)
        # Apply import settings
        unreal_settings = project_settings["unreal"]["import_settings"]
        cls.loaded_asset_dir = unreal_settings["loaded_asset_dir"]
        if unreal_settings.get("content_plugin", {}):
            cls.content_plugin_enabled = (
                unreal_settings["content_plugin"]["enabled"]
            )
            cls.content_plugin_path = (
                unreal_settings["content_plugin"]["content_plugin_name"]
            )

    @classmethod
    def get_options(cls, contexts):
        default_content_plugin = next(
            (path for path in cls.content_plugin_path), "")
        return [
            BoolDef(
                "content_plugin_enabled",
                label="Content Plugin",
                default=cls.content_plugin_enabled
            ),
            EnumDef(
                "content_plugin_name",
                label="Content Plugin Name",
                items=[path for path in cls.content_plugin_path],
                default=default_content_plugin
            )
        ]

    def load(self, context, name, namespace, options):
        """Load and containerise representation into Content Browser.

        Args:
            context (dict): application context
            name (str): Product name
            namespace (str): in Unreal this is basically path to container.
                             This is not passed here, so namespace is set
                             by `containerise()` because only then we know
                             real path.
            options (dict): Those would be data to be imprinted. This is not
                used now, data are imprinted by `containerise()`.

        Returns:
            list(str): list of container content
        """

        # Create directory for asset and Ayon container
        folder_path = context["folder"]["path"]
        suffix = "_CON"
        use_content_plugin = options.get("content_plugin_enabled", False)
        content_plugin_name = options.get(
            "content_plugin_name",
            next((path for path in self.content_plugin_path), "")
        )
        asset_root, asset_name = unreal_pipeline.format_asset_directory(
            context, self.loaded_asset_dir,
            use_content_plugin, content_plugin_name
        )
        tools = unreal.AssetToolsHelpers().get_asset_tools()
        asset_dir, container_name = tools.create_unique_asset_name(
            asset_root, suffix=""
        )
        container_name = f"{container_name}_{suffix}"
        if not unreal.EditorAssetLibrary.does_directory_exist(asset_dir):
            unreal.EditorAssetLibrary.make_directory(asset_dir)
        if use_content_plugin:
            abs_content_plugin_path = os.path.join(
                unreal.Paths.project_plugins_dir(), content_plugin_name)
            destination_path = asset_dir.replace(
                f"/{content_plugin_name}",
                Path(abs_content_plugin_path).as_posix(), 1
            )
        else:
            destination_path = asset_dir.replace(
                "/Game", Path(unreal.Paths.project_content_dir()).as_posix(), 1)

        path = self.filepath_from_context(context)
        asset_name = os.path.basename(path)
        asset_path = unreal_pipeline.has_asset_directory_pattern_matched(
            asset_name, asset_dir, name)
        if asset_path:
            destination_path = unreal.Paths.split(asset_path)[0]
        shutil.copy(path, f"{destination_path}/{asset_name}")

        if not unreal.EditorAssetLibrary.does_asset_exist(
            f"{asset_dir}/{container_name}"):
                # Create Asset Container
                unreal_pipeline.create_container(
                    container=container_name, path=asset_dir)

        data = {
            "schema": "ayon:container-2.0",
            "id": AYON_CONTAINER_ID,
            "namespace": asset_dir,
            "folder_path": folder_path,
            "container_name": container_name,
            "asset_name": asset_name,
            "loader": str(self.__class__.__name__),
            "representation": context["representation"]["id"],
            "parent": context["representation"]["versionId"],
            "product_type": context["product"]["productType"],
            # TODO these should be probably removed
            "asset": folder_path,
            "family": context["product"]["productType"],
            "asset_path": asset_path,
            "project_name": context["project"]["name"]
        }
        if content_plugin_name:
            data["content_plugin_name"] = content_plugin_name

        if asset_path:
            unreal.EditorAssetLibrary.rename_asset(
                f"{asset_path}",
                f"{asset_dir}/{asset_name}.{asset_name}"
            )

        unreal_pipeline.imprint(f"{asset_dir}/{container_name}", data)

        asset_content = unreal.EditorAssetLibrary.list_assets(
            asset_dir, recursive=True, include_folder=True
        )

        for a in asset_content:
            unreal.EditorAssetLibrary.save_asset(a)

        return asset_content

    def update(self, container, context):
        ar = unreal.AssetRegistryHelpers.get_asset_registry()

        asset_dir = container["namespace"]
        repre_entity = context["representation"]
        name = context["product"]["name"]

        destination_path = asset_dir.replace(
            "/Game", Path(unreal.Paths.project_content_dir()).as_posix(), 1)
        if container.get("content_plugin_path", ""):
            plugin_path = container["content_plugin_path"]
            abs_content_plugin_path = os.path.join(
                unreal.Paths.project_plugins_dir(), plugin_path)
            destination_path = asset_dir.replace(
                f"/{plugin_path}",
                Path(abs_content_plugin_path).as_posix(), 1
            )

        asset_content = unreal.EditorAssetLibrary.list_assets(
            asset_dir, recursive=False, include_folder=True
        )

        for asset in asset_content:
            obj = ar.get_asset_by_object_path(asset).get_asset()
            if obj.get_class().get_name() != "AyonAssetContainer":
                unreal.EditorAssetLibrary.delete_asset(asset)

        update_filepath = self.filepath_from_context(context)
        new_asset_name = os.path.basename(update_filepath)
        asset_path = unreal_pipeline.has_asset_directory_pattern_matched(
            new_asset_name, asset_dir, name)


        if asset_path:
            unreal.EditorAssetLibrary.rename_asset(
                f"{asset_path}",
                f"{asset_dir}/{new_asset_name}.{new_asset_name}"
            )
        else:
            shutil.copy(
                update_filepath, f"{destination_path}/{new_asset_name}")

        container_path = f'{container["namespace"]}/{container["objectName"]}'
        # update metadata
        unreal_pipeline.imprint(
            container_path,
            {
                "asset_name": new_asset_name,
                "representation": repre_entity["id"],
                "parent": repre_entity["versionId"],
                "project_name": context["project"]["name"]
            }
        )

        asset_content = unreal.EditorAssetLibrary.list_assets(
            asset_dir, recursive=True, include_folder=True
        )

        for a in asset_content:
            unreal.EditorAssetLibrary.save_asset(a)

    def remove(self, container):
        path = container["namespace"]
        if unreal.EditorAssetLibrary.does_directory_exist(path):
            unreal.EditorAssetLibrary.delete_directory(path)
        unreal_pipeline.remove_asset_from_content_plugin(container)


class UMapLoader(UAssetLoader):
    """Load Level."""

    product_types = {"uasset"}
    label = "Load Level"
    representations = {"umap"}

    extension = "umap"
