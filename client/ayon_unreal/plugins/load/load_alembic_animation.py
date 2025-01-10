# -*- coding: utf-8 -*-
"""Load Alembic Animation."""
import os

from ayon_core.lib import EnumDef
from ayon_core.pipeline import AYON_CONTAINER_ID
from ayon_unreal.api import plugin
from ayon_unreal.api import pipeline as unreal_pipeline
from ayon_core.settings import get_current_project_settings
import unreal  # noqa



class AnimationAlembicLoader(plugin.Loader):
    """Load Unreal SkeletalMesh from Alembic"""

    product_types = {"animation"}
    label = "Import Alembic Animation"
    representations = {"abc"}
    icon = "cube"
    color = "orange"
    abc_conversion_preset = "maya"
    # check frame padding
    loaded_asset_dir = "{folder[path]}/{product[name]}_{version[version]}"
    show_dialog = False
    content_plugin_enabled = False
    content_plugin_path = []

    @classmethod
    def apply_settings(cls, project_settings):
        super(AnimationAlembicLoader, cls).apply_settings(project_settings)
        # Apply import settings
        unreal_settings = project_settings["unreal"]["import_settings"]
        cls.abc_conversion_preset = unreal_settings["abc_conversion_preset"]
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
        content_plugin_defs = []
        plugin_path = cls.content_plugin_path
        if cls.content_plugin_enabled:
            content_plugin_defs = [
                EnumDef(
                    "content_plugin_name",
                    label="Content Plugin Name",
                    items=[path for path in plugin_path],
                    default=plugin_path[0]
                )
            ]
        return content_plugin_defs + [
            EnumDef(
                "abc_conversion_preset",
                label="Alembic Conversion Preset",
                items={
                    "3dsmax": "3dsmax",
                    "maya": "maya",
                    "custom": "custom"
                },
                default=cls.abc_conversion_preset
            )
        ]

    def get_task(self, filename, asset_dir, asset_name, replace, loaded_options=None):
        task = unreal.AssetImportTask()
        options = unreal.AbcImportSettings()
        sm_settings = unreal.AbcStaticMeshSettings()
        conversion_settings = unreal.AbcConversionSettings()
        abc_conversion_preset = loaded_options.get("abc_conversion_preset")
        if abc_conversion_preset == "maya":
            if unreal_pipeline.UNREAL_VERSION.major >= 5 and (
                unreal_pipeline.UNREAL_VERSION.minor >= 4):
                    conversion_settings = unreal.AbcConversionSettings(
                        preset= unreal.AbcConversionPreset.MAYA)
            else:
                conversion_settings = unreal.AbcConversionSettings(
                    preset=unreal.AbcConversionPreset.CUSTOM,
                    flip_u=False, flip_v=True,
                    rotation=[90.0, 0.0, 0.0],
                    scale=[1.0, -1.0, 1.0])
        elif abc_conversion_preset == "3dsmax":
            if unreal_pipeline.UNREAL_VERSION.major >= 5:
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

        options.sampling_settings.frame_start = loaded_options.get("frameStart")
        options.sampling_settings.frame_end = loaded_options.get("frameEnd")
        task.set_editor_property('filename', filename)
        task.set_editor_property('destination_path', asset_dir)
        task.set_editor_property('destination_name', asset_name)
        task.set_editor_property('replace_existing', replace)
        task.set_editor_property('automated', not self.show_dialog)
        task.set_editor_property('save', True)

        options.set_editor_property(
            'import_type', unreal.AlembicImportType.SKELETAL)

        options.static_mesh_settings = sm_settings
        options.conversion_settings = conversion_settings
        task.options = options

        return task

    def import_and_containerize(
        self, filepath, asset_dir, asset_name, container_name, loaded_options=None,
        asset_path=None
    ):
        task = None
        if asset_path:
            loaded_asset_dir = os.path.dirname(asset_path)
            task = self.get_task(filepath, loaded_asset_dir, asset_name, True, loaded_options)
        else:
            if not unreal.EditorAssetLibrary.does_asset_exist(
                f"{asset_dir}/{asset_name}"):
                    task = self.get_task(
                        filepath, asset_dir, asset_name, False, loaded_options
                    )

        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

        # avoid duplicate container asset data being created
        if not unreal.EditorAssetLibrary.does_asset_exist(
            f"{asset_dir}/{container_name}"):
            # Create Asset Container
            unreal_pipeline.create_container(
                container=container_name, path=asset_dir)


    def imprint(
        self,
        folder_path,
        asset_dir,
        container_name,
        asset_name,
        frameStart,
        frameEnd,
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
            "frameStart": frameStart,
            "frameEnd": frameEnd,
            # TODO these should be probably removed
            "asset": folder_path,
            "family": product_type,
            "project_name": project_name
        }
        unreal_pipeline.imprint(f"{asset_dir}/{container_name}", data)

    def load(self, context, name, namespace, options):
        """Load and containerise representation into Content Browser.

        This is two-step process. First, import FBX to temporary path and
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

        # Create directory for asset and ayon container
        folder_entity = context["folder"]
        folder_path = context["folder"]["path"]
        hierarchy = folder_path.lstrip("/").split("/")
        folder_name = hierarchy.pop(-1)
        product_type = context["product"]["productType"]
        suffix = "_CON"
        path = self.filepath_from_context(context)
        ext = os.path.splitext(path)[-1].lstrip(".")
        content_plugin_name = options.get("content_plugin_name", "")
        asset_root, asset_name = unreal_pipeline.format_asset_directory(
            context, self.loaded_asset_dir, content_plugin_name)

        tools = unreal.AssetToolsHelpers().get_asset_tools()
        asset_dir, container_name = tools.create_unique_asset_name(
            asset_root, suffix=f"_{ext}")

        asset_path = unreal_pipeline.has_asset_directory_pattern_matched(
            asset_name, asset_dir, folder_name, extension=ext)

        container_name += suffix
        if not unreal.EditorAssetLibrary.does_directory_exist(asset_dir):
            unreal.EditorAssetLibrary.make_directory(asset_dir)

        loaded_options = {
            "abc_conversion_preset": options.get(
                "abc_conversion_preset", self.abc_conversion_preset),
            "frameStart": folder_entity["attrib"]["frameStart"],
            "frameEnd": folder_entity["attrib"]["frameEnd"]
        }

        path = self.filepath_from_context(context)
        self.import_and_containerize(
            path, asset_dir, asset_name,
            container_name, loaded_options,
            asset_path=asset_path
        )

        if asset_path:
            unreal.EditorAssetLibrary.rename_asset(
                f"{asset_path}",
                f"{asset_dir}/{asset_name}.{asset_name}"
            )

        # update metadata
        self.imprint(
            folder_path,
            asset_dir,
            container_name,
            asset_name,
            folder_entity["attrib"]["frameStart"],
            folder_entity["attrib"]["frameEnd"],
            context["representation"],
            product_type,
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
        hierarchy = folder_path.lstrip("/").split("/")
        folder_name = hierarchy.pop(-1)
        product_type = context["product"]["productType"]
        repre_entity = context["representation"]

        # Create directory for folder and Ayon container
        suffix = "_CON"
        source_path = self.filepath_from_context(context)

        ext = os.path.splitext(source_path)[-1].lstrip(".")
        asset_root, asset_name = unreal_pipeline.format_asset_directory(context, self.loaded_asset_dir)
        # do import fbx and replace existing data
        asset_tools = unreal.AssetToolsHelpers.get_asset_tools()
        asset_dir, container_name = asset_tools.create_unique_asset_name(
             asset_root, suffix=f"_{ext}")
        asset_path = unreal_pipeline.has_asset_directory_pattern_matched(
            asset_name, asset_dir, folder_name, extension=ext)

        content_plugin_path = unreal_pipeline.get_target_content_plugin_path(folder_name, ext, container_name)
        if content_plugin_path:
            asset_dir = content_plugin_path

        container_name += suffix

        if not unreal.EditorAssetLibrary.does_directory_exist(asset_dir):
            unreal.EditorAssetLibrary.make_directory(asset_dir)
        loaded_options = {
            "abc_conversion_preset": self.abc_conversion_preset,
            "frameStart": int(container.get("frameStart", "1")),
            "frameEnd": int(container.get("frameEnd", "1"))
        }

        self.import_and_containerize(
            source_path, asset_dir, asset_name,
            container_name, loaded_options,
            asset_path=asset_path
        )
        if asset_path:
            unreal.EditorAssetLibrary.rename_asset(
                f"{asset_path}",
                f"{asset_dir}/{asset_name}.{asset_name}"
            )

        # update metadata
        self.imprint(
            folder_path,
            asset_dir,
            container_name,
            asset_name,
            container.get("frameStart", "1"),
            container.get("frameEnd", "1"),
            repre_entity,
            product_type,
            context["project"]["name"]
        )
        asset_content = unreal.EditorAssetLibrary.list_assets(
            asset_dir, recursive=True, include_folder=True
        )

        for a in asset_content:
            unreal.EditorAssetLibrary.save_asset(a)

        unreal_pipeline.add_assets_to_content_plugin(
            asset_name, ext, asset_content)

    def remove(self, container):
        path = container["namespace"]
        if unreal.EditorAssetLibrary.does_directory_exist(path):
            unreal.EditorAssetLibrary.delete_directory(path)
