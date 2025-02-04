# -*- coding: utf-8 -*-
"""Load Skeletal Mesh alembics."""
import os

from ayon_core.pipeline import AYON_CONTAINER_ID

from ayon_core.lib import EnumDef
from ayon_unreal.api import plugin
from ayon_unreal.api.pipeline import (
    create_container,
    imprint,
    format_asset_directory,
    UNREAL_VERSION,
    find_existing_asset
)
from ayon_core.settings import get_current_project_settings
import unreal  # noqa


class SkeletalMeshAlembicLoader(plugin.Loader):
    """Load Unreal SkeletalMesh from Alembic"""

    product_types = {"pointcache", "skeletalMesh"}
    label = "Import Alembic Skeletal Mesh"
    representations = {"abc"}
    icon = "cube"
    color = "orange"

    abc_conversion_preset = "maya"
    loaded_asset_dir = "{folder[path]}/{product[name]}_{version[version]}"
    show_dialog = False
    asset_loading_location = "project"

    @classmethod
    def apply_settings(cls, project_settings):
        super(SkeletalMeshAlembicLoader, cls).apply_settings(project_settings)
        # Apply import settings
        unreal_settings = project_settings["unreal"]["import_settings"]
        cls.abc_conversion_preset = unreal_settings["abc_conversion_preset"]
        cls.loaded_asset_dir = unreal_settings["loaded_asset_dir"]
        cls.show_dialog = unreal_settings["show_dialog"]
        cls.asset_loading_location = unreal_settings.get(
            "asset_loading_location", cls.asset_loading_location)

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
                default="Do not apply materials"
            )
        ]

    @staticmethod
    def get_task(filename, asset_dir, asset_name, replace, loaded_options):
        task = unreal.AssetImportTask()
        options = unreal.AbcImportSettings()
        mat_settings = unreal.AbcMaterialSettings()
        conversion_settings = unreal.AbcConversionSettings()

        task.set_editor_property('filename', filename)
        task.set_editor_property('destination_path', asset_dir)
        task.set_editor_property('destination_name', asset_name)
        task.set_editor_property('replace_existing', replace)
        task.set_editor_property(
            'automated', not loaded_options.get("show_dialog"))
        task.set_editor_property('save', True)

        options.set_editor_property(
            'import_type', unreal.AlembicImportType.SKELETAL)
        options.sampling_settings.frame_start = loaded_options.get("frameStart")
        options.sampling_settings.frame_end = loaded_options.get("frameEnd")

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

            options.material_settings = mat_settings

        task.options = options

        return task

    def import_and_containerize(
        self, filepath, asset_dir, asset_name, container_name,
        loaded_options, pattern_regex
    ):
        task = None
        # Determine where to load the asset based on settings
        if self.asset_loading_location == "follow_existing":
            # Follow the existing version's location
            show_dialog = (
                True
                if loaded_options.get(
                    "resolution_priority", "project_first") == "content_plugin_first"
                else False
            )
            existing_asset_path = find_existing_asset(
                asset_name, asset_dir, pattern_regex, show_dialog=show_dialog)
            if existing_asset_path:
                version_folder = unreal.Paths.split(asset_dir)[1]
                asset_dir = unreal.Paths.get_path(existing_asset_path)
                asset_dir = f"{existing_asset_path}/{version_folder}"
        if not unreal.EditorAssetLibrary.does_directory_exist(asset_dir):
            unreal.EditorAssetLibrary.make_directory(asset_dir)
        # Check if the asset already exists
        existing_asset_path = find_existing_asset(asset_name)
        if existing_asset_path:
            # If the asset exists, reuse it
            task = self.get_task(
                filepath, existing_asset_path, asset_name, True, loaded_options
            )
        else:
            if not unreal.EditorAssetLibrary.does_asset_exist(
                f"{asset_dir}/{asset_name}"):
                    task = self.get_task(
                        filepath, asset_dir, asset_name, False, loaded_options)

        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        if existing_asset_path:
            if not unreal.EditorAssetLibrary.does_directory_exist(
                existing_asset_path):
                    unreal.EditorAssetLibrary.rename_asset(
                        f"{existing_asset_path}/{asset_name}.{asset_name}",
                        f"{asset_dir}/{asset_name}.{asset_name}"
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
        representation,
        product_type,
        frameStart,
        frameEnd,
        project_name,
        resolution_priority="project_first"
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
            "frameStart":frameStart,
            "frameEnd": frameEnd,
            # TODO these should be probably removed
            "asset": folder_path,
            "family": product_type,
            "project_name": project_name,
            "resolution_priority": resolution_priority
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
        # Create directory for asset and ayon container
        folder_entity = context["folder"]
        folder_path = folder_entity["path"]
        suffix = "_CON"
        path = self.filepath_from_context(context)
        ext = os.path.splitext(path)[-1].lstrip(".")
        asset_root, asset_name = format_asset_directory(
            context, self.loaded_asset_dir
        )
        resolution_priority = options.get("resolution_priority", "project_first")
        loaded_options = {
            "default_conversion": options.get("default_conversion", False),
            "abc_conversion_preset": options.get(
                "abc_conversion_preset", self.abc_conversion_preset),
            "abc_material_settings": options.get("abc_material_settings", "no_material"),
            "frameStart": folder_entity["attrib"]["frameStart"],
            "frameEnd": folder_entity["attrib"]["frameEnd"],
            "resolution_priority": resolution_priority
        }

        pattern_regex = {
            "name": name,
            "extension": ext
        }
        tools = unreal.AssetToolsHelpers().get_asset_tools()
        asset_dir, container_name = tools.create_unique_asset_name(
            asset_root, suffix=f"_{ext}")
        container_name += suffix
        asset_dir = self.import_and_containerize(
            path, asset_dir, asset_name,
            container_name, loaded_options,
            pattern_regex
        )

        self.imprint(
            folder_path,
            asset_dir,
            container_name,
            asset_name,
            context["representation"],
            context["product"]["productType"],
            folder_entity["attrib"]["frameStart"],
            folder_entity["attrib"]["frameEnd"],
            context["project"]["name"],
            resolution_priority
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

        # Create directory for folder and Ayon container
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
        loaded_options = {
            "default_conversion": False,
            "abc_conversion_preset": self.abc_conversion_preset,
            "frameStart": container.get("frameStart", 1),
            "frameEnd": container.get("frameEnd", 1),
            "resolution_priority": container.get(
                "resolution_priority", "project_first")
        }
        pattern_regex = {
            "name": context["product"]["name"],
            "extension": ext
        }
        asset_dir = self.import_and_containerize(
            path, asset_dir, asset_name,
            container_name, loaded_options,
            pattern_regex
        )

        self.imprint(
            folder_path,
            asset_dir,
            container_name,
            asset_name,
            repre_entity,
            product_type,
            container.get("frameStart", 1),
            container.get("frameEnd", 1),
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
