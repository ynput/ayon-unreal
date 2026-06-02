# -*- coding: utf-8 -*-
"""Load Skeletal Meshes form FBX."""
from __future__ import annotations

from ayon_core.pipeline import AYON_CONTAINER_ID
from ayon_unreal.api import plugin
from ayon_unreal.api.pipeline import (
    create_container,
    _imprint,
    format_asset_directory,
    get_dir_from_existing_asset
)
import unreal  # noqa


class SkeletalMeshFBXLoader(plugin.Loader):
    """Load Unreal SkeletalMesh from FBX."""

    product_base_types = {"rig", "skeletalMesh"}
    product_types = product_base_types
    label = "Import FBX Skeletal Mesh"
    representations = {"*"}
    extensions = {"fbx"}
    icon = "cube"
    color = "orange"

    loaded_asset_dir = "{folder[path]}/{product[name]}_{version[version]}"
    loaded_asset_name = "{folder[name]}_{product[name]}_{version[version]}_{representation[name]}"      # noqa
    show_dialog = False

    @classmethod
    def apply_settings(cls, project_settings):
        unreal_settings = project_settings["unreal"]["import_settings"]
        super(SkeletalMeshFBXLoader, cls).apply_settings(project_settings)
        cls.loaded_asset_dir = unreal_settings["loaded_asset_dir"]
        cls.loaded_asset_name = unreal_settings["loaded_asset_name"]
        cls.show_dialog = unreal_settings["show_dialog"]

    @classmethod
    def get_task(cls, filename, asset_dir, asset_name, replace):
        task = unreal.AssetImportTask()
        options = unreal.FbxImportUI()

        task.set_editor_property('filename', filename)
        task.set_editor_property('destination_path', asset_dir)
        task.set_editor_property('destination_name', asset_name)
        task.set_editor_property('replace_existing', replace)
        task.set_editor_property('automated', not cls.show_dialog)
        task.set_editor_property('save', True)

        options.set_editor_property(
            'automated_import_should_detect_type', False)
        options.set_editor_property('import_as_skeletal', True)
        options.set_editor_property('import_animations', False)
        options.set_editor_property('import_mesh', True)
        options.set_editor_property('import_materials', False)
        options.set_editor_property('import_textures', False)
        options.set_editor_property('skeleton', None)
        options.set_editor_property('create_physics_asset', False)

        options.set_editor_property(
            'mesh_type_to_import',
            unreal.FBXImportType.FBXIT_SKELETAL_MESH)

        options.skeletal_mesh_import_data.set_editor_property(
            'import_content_type',
            unreal.FBXImportContentType.FBXICT_ALL)

        options.skeletal_mesh_import_data.set_editor_property(
            'normal_import_method',
            unreal.FBXNormalImportMethod.FBXNIM_IMPORT_NORMALS)

        task.options = options

        return task


    def import_and_containerize(
        self, filepath, asset_dir, asset_name, container_name
    ):
        task = None
        if not unreal.EditorAssetLibrary.does_directory_exist(asset_dir):
            unreal.EditorAssetLibrary.make_directory(asset_dir)
        if not unreal.EditorAssetLibrary.does_asset_exist(
            f"{asset_dir}/{asset_name}"):
                task = self.get_task(filepath, asset_dir, asset_name, False)

        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

        if not unreal.EditorAssetLibrary.does_asset_exist(
            f"{asset_dir}/{container_name}"):
                # Create Asset Container
                create_container(container=container_name, path=asset_dir)

        return asset_dir

    def imprint(
        self,
        folder_path: str,
        asset_dir: str,
        container_name: str,
        asset_name: str,
        representation: dict,
        project_name: str,
        product_base_type: str,
        *,
        layout: bool,
    ) -> None:
        """Imprint AYON_CONTAINER_ID to the container asset.

        Args:
            folder_path (str): Path to the folder in Unreal Content Browser.
            asset_dir (str): Directory of the asset in Unreal Content Browser.
            container_name (str): Name of the container asset.
            asset_name (str): Name of the main asset.
            representation (dict): Representation data to imprint.
            product_base_type (str): Product base type to imprint.
            project_name (str): Name of the project to imprint.
            layout (bool): Whether the container is created with layout.

        Todo (antirotor):
            This per loader imprint is wrong and should be moved to some
            common place, custom data usage should be re-evaluated.

        """
        data = {
            "schema": "ayon:container-2.0",
            "id": AYON_CONTAINER_ID,
            "folder_path": folder_path,
            "namespace": asset_dir,
            "container_name": container_name,
            "asset_name": asset_name,
            "loader": str(self.__class__.__name__),
            "representation": representation["id"],
            "parent": representation["versionId"],
            "product_base_type": product_base_type,
            # TODO these should be probably removed
            "asset": folder_path,
            "family": product_base_type,
            "project_name": project_name,
            "layout": layout
        }
        _imprint(f"{asset_dir}/{container_name}", data)

    def load(self, context, name, namespace, options):
        """Load and containerise representation into Content Browser.

        Args:
            context (dict): application context
            name (str): Product name
            namespace (str): in Unreal this is basically path to container.
                             This is not passed here, so namespace is set
                             by `containerise()` because only then we know
                             real path.
            data (dict): Those would be data to be imprinted.

        Returns:
            list(str): list of container content
        """
        # Create directory for asset and Ayon container
        folder_name = context["folder"]["name"]
        product_base_type = context["product"]["productBaseType"]
        suffix = "_CON"
        path = self.filepath_from_context(context)
        asset_root, asset_name = format_asset_directory(
            context, self.loaded_asset_dir, self.loaded_asset_name
        )

        tools = unreal.AssetToolsHelpers().get_asset_tools()
        asset_dir, container_name = tools.create_unique_asset_name(
            asset_root, suffix="")

        container_name += suffix
        should_use_layout = options.get("layout", False)

        # Get existing asset dir if possible, otherwise import & containerize
        if should_use_layout and (
            existing_asset_dir := get_dir_from_existing_asset(
                 asset_dir, asset_name)
            ):
                asset_dir = existing_asset_dir
        else:
            asset_dir = self.import_and_containerize(
                path, asset_dir, asset_name, container_name
            )

        self.imprint(
            folder_path=folder_name,
            asset_dir=asset_dir,
            container_name=container_name,
            asset_name=asset_name,
            representation=context["representation"],
            product_base_type=product_base_type,
            project_name=context["project"]["name"],
            layout=should_use_layout,
        )
        asset_content = unreal.EditorAssetLibrary.list_assets(
            asset_dir, recursive=True, include_folder=True
        )

        for a in asset_content:
            unreal.EditorAssetLibrary.save_asset(a)

        return asset_content

    def update(self, container, context):
        folder_path = context["folder"]["path"]
        product_base_type = context["product"]["productBaseType"]
        repre_entity = context["representation"]

        # Create directory for asset and Ayon container
        suffix = "_CON"
        path = self.filepath_from_context(context)

        asset_root, asset_name = format_asset_directory(
            context, self.loaded_asset_dir, self.loaded_asset_name
        )
        tools = unreal.AssetToolsHelpers().get_asset_tools()
        asset_dir, container_name = tools.create_unique_asset_name(
            asset_root, suffix="")

        container_name += suffix
        should_use_layout = container.get("layout", False)

        # Get existing asset dir if possible, otherwise import & containerize
        if should_use_layout and (
            existing_asset_dir := get_dir_from_existing_asset(
                 asset_dir, asset_name)
            ):
                asset_dir = existing_asset_dir
        else:
            asset_dir = self.import_and_containerize(
                path, asset_dir, asset_name, container_name
            )

        self.imprint(
            folder_path=folder_path,
            asset_dir=asset_dir,
            container_name=container_name,
            asset_name=asset_name,
            representation=repre_entity,
            product_base_type=product_base_type,
            project_name=context["project"]["name"],
            layout=should_use_layout)

        asset_content = unreal.EditorAssetLibrary.list_assets(
            asset_dir, recursive=True, include_folder=False
        )

        for a in asset_content:
            unreal.EditorAssetLibrary.save_asset(a)

    def remove(self, container):
        path = container["namespace"]
        if unreal.EditorAssetLibrary.does_directory_exist(path):
            unreal.EditorAssetLibrary.delete_directory(path)
