# -*- coding: utf-8 -*-
"""Loader for Yeti Cache."""
import json
import os
from ayon_core.pipeline import AYON_CONTAINER_ID
from ayon_core.lib import BoolDef, EnumDef
from ayon_unreal.api import plugin
from ayon_unreal.api import pipeline as unreal_pipeline
import unreal  # noqa


class YetiLoader(plugin.Loader):
    """Load Yeti Cache"""

    product_types = {"yeticacheUE"}
    label = "Import Yeti"
    representations = {"abc"}
    icon = "pagelines"
    color = "orange"

    loaded_asset_dir = "{folder[path]}/{product[name]}_{version[version]}"
    asset_loading_location = "project"

    @classmethod
    def apply_settings(cls, project_settings):
        super(YetiLoader, cls).apply_settings(project_settings)
        # Apply import settings
        unreal_settings = project_settings["unreal"]["import_settings"]
        cls.loaded_asset_dir = unreal_settings["loaded_asset_dir"]
        cls.asset_loading_location = unreal_settings.get(
            "asset_loading_location", cls.asset_loading_location)

    @staticmethod
    def get_task(filename, asset_dir, asset_name, replace):
        task = unreal.AssetImportTask()
        options = unreal.AbcImportSettings()

        task.set_editor_property('filename', filename)
        task.set_editor_property('destination_path', asset_dir)
        task.set_editor_property('destination_name', asset_name)
        task.set_editor_property('replace_existing', replace)
        task.set_editor_property('automated', True)
        task.set_editor_property('save', True)

        task.options = options

        return task

    @staticmethod
    def is_groom_module_active():
        """
        Check if Groom plugin is active.

        This is a workaround, because the Unreal python API don't have
        any method to check if plugin is active.
        """
        prj_file = unreal.Paths.get_project_file_path()

        with open(prj_file, "r") as fp:
            data = json.load(fp)

        plugins = data.get("Plugins")

        if not plugins:
            return False

        plugin_names = [p.get("Name") for p in plugins]

        return "HairStrands" in plugin_names

    def load(self, context, name, namespace, options):
        """Load and containerise representation into Content Browser.

        This is two step process. First, import FBX to temporary path and
        then call `containerise()` on it - this moves all content to new
        directory and then it will create AssetContainer there and imprint it
        with metadata. This will mark this path as container.

        Args:
            context (dict): application context
            name (str): Product name
            namespace (str): in Unreal this is basically path to container.
                             This is not passed here, so namespace is set
                             by `containerise()` because only then we know
                             real path.
            data (dict): Those would be data to be imprinted. This is not used
                         now, data are imprinted by `containerise()`.

        Returns:
            list(str): list of container content

        """
        # Check if Groom plugin is active
        if not self.is_groom_module_active():
            raise RuntimeError("Groom plugin is not activated.")

        # Create directory for asset and Ayon container
        folder_path = context["folder"]["path"]
        suffix = "_CON"
        path = self.filepath_from_context(context)
        ext = os.path.splitext(path)[-1].lstrip(".")
        asset_root, asset_name = unreal_pipeline.format_asset_directory(
            context, self.loaded_asset_dir
        )

        tools = unreal.AssetToolsHelpers().get_asset_tools()
        asset_dir, container_name = tools.create_unique_asset_name(
            asset_root, suffix=f"_{ext}")
        pattern_regex = {
            "name": name,
            "extension": ext
        }
        container_name = f"{container_name}_{suffix}"
        task = None
        if self.asset_loading_location == "follow_existing":
            # Follow the existing version's location
            existing_asset_path = unreal_pipeline.find_existing_asset(
                asset_name, asset_dir, pattern_regex)
            if existing_asset_path:
                asset_dir = unreal.Paths.get_path(existing_asset_path)
        if not unreal.EditorAssetLibrary.does_directory_exist(asset_dir):
            unreal.EditorAssetLibrary.make_directory(asset_dir)
        # Check if the asset already exists
        existing_asset_path =  unreal_pipeline.find_existing_asset(asset_name)
        if existing_asset_path:
            task = self.get_task(
                path, existing_asset_path, asset_name, True)
        else:
            task = self.get_task(path, asset_dir, asset_name, False)

        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])  # noqa: E501

        if not unreal.EditorAssetLibrary.does_asset_exist(
            f"{asset_dir}/{container_name}"):
                # Create Asset Container
                unreal_pipeline.create_container(
                    container=container_name, path=asset_dir)

        data = {
            "schema": "ayon:container-2.0",
            "id": AYON_CONTAINER_ID,
            "namespace": asset_dir,
            "container_name": container_name,
            "folder_path": folder_path,
            "asset_name": asset_name,
            "loader": str(self.__class__.__name__),
            "representation": context["representation"]["id"],
            "parent": context["representation"]["versionId"],
            "product_type": context["product"]["productType"],
            # TODO these shold be probably removed
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
        repre_entity = context["representation"]
        asset_name = container["asset_name"]
        source_path = self.filepath_from_context(context)
        ext = os.path.splitext(source_path)[-1].lstrip(".")
        destination_path = container["namespace"]
        pattern_regex = {
            "name": context["product"]["name"],
            "extension": ext
        }
        task = None
        if self.asset_loading_location == "follow_existing":
            # Follow the existing version's location
            existing_asset_path = unreal_pipeline.find_existing_asset(
                asset_name, destination_path, pattern_regex)
            if existing_asset_path:
                destination_path = unreal.Paths.get_path(existing_asset_path)
        if not unreal.EditorAssetLibrary.does_directory_exist(destination_path):
            unreal.EditorAssetLibrary.make_directory(destination_path)
        # Check if the asset already exists
        existing_asset_path =  unreal_pipeline.find_existing_asset(asset_name)
        if existing_asset_path:
            task = self.get_task(source_path, existing_asset_path, asset_name, True)
        else:
            task = self.get_task(source_path, destination_path, asset_name, False)


        # do import fbx and replace existing data
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

        container_path = f'{container["namespace"]}/{container["objectName"]}'
        # update metadata
        unreal_pipeline.imprint(
            container_path,
            {
                "representation": repre_entity["id"],
                "parent": repre_entity["versionId"],
                "project_name": context["project"]["name"]
            }
        )
        asset_content = unreal.EditorAssetLibrary.list_assets(
            destination_path, recursive=True, include_folder=True
        )

        for a in asset_content:
            unreal.EditorAssetLibrary.save_asset(a)

    def remove(self, container):
        path = container["namespace"]
        if unreal.EditorAssetLibrary.does_directory_exist(path):
            unreal.EditorAssetLibrary.delete_directory(path)
