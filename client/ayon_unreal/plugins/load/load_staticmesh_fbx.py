# -*- coding: utf-8 -*-
"""Load Static meshes form FBX."""
import os

from ayon_core.pipeline import AYON_CONTAINER_ID

from ayon_unreal.api import plugin
from ayon_unreal.api.pipeline import (
    create_container,
    imprint,
    has_asset_directory_pattern_matched,
    format_asset_directory,
    add_assets_to_content_plugin
)
import unreal  # noqa


class StaticMeshFBXLoader(plugin.Loader):
    """Load Unreal StaticMesh from FBX."""

    product_types = {"model", "staticMesh"}
    label = "Import FBX Static Mesh"
    representations = {"fbx"}
    icon = "cube"
    color = "orange"

    use_interchange = False
    use_nanite = True
    show_dialog = False
    pipeline_path = ""
    loaded_asset_dir = "{folder[path]}/{product[name]}_{version[version]}"

    @classmethod
    def apply_settings(cls, project_settings):
        super(StaticMeshFBXLoader, cls).apply_settings(project_settings)
        # Apply import settings
        unreal_settings = project_settings.get("unreal", {})
        import_settings = unreal_settings.get("import_settings", {})
        cls.use_interchange = import_settings.get("interchange", {}).get(
            "enabled", cls.use_interchange
        )
        cls.show_dialog = import_settings.get("show_dialog", cls.show_dialog)
        cls.use_nanite = import_settings.get("use_nanite", cls.use_nanite)
        cls.pipeline_path = import_settings.get("interchange", {}).get(
            "pipeline_path_static_mesh", cls.pipeline_path
        )
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
        cls, filepath, asset_dir, asset_name, container_name, asset_path=None
    ):
        if cls.use_interchange:
            unreal.log("Import using interchange method")
            unreal.SystemLibrary.execute_console_command(None, "Interchange.FeatureFlags.Import.FBX 1")

            import_assetparameters = unreal.ImportAssetParameters()
            editor_asset_subsystem = unreal.EditorAssetSubsystem()
            import_assetparameters.is_automated = not cls.show_dialog

            # The path to the Interchange asset
            tmp_pipeline_path = "/Game/tmp"
            # interchange settings here
            unreal.EditorAssetLibrary.rename_asset(
                f"{cls.pipeline_path}",
                f"{tmp_pipeline_path}/{asset_name}.{asset_name}"
            )

            import_assetparameters.override_pipelines.append(
                unreal.SoftObjectPath(f"{tmp_pipeline_path}.tmp"))

            source_data = unreal.InterchangeManager.create_source_data(filepath)
            interchange_manager = unreal.InterchangeManager.get_interchange_manager_scripted()
            interchange_manager.import_asset(asset_dir, source_data,
                                            import_assetparameters)


            editor_asset_subsystem.delete_asset(tmp_pipeline_path) # remove temp file

        else:
            unreal.log("Import using deferred method")
            task = None
            if asset_path:
                loaded_asset_dir = unreal.Paths.split(asset_path)[0]
                task = cls.get_task(filepath, loaded_asset_dir, asset_name, True)
            else:
                if not unreal.EditorAssetLibrary.does_asset_exist(
                    f"{asset_dir}/{asset_name}"):
                        task = cls.get_task(filepath, asset_dir, asset_name, False)

            unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

        if not unreal.EditorAssetLibrary.does_asset_exist(
            f"{asset_dir}/{container_name}"):
                # Create Asset Container
                create_container(container=container_name, path=asset_dir)

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
        asset_root, asset_name = format_asset_directory(context, self.loaded_asset_dir)

        tools = unreal.AssetToolsHelpers().get_asset_tools()
        asset_dir, container_name = tools.create_unique_asset_name(
            asset_root, suffix=f"_{ext}")

        container_name += suffix
        asset_path = (
            has_asset_directory_pattern_matched(asset_name, asset_dir, name, extension=ext)
            if not self.use_interchange else None
        )
        if not unreal.EditorAssetLibrary.does_directory_exist(asset_dir):
            unreal.EditorAssetLibrary.make_directory(asset_dir)
        self.import_and_containerize(
            path, asset_dir, asset_name,
            container_name, asset_path=asset_path
        )
        if asset_path:
            unreal.EditorAssetLibrary.rename_asset(
                f"{asset_path}",
                f"{asset_dir}/{asset_name}.{asset_name}"
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

        add_assets_to_content_plugin(name, ext, asset_content)

        return asset_content

    def update(self, container, context):
        folder_path = context["folder"]["path"]
        product_type = context["product"]["productType"]
        repre_entity = context["representation"]
        name = context["product"]["name"]

        # Create directory for asset and Ayon container
        suffix = "_CON"
        path = self.filepath_from_context(context)
        ext = os.path.splitext(path)[-1].lstrip(".")
        asset_root, asset_name = format_asset_directory(context, self.loaded_asset_dir)
        tools = unreal.AssetToolsHelpers().get_asset_tools()
        asset_dir, container_name = tools.create_unique_asset_name(
            asset_root, suffix=f"_{ext}")


        container_name += suffix
        asset_path = (
            has_asset_directory_pattern_matched(asset_name, asset_dir, name, extension=ext)
            if not self.use_interchange else None
        )
        if not unreal.EditorAssetLibrary.does_directory_exist(asset_dir):
            unreal.EditorAssetLibrary.make_directory(asset_dir)
        self.import_and_containerize(path, asset_dir, asset_name,
                                     container_name, asset_path=asset_path)
        if asset_path:
            unreal.EditorAssetLibrary.rename_asset(
                f"{asset_path}",
                f"{asset_dir}/{asset_name}.{asset_name}"
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

        add_assets_to_content_plugin(name, ext, asset_content)

    def remove(self, container):
        path = container["namespace"]
        if unreal.EditorAssetLibrary.does_directory_exist(path):
            unreal.EditorAssetLibrary.delete_directory(path)
