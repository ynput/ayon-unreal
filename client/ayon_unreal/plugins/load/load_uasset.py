# -*- coding: utf-8 -*-
"""Load UAsset."""
from pathlib import Path
import os
import shutil

from ayon_core.pipeline import AYON_CONTAINER_ID
from ayon_core.lib import EnumDef
from ayon_unreal.api import plugin
from ayon_unreal.api import pipeline as unreal_pipeline
import unreal  # noqa


def parsing_to_absolute_directory(asset_dir):
    if unreal_pipeline.AYON_ROOT_DIR in asset_dir:
        return asset_dir.replace(
            "/Game", Path(unreal.Paths.project_content_dir()).as_posix(),
        1)
    else:
        absolute_path = os.path.join(
            unreal.Paths.project_plugins_dir(), asset_dir)
        return os.path.normpath(absolute_path)


class UAssetLoader(plugin.Loader):
    """Load UAsset."""

    product_types = {"uasset"}
    label = "Load UAsset"
    representations = {"uasset"}
    icon = "cube"
    color = "orange"

    extension = "uasset"

    loaded_asset_dir = "{folder[path]}/{product[name]}_{version[version]}"
    asset_loading_location = "project"

    @classmethod
    def apply_settings(cls, project_settings):
        super(UAssetLoader, cls).apply_settings(project_settings)
        # Apply import settings
        unreal_settings = project_settings["unreal"]["import_settings"]
        cls.loaded_asset_dir = unreal_settings["loaded_asset_dir"]
        cls.asset_loading_location = unreal_settings.get(
            "asset_loading_location", cls.asset_loading_location)

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
        asset_root, asset_name = unreal_pipeline.format_asset_directory(
            context, self.loaded_asset_dir
        )
        tools = unreal.AssetToolsHelpers().get_asset_tools()
        asset_dir, container_name = tools.create_unique_asset_name(
            asset_root, suffix=""
        )
        pattern_regex = {
            "name": name,
            "extension": ""
        }
        container_name = f"{container_name}_{suffix}"
        if self.asset_loading_location == "follow_existing":
            # Follow the existing version's location
            existing_asset_path = unreal_pipeline.find_existing_asset(
                asset_name, asset_dir, pattern_regex)
            if existing_asset_path:
                version_folder = unreal.Paths.split(asset_dir)[1]
                asset_dir = unreal.Paths.get_path(existing_asset_path)
                asset_dir = f"{existing_asset_path}/{version_folder}"
        if not unreal.EditorAssetLibrary.does_directory_exist(asset_dir):
            unreal.EditorAssetLibrary.make_directory(asset_dir)
        # Check if the asset already exists
        existing_asset_path =  unreal_pipeline.find_existing_asset(asset_name)
        if existing_asset_path:
            destination_path = parsing_to_absolute_directory(existing_asset_path)
        else:
            destination_path = parsing_to_absolute_directory(asset_dir)

        path = self.filepath_from_context(context)

        shutil.copy(path, f"{destination_path}/{asset_name}")
        if existing_asset_path:
            unreal.EditorAssetLibrary.rename_asset(
                f"{existing_asset_path}/{asset_name}.{asset_name}",
                f"{asset_dir}/{asset_name}.{asset_name}"
            )
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
            "project_name": context["project"]["name"]
        }

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

        asset_content = unreal.EditorAssetLibrary.list_assets(
            asset_dir, recursive=False, include_folder=True
        )

        for asset in asset_content:
            obj = ar.get_asset_by_object_path(asset).get_asset()
            if obj.get_class().get_name() != "AyonAssetContainer":
                unreal.EditorAssetLibrary.delete_asset(asset)

        update_filepath = self.filepath_from_context(context)
        new_asset_name = os.path.basename(update_filepath)
        pattern_regex = {
            "name": context["product"]["name"],
            "extension": ""
        }
        if self.asset_loading_location == "follow_existing":
            # Follow the existing version's location
            existing_asset_path = unreal_pipeline.find_existing_asset(
                new_asset_name, asset_dir, pattern_regex)
            if existing_asset_path:
                version_folder = unreal.Paths.split(asset_dir)[1]
                asset_dir = unreal.Paths.get_path(existing_asset_path)
                asset_dir = f"{existing_asset_path}/{version_folder}"
        if not unreal.EditorAssetLibrary.does_directory_exist(asset_dir):
            unreal.EditorAssetLibrary.make_directory(asset_dir)
        # Check if the asset already exists
        existing_asset_path =  unreal_pipeline.find_existing_asset(new_asset_name)
        if existing_asset_path:
            destination_path = parsing_to_absolute_directory(existing_asset_path)
        else:
            destination_path = parsing_to_absolute_directory(asset_dir)

        shutil.copy(
            update_filepath, f"{destination_path}/{new_asset_name}")
        if existing_asset_path:
            unreal.EditorAssetLibrary.rename_asset(
                f"{existing_asset_path}/{new_asset_name}.{new_asset_name}",
                f"{asset_dir}/{new_asset_name}.{new_asset_name}"
            )
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


class UMapLoader(UAssetLoader):
    """Load Level."""

    product_types = {"uasset"}
    label = "Load Level"
    representations = {"umap"}

    extension = "umap"
