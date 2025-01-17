# -*- coding: utf-8 -*-
"""Load Skeletal Meshes form FBX."""
import os

from ayon_core.pipeline import AYON_CONTAINER_ID
from ayon_core.lib import BoolDef, EnumDef
from ayon_unreal.api import plugin
from ayon_unreal.api.pipeline import (
    create_container,
    imprint,
    has_asset_directory_pattern_matched,
    format_asset_directory,
    remove_asset_from_content_plugin
)
import unreal  # noqa


class SkeletalMeshFBXLoader(plugin.Loader):
    """Load Unreal SkeletalMesh from FBX."""

    product_types = {"rig", "skeletalMesh"}
    label = "Import FBX Skeletal Mesh"
    representations = {"fbx"}
    icon = "cube"
    color = "orange"

    loaded_asset_dir = "{folder[path]}/{product[name]}_{version[version]}"
    show_dialog = False
    content_plugin_enabled = False
    content_plugin_path = []

    @classmethod
    def apply_settings(cls, project_settings):
        unreal_settings = project_settings["unreal"]["import_settings"]
        super(SkeletalMeshFBXLoader, cls).apply_settings(project_settings)
        cls.loaded_asset_dir = unreal_settings["loaded_asset_dir"]
        cls.show_dialog = unreal_settings["show_dialog"]
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
        self, filepath, asset_dir, asset_name, container_name,
        asset_path=None
    ):
        task = None
        if asset_path:
            loaded_asset_dir = unreal.Paths.split(asset_path)[0]
            task = self.get_task(filepath, loaded_asset_dir, asset_name, False)
        else:
            if not unreal.EditorAssetLibrary.does_asset_exist(
                f"{asset_dir}/{asset_name}"):
                    task = self.get_task(filepath, asset_dir, asset_name, False)

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
        representation,
        product_type,
        project_name,
        content_plugin_name=None,
        content_plugin_enabled=False
    ):
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
            "product_type": product_type,
            # TODO these should be probably removed
            "asset": folder_path,
            "family": product_type,
            "project_name": project_name
        }
        if content_plugin_enabled and content_plugin_name:
            data["content_plugin_name"] = content_plugin_name
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
            data (dict): Those would be data to be imprinted.

        Returns:
            list(str): list of container content
        """
        # Create directory for asset and Ayon container
        folder_name = context["folder"]["name"]
        product_type = context["product"]["productType"]
        suffix = "_CON"
        path = self.filepath_from_context(context)
        ext = os.path.splitext(path)[-1].lstrip(".")
        use_content_plugin = options.get("content_plugin_enabled", False)
        content_plugin_name = options.get(
            "content_plugin_name",
            next((path for path in self.content_plugin_path), "")
        )
        asset_root, asset_name = format_asset_directory(
            context, self.loaded_asset_dir,
            use_content_plugin, content_plugin_name
        )

        tools = unreal.AssetToolsHelpers().get_asset_tools()
        asset_dir, container_name = tools.create_unique_asset_name(
            asset_root, suffix=f"_{ext}")

        asset_path = has_asset_directory_pattern_matched(
            asset_name, asset_dir, name, extension=ext,
            use_content_plugin=use_content_plugin,
            content_plugin_name=content_plugin_name
        )

        container_name += suffix
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
            folder_name,
            asset_dir,
            container_name,
            asset_name,
            context["representation"],
            product_type,
            context["project"]["name"],
            content_plugin_name,
            use_content_plugin
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
        name = context["product"]["name"]

        # Create directory for asset and Ayon container
        suffix = "_CON"
        path = self.filepath_from_context(context)
        ext = os.path.splitext(path)[-1].lstrip(".")
        content_plugin_name = container.get("content_plugin_name", "")

        asset_root, asset_name = format_asset_directory(
            context, self.loaded_asset_dir,
            use_content_plugin=bool(content_plugin_name),
            content_plugin_name=content_plugin_name
        )
        tools = unreal.AssetToolsHelpers().get_asset_tools()
        asset_dir, container_name = tools.create_unique_asset_name(
            asset_root, suffix=f"_{ext}")

        asset_path = has_asset_directory_pattern_matched(
            asset_name, asset_dir, name, extension=ext,
            use_content_plugin=bool(content_plugin_name),
            content_plugin_name=content_plugin_name
        )

        container_name += suffix
        if not unreal.EditorAssetLibrary.does_directory_exist(asset_dir):
            unreal.EditorAssetLibrary.make_directory(asset_dir)
        self.import_and_containerize(
            path, asset_dir, asset_name, container_name, asset_path=asset_path)
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

    def remove(self, container):
        path = container["namespace"]
        if unreal.EditorAssetLibrary.does_directory_exist(path):
            unreal.EditorAssetLibrary.delete_directory(path)
        remove_asset_from_content_plugin(container)
