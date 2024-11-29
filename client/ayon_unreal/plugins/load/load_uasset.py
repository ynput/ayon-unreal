# -*- coding: utf-8 -*-
"""Load UAsset."""
from pathlib import Path
import os
import shutil

from ayon_core.pipeline import (
    get_representation_path,
    AYON_CONTAINER_ID
)
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

    @classmethod
    def apply_settings(cls, project_settings):
        super(UAssetLoader, cls).apply_settings(project_settings)
        # Apply import settings
        cls.loaded_asset_dir = (
            project_settings["unreal"]
                            ["import_settings"]
                            ["loaded_asset_dir"]
        )

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
        asset_root, asset_name = unreal_pipeline.format_asset_directory(context, self.loaded_asset_dir)
        tools = unreal.AssetToolsHelpers().get_asset_tools()
        asset_dir, container_name = tools.create_unique_asset_name(
            asset_root, suffix=""
        )
        container_name = f"{container_name}_{suffix}"
        if not unreal.EditorAssetLibrary.does_directory_exist(asset_dir):
            unreal.EditorAssetLibrary.make_directory(asset_dir)

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
            "asset_path": asset_path
        }

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

        destination_path = asset_dir.replace(
            "/Game", Path(unreal.Paths.project_content_dir()).as_posix(), 1)

        asset_content = unreal.EditorAssetLibrary.list_assets(
            asset_dir, recursive=False, include_folder=True
        )

        for asset in asset_content:
            obj = ar.get_asset_by_object_path(asset).get_asset()
            if obj.get_class().get_name() != "AyonAssetContainer":
                unreal.EditorAssetLibrary.delete_asset(asset)

        update_filepath = get_representation_path(repre_entity)
        new_asset_name = os.path.basename(update_filepath)
        shutil.copy(update_filepath, f"{destination_path}/{new_asset_name}")

        container_path = f'{container["namespace"]}/{container["objectName"]}'
        # update metadata
        unreal_pipeline.imprint(
            container_path,
            {
                "representation": repre_entity["id"],
                "parent": repre_entity["versionId"],
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
