# -*- coding: utf-8 -*-
"""Loader for published alembics."""
import os

from ayon_core.pipeline import AYON_CONTAINER_ID
from ayon_core.lib import EnumDef
from ayon_unreal.api import plugin
from ayon_unreal.api.pipeline import (
    create_container,
    imprint,
    format_asset_directory,
    UNREAL_VERSION,
    get_dir_from_existing_asset
)
from ayon_core.settings import get_current_project_settings

import unreal  # noqa


class PointCacheAlembicLoader(plugin.Loader):
    """Load Point Cache from Alembic"""

    product_types = {"model", "pointcache"}
    label = "Import Alembic Point Cache"
    representations = {"abc"}
    icon = "cube"
    color = "orange"

    abc_conversion_preset = "maya"
    loaded_asset_dir = "{folder[path]}/{product[name]}_{version[version]}"
    show_dialog = False

    @classmethod
    def apply_settings(cls, project_settings):
        super(PointCacheAlembicLoader, cls).apply_settings(project_settings)
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
            )
        ]

    @staticmethod
    def get_task(
        filename, asset_dir, asset_name, replace,
        frame_start=None, frame_end=None, loaded_options=None
    ):
        task = unreal.AssetImportTask()
        options = unreal.AbcImportSettings()
        gc_settings = unreal.AbcGeometryCacheSettings()
        conversion_settings = unreal.AbcConversionSettings()
        sampling_settings = unreal.AbcSamplingSettings()
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

        task.set_editor_property('filename', filename)
        task.set_editor_property('destination_path', asset_dir)
        task.set_editor_property('destination_name', asset_name)
        task.set_editor_property('replace_existing', replace)
        task.set_editor_property(
            'automated', not loaded_options.get("show_dialog"))
        task.set_editor_property('save', True)

        options.set_editor_property(
            'import_type', unreal.AlembicImportType.GEOMETRY_CACHE)
        options.sampling_settings.frame_start = frame_start
        options.sampling_settings.frame_end = frame_end

        gc_settings.set_editor_property('flatten_tracks', False)

        if frame_start is not None:
            sampling_settings.set_editor_property('frame_start', frame_start)
        if frame_end is not None:
            sampling_settings.set_editor_property('frame_end', frame_end)

        options.geometry_cache_settings = gc_settings
        options.conversion_settings = conversion_settings
        options.sampling_settings = sampling_settings
        task.options = options

        return task

    def import_and_containerize(
        self, filepath, asset_dir, asset_name, container_name,
        frame_start, frame_end, loaded_options
    ):
        task = None

        if not unreal.EditorAssetLibrary.does_asset_exist(
            f"{asset_dir}/{asset_name}"):
                task = self.get_task(
                    filepath, asset_dir, asset_name, False,
                    frame_start, frame_end,
                    loaded_options=loaded_options
                )

        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
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
        frame_start,
        frame_end,
        product_type,
        project_name,
        layout
    ):
        data = {
            "schema": "ayon:container-2.0",
            "id": AYON_CONTAINER_ID,
            "namespace": asset_dir,
            "container_name": container_name,
            "asset_name": asset_name,
            "loader": str(self.__class__.__name__),
            "representation": representation["id"],
            "parent": representation["versionId"],
            "frame_start": frame_start,
            "frame_end": frame_end,
            "product_type": product_type,
            "folder_path": folder_path,
            # TODO these should be probably removed
            "family": product_type,
            "asset": folder_path,
            "project_name": project_name,
            "layout": layout
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
        folder_entity = context["folder"]
        folder_path = folder_entity["path"]
        folder_attributes = folder_entity["attrib"]

        suffix = "_CON"
        path = self.filepath_from_context(context)
        ext = os.path.splitext(path)[-1].lstrip(".")
        asset_root, asset_name = format_asset_directory(
            context, self.loaded_asset_dir
        )

        tools = unreal.AssetToolsHelpers().get_asset_tools()
        asset_dir, container_name = tools.create_unique_asset_name(
            asset_root, suffix=f"_{ext}")

        frame_start = folder_attributes.get("frameStart")
        frame_end = folder_attributes.get("frameEnd")

        # If frame start and end are the same, we increase the end frame by
        # one, otherwise Unreal will not import it
        if frame_start == frame_end:
            frame_end += 1

        container_name += suffix
        should_use_layout = options.get("layout", False)

        # Get existing asset dir if possible, otherwise import & containerize
        if should_use_layout and (
            existing_asset_dir := get_dir_from_existing_asset(
                 asset_dir, asset_name)
            ):
                asset_dir = existing_asset_dir
        else:
            loaded_options = {
                "abc_conversion_preset": options.get(
                    "abc_conversion_preset", self.abc_conversion_preset),
                "show_dialog": options.get("show_dialog", self.show_dialog),
            }
            asset_dir = self.import_and_containerize(
                path, asset_dir, asset_name, container_name,
                frame_start, frame_end, loaded_options
            )

        self.imprint(
            folder_path,
            asset_dir,
            container_name,
            asset_name,
            context["representation"],
            frame_start,
            frame_end,
            context["product"]["productType"],
            context["project"]["name"],
            should_use_layout
        )
        asset_content = unreal.EditorAssetLibrary.list_assets(
            asset_dir, recursive=True, include_folder=True
        )

        for a in asset_content:
            unreal.EditorAssetLibrary.save_asset(a)

        return asset_content

    def update(self, container, context):
        # Create directory for folder and Ayon container
        folder_path = context["folder"]["path"]
        product_type = context["product"]["productType"]
        repre_entity = context["representation"]
        asset_dir = container["namespace"]
        suffix = "_CON"
        path = self.filepath_from_context(context)
        ext = os.path.splitext(path)[-1].lstrip(".")

        asset_root, asset_name = format_asset_directory(
            context, self.loaded_asset_dir
        )
        tools = unreal.AssetToolsHelpers().get_asset_tools()
        asset_dir, container_name = tools.create_unique_asset_name(
            asset_root, suffix=f"_{ext}")

        frame_start = int(container.get("frame_start"))
        frame_end = int(container.get("frame_end"))

        container_name += suffix
        should_use_layout = container.get("layout", False)

        # Get existing asset dir if possible, otherwise import & containerize
        if should_use_layout and (
            existing_asset_dir := get_dir_from_existing_asset(
                 asset_dir, asset_name)
            ):
                asset_dir = existing_asset_dir
        else:
            loaded_options = {
                "abc_conversion_preset": self.abc_conversion_preset,
                "show_dialog": self.show_dialog,
            }
            asset_dir = self.import_and_containerize(
                path, asset_dir, asset_name, container_name,
                frame_start, frame_end, loaded_options)

        self.imprint(
            folder_path,
            asset_dir,
            container_name,
            asset_name,
            repre_entity,
            frame_start,
            frame_end,
            product_type,
            context["project"]["name"],
            should_use_layout
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
