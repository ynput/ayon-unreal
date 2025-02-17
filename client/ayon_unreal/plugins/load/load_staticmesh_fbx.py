# -*- coding: utf-8 -*-
"""Load Static meshes form FBX."""
import os

from ayon_core.pipeline import AYON_CONTAINER_ID

from ayon_unreal.api import plugin
from ayon_unreal.api.pipeline import (
    create_container,
    imprint,
    format_asset_directory,
    find_existing_asset,
)
import unreal  # noqa


class StaticMeshFBXLoader(plugin.Loader):
    """Load Unreal StaticMesh from FBX."""

    product_types = {"model", "staticMesh"}
    label = "Import FBX Static Mesh"
    representations = {"fbx"}
    icon = "cube"
    color = "orange"

    use_nanite = True
    show_dialog = False
    loaded_asset_dir = "{folder[path]}/{product[name]}_{version[version]}"
    asset_loading_location = "project"

    @classmethod
    def apply_settings(cls, project_settings):
        super(StaticMeshFBXLoader, cls).apply_settings(project_settings)
        # Apply import settings
        unreal_settings = project_settings.get("unreal", {})
        import_settings = unreal_settings.get("import_settings", {})
        cls.show_dialog = import_settings.get("show_dialog", cls.show_dialog)
        cls.use_nanite = import_settings.get("use_nanite", cls.use_nanite)
        cls.loaded_asset_dir = import_settings.get(
            "loaded_asset_dir", cls.loaded_asset_dir)

    @classmethod
    def get_task(cls, filename, asset_dir, asset_name, replace):
        task = unreal.AssetImportTask()
        options = unreal.FbxImportUI()
        import_data = unreal.FbxStaticMeshImportData()

        task.set_editor_property('filename', filename)
        task.set_editor_property('destination_path', asset_dir)
        task.set_editor_property('destination_name', asset_name)
        task.set_editor_property('replace_existing', replace)
        task.set_editor_property('automated', not cls.show_dialog)
        task.set_editor_property('save', True)

        # set import options here
        options.set_editor_property(
            'automated_import_should_detect_type', False)
        options.set_editor_property('import_animations', False)

        import_data.set_editor_property('combine_meshes', True)
        import_data.set_editor_property('remove_degenerates', False)
        import_data.set_editor_property('build_nanite', cls.use_nanite) #nanite

        options.static_mesh_import_data = import_data
        task.options = options

        return task

    @classmethod
    def import_and_containerize(
        cls, filepath, asset_dir, asset_name, container_name,
        pattern_regex
    ):
        # Determine where to load the asset based on settings
        if cls.asset_loading_location == "follow_existing":
            # Follow the existing version's location
            existing_asset_path = find_existing_asset(
                asset_name, asset_dir, pattern_regex
            )
            if existing_asset_path:
                version_folder = unreal.Paths.split(asset_dir)[1]
                asset_dir = unreal.Paths.get_path(existing_asset_path)
                asset_dir = f"{existing_asset_path}/{version_folder}"

        if not unreal.EditorAssetLibrary.does_directory_exist(asset_dir):
            unreal.EditorAssetLibrary.make_directory(asset_dir)

        unreal.log("Import using interchange method")
        unreal.SystemLibrary.execute_console_command(None, "Interchange.FeatureFlags.Import.FBX 1")

        import_asset_parameters = unreal.ImportAssetParameters()
        import_asset_parameters.is_automated = not cls.show_dialog

        source_data = unreal.InterchangeManager.create_source_data(filepath)
        interchange_manager = unreal.InterchangeManager.get_interchange_manager_scripted()
        interchange_manager.import_asset(asset_dir, source_data, import_asset_parameters)

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
        ext = os.path.splitext(path)[-1].lstrip(".")
        asset_root, asset_name = format_asset_directory(
            context, self.loaded_asset_dir
        )

        tools = unreal.AssetToolsHelpers().get_asset_tools()
        asset_dir, container_name = tools.create_unique_asset_name(
            asset_root, suffix=f"_{ext}")

        container_name += suffix
        pattern_regex = {
            "name": name,
            "extension": ext
        }

        asset_dir = self.import_and_containerize(
            path, asset_dir, asset_name,
            container_name, pattern_regex
        )

        self.imprint(
            folder_path,
            asset_dir,
            container_name,
            asset_name,
            context["representation"],
            context["product"]["productType"],
            context["project"]["name"]
        )

        asset_content = unreal.EditorAssetLibrary.list_assets(
            asset_dir, recursive=True, include_folder=True
        )

        for a in asset_content:
            unreal.EditorAssetLibrary.save_asset(a)

        return asset_content

    def update(self, container, context):
        folder_path = context["folder"]["path"]
        product_type = context["product"]["productType"]
        repre_entity = context["representation"]

        # Create directory for asset and Ayon container
        suffix = "_CON"
        path = self.filepath_from_context(context)
        ext = os.path.splitext(path)[-1].lstrip(".")

        asset_root, asset_name = format_asset_directory(
            context, self.loaded_asset_dir
        )
        tools = unreal.AssetToolsHelpers().get_asset_tools()
        asset_dir, container_name = tools.create_unique_asset_name(
            asset_root, suffix=f"_{ext}")

        container_name += suffix
        pattern_regex = {
            "name": context["product"]["name"],
            "extension": ext
        }
        asset_dir = self.import_and_containerize(
            path, asset_dir, asset_name,
            container_name, pattern_regex
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

        asset_content = unreal.EditorAssetLibrary.list_assets(
            asset_dir, recursive=True, include_folder=False
        )

        for a in asset_content:
            unreal.EditorAssetLibrary.save_asset(a)

    def remove(self, container):
        path = container["namespace"]
        if unreal.EditorAssetLibrary.does_directory_exist(path):
            unreal.EditorAssetLibrary.delete_directory(path)
