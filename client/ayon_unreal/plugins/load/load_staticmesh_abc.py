# -*- coding: utf-8 -*-
"""Loader for Static Mesh alembics."""
import os

from ayon_core.pipeline import AYON_CONTAINER_ID
from ayon_unreal.api import plugin
from ayon_unreal.api.pipeline import (
    create_container,
    imprint,
    has_asset_directory_pattern_matched,
    format_asset_directory,
    get_target_content_plugin_path,
    UNREAL_VERSION
)
from ayon_core.settings import get_current_project_settings
from ayon_core.lib import EnumDef, BoolDef
import unreal  # noqa


class StaticMeshAlembicLoader(plugin.Loader):
    """Load Unreal StaticMesh from Alembic"""

    product_types = {"model", "staticMesh"}
    label = "Import Alembic Static Mesh"
    representations = {"abc"}
    icon = "cube"
    color = "orange"

    abc_conversion_preset = "maya"
    loaded_asset_dir = "{folder[path]}/{product[name]}_{version[version]}"
    show_dialog = False


    @classmethod
    def apply_settings(cls, project_settings):
        super(StaticMeshAlembicLoader, cls).apply_settings(project_settings)
        # Apply import settings
        unreal_settings = project_settings["unreal"]["import_settings"]
        cls.abc_conversion_preset = unreal_settings["abc_conversion_preset"]
        cls.loaded_asset_dir = unreal_settings["loaded_asset_dir"]
        cls.show_dialog = unreal_settings["show_dialog"]

    @classmethod
    def get_options(cls, contexts):
        return [
            EnumDef(
                "abc_conversion_preset",
                label="Alembic Conversion Preset",
                items={
                    "3dsmax": "3dsmax",
                    "maya": "maya",
                    "custom": "custom"
                },
                default=cls.abc_conversion_preset
            ),
            EnumDef(
                "abc_material_settings",
                label="Alembic Material Settings",
                items={
                    "no_material": "Do not apply materials",
                    "create_materials": "Create matarials by face sets",
                    "find_materials": "Search matching materials by face sets",
                },
                default="no_materials"
            ),
            BoolDef(
                "merge_meshes",
                label="Merge Meshes",
                default=True
            )
        ]

    @staticmethod
    def get_task(filename, asset_dir, asset_name, replace, loaded_options):
        task = unreal.AssetImportTask()
        options = unreal.AbcImportSettings()
        sm_settings = unreal.AbcStaticMeshSettings()
        mat_settings = unreal.AbcMaterialSettings()
        conversion_settings = unreal.AbcConversionSettings()

        task.set_editor_property('filename', filename)
        task.set_editor_property('destination_path', asset_dir)
        task.set_editor_property('destination_name', asset_name)
        task.set_editor_property('replace_existing', replace)
        task.set_editor_property(
            'automated', not loaded_options.get("show_dialog"))
        task.set_editor_property('save', True)

        # set import options here
        # Unreal 4.24 ignores the settings. It works with Unreal 4.26
        options.set_editor_property(
            'import_type', unreal.AlembicImportType.STATIC_MESH)

        sm_settings.set_editor_property(
            'merge_meshes', loaded_options.get("merge_meshes", True))

        if loaded_options.get("abc_material_settings") == "create_materials":
            mat_settings.set_editor_property("create_materials", True)
            mat_settings.set_editor_property("find_materials", False)
        elif loaded_options.get("abc_material_settings") == "find_materials":
            mat_settings.set_editor_property("create_materials", False)
            mat_settings.set_editor_property("find_materials", True)
        else:
            mat_settings.set_editor_property("create_materials", False)
            mat_settings.set_editor_property("find_materials", False)


        if not loaded_options.get("default_conversion"):
            conversion_settings = None
            abc_conversion_preset = loaded_options.get("abc_conversion_preset")
            if abc_conversion_preset == "maya":
                if UNREAL_VERSION.major >= 5 and UNREAL_VERSION.minor >= 4:
                    conversion_settings = unreal.AbcConversionSettings(
                        preset=unreal.AbcConversionPreset.MAYA)
                else:
                    conversion_settings = unreal.AbcConversionSettings(
                        preset=unreal.AbcConversionPreset.CUSTOM,
                        flip_u=False, flip_v=True,
                        rotation=[90.0, 0.0, 0.0],
                        scale=[1.0, -1.0, 1.0])
            elif abc_conversion_preset == "3dsmax":
                if UNREAL_VERSION.major >= 5:
                    conversion_settings = unreal.AbcConversionSettings(
                        preset=unreal.AbcConversionPreset.MAX)
                else:
                    conversion_settings = unreal.AbcConversionSettings(
                        preset=unreal.AbcConversionPreset.CUSTOM,
                        flip_u=False, flip_v=True,
                        rotation=[0.0, 0.0, 0.0],
                        scale=[1.0, -1.0, 1.0])
            else:
                data = get_current_project_settings()
                preset = (
                    data["unreal"]["import_settings"]["custom"]
                )
                conversion_settings = unreal.AbcConversionSettings(
                    preset=unreal.AbcConversionPreset.CUSTOM,
                    flip_u=preset["flip_u"],
                    flip_v=preset["flip_v"],
                    rotation=[
                        preset["rot_x"],
                        preset["rot_y"],
                        preset["rot_z"]
                    ],
                    scale=[
                        preset["scl_x"],
                        preset["scl_y"],
                        preset["scl_z"]
                    ]
                )
            options.conversion_settings = conversion_settings

        options.static_mesh_settings = sm_settings
        options.material_settings = mat_settings
        task.options = options

        return task

    def import_and_containerize(
        self, filepath, asset_dir, asset_name, container_name,
        loaded_options, asset_path=None
    ):
        task = None
        if asset_path:
            loaded_asset_dir = unreal.Paths.split(asset_path)[0]
            task = self.get_task(
                filepath, loaded_asset_dir, asset_name, True, loaded_options)
        else:
            if not unreal.EditorAssetLibrary.does_asset_exist(
                f"{asset_dir}/{asset_name}"):
                    task = self.get_task(
                        filepath, asset_dir, asset_name, False, loaded_options)

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
        project_name
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
        folder_path = context["folder"]["path"]

        suffix = "_CON"
        path = self.filepath_from_context(context)
        ext = os.path.splitext(path)[-1].lstrip(".")
        asset_root, asset_name = format_asset_directory(context, self.loaded_asset_dir)
        loaded_options = {
            "default_conversion": options.get("default_conversion", False),
            "abc_conversion_preset": options.get(
                "abc_conversion_preset", self.abc_conversion_preset),
            "abc_material_settings": options.get("abc_material_settings", "no_material"),
            "merge_meshes": options.get("merge_meshes", True),
            "show_dialog": options.get("show_dialog", self.show_dialog),
        }

        tools = unreal.AssetToolsHelpers().get_asset_tools()
        asset_dir, container_name = tools.create_unique_asset_name(
            asset_root, suffix=f"_{ext}")

        asset_path = has_asset_directory_pattern_matched(
            asset_name, asset_dir, name, extension=ext)

        content_plugin_path = get_target_content_plugin_path(name, ext, container_name)
        if content_plugin_path:
            asset_dir = content_plugin_path

        container_name += suffix
        if not unreal.EditorAssetLibrary.does_directory_exist(asset_dir):
            unreal.EditorAssetLibrary.make_directory(asset_dir)

        self.import_and_containerize(path, asset_dir, asset_name,
                                     container_name, loaded_options,
                                     asset_path=asset_path)

        product_type = context["product"]["productType"]
        self.imprint(
            folder_path,
            asset_dir,
            container_name,
            asset_name,
            context["representation"],
            product_type,
            context["project"]["name"]
        )
        if asset_path:
            unreal.EditorAssetLibrary.rename_asset(
                f"{asset_path}",
                f"{asset_dir}/{asset_name}.{asset_name}"
            )
        asset_content = unreal.EditorAssetLibrary.list_assets(
            asset_dir, recursive=True, include_folder=False
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
        asset_root, asset_name = format_asset_directory(context, self.loaded_asset_dir)
        tools = unreal.AssetToolsHelpers().get_asset_tools()
        asset_dir, container_name = tools.create_unique_asset_name(
            asset_root, suffix=f"_{ext}")

        asset_path = has_asset_directory_pattern_matched(
            asset_name, asset_dir, name, extension=ext)

        content_plugin_path = get_target_content_plugin_path(name, ext, container_name)
        if content_plugin_path:
            asset_dir = content_plugin_path

        container_name += suffix
        if not unreal.EditorAssetLibrary.does_directory_exist(asset_dir):
            unreal.EditorAssetLibrary.make_directory(asset_dir)
        loaded_options = {
            "default_conversion": False,
            "abc_conversion_preset": self.abc_conversion_preset
        }
        self.import_and_containerize(path, asset_dir, asset_name,
                                     container_name, loaded_options,
                                     asset_path=asset_path)
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
