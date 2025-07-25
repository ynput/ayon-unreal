# -*- coding: utf-8 -*-
"""Load Static meshes from USD using Interchange."""
import os

from ayon_core.pipeline import AYON_CONTAINER_ID

from ayon_unreal.api import plugin
from ayon_unreal.api.pipeline import (
    create_container,
    imprint,
    format_asset_directory,
    get_dir_from_existing_asset
)
import unreal  # noqa


class StaticMeshUSDLoader(plugin.Loader):
    """Load Unreal StaticMesh from USD."""

    #product_types = {"usd", "staticMesh"}
    #product_types = {"model", "staticMesh"}
    #representations = {"usd"}

    label = "Import USD"
    representations = {"*"}
    extensions = {"usd", "usda", "usdc", "usdz"}
    product_types = {"*"}

    icon = "cube"
    color = "orange"

    use_nanite = True
    show_dialog = False
    loaded_asset_dir = "{folder[path]}/{product[name]}_{version[version]}"

    @classmethod
    def apply_settings(cls, project_settings):
        super(StaticMeshUSDLoader, cls).apply_settings(project_settings)

        unreal_settings = project_settings.get("unreal", {})
        import_settings = unreal_settings.get("import_settings", {})

        cls.show_dialog = import_settings.get("show_dialog", cls.show_dialog)
        cls.save_asset_after_import = import_settings.get("save_asset_after_import")

        cls.loaded_asset_dir = import_settings.get("loaded_asset_dir", cls.loaded_asset_dir)
        cls.use_nanite = import_settings.get("use_nanite", cls.use_nanite)
        cls.asset_type_sub_folders = import_settings.get("use_asset_type_sub_folders")
        cls.import_static_meshes = import_settings.get("import_static_meshes")
        cls.combine_static_meshes = import_settings.get("combine_static_meshes")
        cls.bake_meshes = import_settings.get("bake_meshes")
        cls.import_collisions = import_settings.get("import_collisions")
        cls.import_skeletal_meshes = import_settings.get("import_skeletal_meshes")
        cls.import_animation = import_settings.get("import_animations")
        cls.import_materials = import_settings.get("import_materials")
        cls.import_textures = import_settings.get("import_textures")
  
    @classmethod
    def import_and_containerize(cls, filepath, asset_dir, container_name):
        if not unreal.EditorAssetLibrary.does_directory_exist(asset_dir):
            unreal.EditorAssetLibrary.make_directory(asset_dir)


        unreal.log(f"🔄 Starting USD import from: {filepath}")

        # ADDED INTERCHANGE OPTIONS
        editor_asset_subsystem = unreal.get_editor_subsystem(unreal.EditorAssetSubsystem)

        # Clear Automation asset if it exists
        transient_path = "/Interchange/Pipelines/Transient/"
        transient_pipeline_path = transient_path + "MyAutomationPipeline"

        if unreal.EditorAssetLibrary.does_directory_exist(transient_path):
            editor_asset_subsystem.delete_directory(transient_path)

        # Duplicate Pipeline Asset Config
        pipeline = editor_asset_subsystem.duplicate_asset("/Interchange/Pipelines/DefaultAssetsPipeline", transient_pipeline_path)

        # Set pipeline defaults
        pipeline.asset_type_sub_folders = cls.asset_type_sub_folders
        pipeline.common_meshes_properties.bake_meshes = cls.bake_meshes

        # Mesh Pipeline Options
        pipeline.mesh_pipeline.combine_static_meshes = cls.combine_static_meshes
        pipeline.mesh_pipeline.import_static_meshes = cls.import_static_meshes
        pipeline.mesh_pipeline.collision = cls.import_collisions
        pipeline.mesh_pipeline.import_skeletal_meshes = cls.import_skeletal_meshes

        # Animation Pipeline Options
        pipeline.animation_pipeline.import_animations = cls.import_animation

        # Material Pipeline
        pipeline.material_pipeline.import_materials = cls.import_materials
        pipeline.material_pipeline.texture_pipeline.import_textures = cls.import_textures

        import_params = unreal.ImportAssetParameters()
        import_params.is_automated = not cls.show_dialog

        # Override pipeline path
        import_params.override_pipelines.append(unreal.SoftObjectPath(transient_pipeline_path + ".MyAutomationPipeline"))
        ## END INTERCHANGE OPTIONS

        source_data = unreal.InterchangeManager.create_source_data(filepath)
        manager = unreal.InterchangeManager.get_interchange_manager_scripted()
        imported_assets = manager.import_asset(asset_dir, source_data, import_params)

        ##Delete Transient Path
        editor_asset_subsystem.delete_directory(transient_path)

        if not imported_assets:
            unreal.log_warning(f"❌ USD Import failed or no assets found at: {filepath}")
        else:
            unreal.log(f"✅ USD Import success: {imported_assets}")

        # Double-check whether anything now exists in the directory
        assets_in_dir = unreal.EditorAssetLibrary.list_assets(asset_dir, recursive=True)
        if not assets_in_dir:
            unreal.log_error(f"❌ Still no assets found in: {asset_dir} — import may have failed.")
        else:
            unreal.log(f"📁 Assets found in {asset_dir}: {assets_in_dir}")

        # Create AYON container if needed
        if not unreal.EditorAssetLibrary.does_asset_exist(f"{asset_dir}/{container_name}"):
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
        project_name,
        layout
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
            "asset": folder_path,
            "family": product_type,
            "project_name": project_name,
            "layout": layout
        }
        imprint(f"{asset_dir}/{container_name}", data)

    def load(self, context, name, namespace, options):
        folder_path = context["folder"]["path"]
        suffix = "_CON"
        path = self.filepath_from_context(context)
        ext = os.path.splitext(path)[-1].lstrip(".")
        asset_root, asset_name = format_asset_directory(context, self.loaded_asset_dir)

        tools = unreal.AssetToolsHelpers().get_asset_tools()
        asset_dir, container_name = tools.create_unique_asset_name(
            asset_root, suffix=f"_{ext}")
        container_name += suffix

        should_use_layout = options.get("layout", False)

        if should_use_layout and (
            existing_asset_dir := get_dir_from_existing_asset(asset_dir, asset_name)
        ):
            asset_dir = existing_asset_dir
        else:
            asset_dir = self.import_and_containerize(path, asset_dir, container_name)

        self.imprint(
            folder_path,
            asset_dir,
            container_name,
            asset_name,
            context["representation"],
            context["product"]["productType"],
            context["project"]["name"],
            should_use_layout
        )

        asset_content = unreal.EditorAssetLibrary.list_assets(
            asset_dir, recursive=True, include_folder=True)

        if self.save_asset_after_import:
            for a in asset_content:
                unreal.EditorAssetLibrary.save_asset(a)

        return asset_content

    def update(self, container, context):
        folder_path = context["folder"]["path"]
        product_type = context["product"]["productType"]
        repre_entity = context["representation"]

        suffix = "_CON"
        path = self.filepath_from_context(context)
        ext = os.path.splitext(path)[-1].lstrip(".")
        asset_root, asset_name = format_asset_directory(
            context, self.loaded_asset_dir)

        tools = unreal.AssetToolsHelpers().get_asset_tools()
        asset_dir, container_name = tools.create_unique_asset_name(
            asset_root, suffix=f"_{ext}")
        container_name += suffix

        should_use_layout = container.get("layout", False)

        if should_use_layout and (
            existing_asset_dir := get_dir_from_existing_asset(asset_dir, asset_name)
        ):
            asset_dir = existing_asset_dir
        else:
            asset_dir = self.import_and_containerize(path, asset_dir, container_name)

        self.imprint(
            folder_path,
            asset_dir,
            container_name,
            asset_name,
            repre_entity,
            product_type,
            context["project"]["name"],
            should_use_layout
        )

        asset_content = unreal.EditorAssetLibrary.list_assets(
            asset_dir, recursive=True, include_folder=False)

        if self.save_asset_after_import:
            for a in asset_content:
                unreal.EditorAssetLibrary.save_asset(a)

    def remove(self, container):
        path = container["namespace"]
        if unreal.EditorAssetLibrary.does_directory_exist(path):
            unreal.EditorAssetLibrary.delete_directory(path)
