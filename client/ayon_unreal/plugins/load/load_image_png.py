# -*- coding: utf-8 -*-
"""Load textures from PNG."""
from ayon_core.pipeline import AYON_CONTAINER_ID
from ayon_unreal.api import plugin
from ayon_unreal.api.pipeline import (
    create_container,
    imprint,
    format_asset_directory
)

import unreal  # noqa


class TexturePNGLoader(plugin.Loader):
    """Load Unreal texture from PNG file."""

    product_types = {"image", "texture", "render"}
    label = "Import image texture 2d"
    representations = {"*"}
    extensions = {"png", "jpg", "tiff", "exr"}
    icon = "wallpaper"
    color = "orange"

    # Defined by settings
    show_dialog = False
    loaded_asset_dir = "{folder[path]}/{product[name]}_{version[version]}"
    loaded_asset_name = "{folder[name]}_{product[name]}_{version[version]}_{representation[name]}"      # noqa

    @classmethod
    def apply_settings(cls, project_settings):
        super(TexturePNGLoader, cls).apply_settings(project_settings)
        unreal_settings = project_settings.get("unreal", {})
        # Apply import settings
        import_settings = unreal_settings.get("import_settings", {})
        cls.show_dialog = import_settings.get("show_dialog", cls.show_dialog)
        cls.loaded_asset_dir = import_settings.get("loaded_asset_dir", cls.loaded_asset_dir)
        cls.loaded_asset_name = import_settings.get("loaded_asset_name", cls.loaded_asset_name)

    @classmethod
    def get_task(cls, filename, asset_dir, asset_name, replace):
        task = unreal.AssetImportTask()

        task.set_editor_property('filename', filename)
        task.set_editor_property('destination_path', asset_dir)
        task.set_editor_property('destination_name', asset_name)
        task.set_editor_property('replace_existing', replace)
        task.set_editor_property('automated', bool(not cls.show_dialog))
        task.set_editor_property('save', True)

        # set import options here

        return task

    @classmethod
    def import_and_containerize(
        self, filepath, asset_dir, container_name
    ):
        if not unreal.EditorAssetLibrary.does_directory_exist(asset_dir):
            unreal.EditorAssetLibrary.make_directory(asset_dir)

        unreal.log("Import using interchange method")
        unreal.SystemLibrary.execute_console_command(
            None, "Interchange.FeatureFlags.Import.PNG 1")
        unreal.SystemLibrary.execute_console_command(
            None, "Interchange.FeatureFlags.Import.JPG 1")
        unreal.SystemLibrary.execute_console_command(
            None, "Interchange.FeatureFlags.Import.TIFF 1")
        unreal.SystemLibrary.execute_console_command(
            None, "Interchange.FeatureFlags.Import.EXR 1")

        import_asset_parameters = unreal.ImportAssetParameters()
        import_asset_parameters.is_automated = bool(not self.show_dialog)

        source_data = unreal.InterchangeManager.create_source_data(filepath)
        interchange_manager = unreal.InterchangeManager.get_interchange_manager_scripted()  # noqa
        interchange_manager.import_asset(
            asset_dir, source_data,import_asset_parameters
        )

        if not unreal.EditorAssetLibrary.does_asset_exist(
            f"{asset_dir}/{container_name}"):
                # Create Asset Container
                create_container(container=container_name, path=asset_dir)

        return asset_dir

    def imprint(
        self,
        folder_path,
        asset_dir,
        container_name,
        asset_name,
        repre_entity,
        product_type,
        project_name
    ):
        data = {
            "schema": "ayon:container-2.0",
            "id": AYON_CONTAINER_ID,
            "namespace": asset_dir,
            "folder_path": folder_path,
            "container_name": container_name,
            "asset_name": asset_name,
            "loader": str(self.__class__.__name__),
            "representation": repre_entity["id"],
            "parent": repre_entity["versionId"],
            "product_type": product_type,
            # TODO these shold be probably removed
            "asset": folder_path,
            "family": product_type,
            "project_name": project_name
        }
        imprint(f"{asset_dir}/{container_name}", data)

    def load(self, context, name, namespace, options):
        """Load and containerise representation into Content Browser.

        Args:
            context (dict): application context
            name (str): Product name
            namespace (str): in Unreal this is basically path to container.
                             This is not passed here, so namespace is set
                             by `containerise()` because only then we know
                             real path.
            options (dict): Those would be data to be imprinted.

        Returns:
            list(str): list of container content
        """
        # Create directory for asset and Ayon container
        folder_path = context["folder"]["path"]
        suffix = "_CON"
        path = self.filepath_from_context(context)
        asset_root, asset_name = format_asset_directory(
            context, self.loaded_asset_dir, self.loaded_asset_name
        )
        tools = unreal.AssetToolsHelpers().get_asset_tools()
        asset_dir, container_name = tools.create_unique_asset_name(
            asset_root, suffix="")

        container_name += suffix

        asset_dir = self.import_and_containerize(
            path, asset_dir, container_name
        )
        self.imprint(
            folder_path,
            asset_dir,
            container_name,
            asset_name,
            context["representation"],
            context["product"]["productType"],
            context["project"]["name"],
        )

        asset_contents = unreal.EditorAssetLibrary.list_assets(
            asset_dir, recursive=True, include_folder=True
        )
        for unreal_asset in asset_contents:
            unreal.EditorAssetLibrary.save_asset(unreal_asset)

        return asset_contents

    def update(self, container, context):
        folder_path = context["folder"]["path"]
        product_type = context["product"]["productType"]
        repre_entity = context["representation"]
        path = self.filepath_from_context(context)

        # Create directory for asset and Ayon container
        suffix = "_CON"

        asset_root, asset_name = format_asset_directory(
            context, self.loaded_asset_dir, self.loaded_asset_name
        )
        tools = unreal.AssetToolsHelpers().get_asset_tools()
        asset_dir, container_name = tools.create_unique_asset_name(
            asset_root, suffix="")
        container_name += suffix
        asset_dir = self.import_and_containerize(
            path, asset_dir, container_name
        )

        self.imprint(
            folder_path,
            asset_dir,
            container_name,
            asset_name,
            repre_entity,
            product_type,
            context["project"]["name"]
        )

        asset_contents = unreal.EditorAssetLibrary.list_assets(
            asset_dir, recursive=True, include_folder=False
        )
        for unreal_asset in asset_contents:
            unreal.EditorAssetLibrary.save_asset(unreal_asset)

    def remove(self, container):
        path = container["namespace"]
        if unreal.EditorAssetLibrary.does_directory_exist(path):
            unreal.EditorAssetLibrary.delete_directory(path)
