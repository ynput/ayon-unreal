# -*- coding: utf-8 -*-
"""Loader for published alembics."""
import os

from ayon_core.pipeline import (
    get_representation_path,
    AYON_CONTAINER_ID
)
from ayon_core.lib import EnumDef
from ayon_unreal.api import plugin
from ayon_unreal.api.pipeline import (
    AYON_ASSET_DIR,
    create_container,
    imprint,
)

import unreal  # noqa


class PointCacheAlembicLoader(plugin.Loader):
    """Load Point Cache from Alembic"""

    product_types = {"model", "pointcache"}
    label = "Import Alembic Point Cache"
    representations = {"abc"}
    icon = "cube"
    color = "orange"

    root = AYON_ASSET_DIR
    abc_conversion_preset = "maya"

    @classmethod
    def apply_settings(cls, project_settings):
        super(PointCacheAlembicLoader, cls).apply_settings(project_settings)
        # Apply import settings
        unreal_settings = project_settings.get("unreal", {})
        if unreal_settings.get("abc_conversion_preset", cls.abc_conversion_preset):
            cls.abc_conversion_preset = unreal_settings.get(
                "abc_conversion_preset", cls.abc_conversion_preset)

    @classmethod
    def get_options(cls, contexts):
        return [
            EnumDef(
                "abc_conversion_preset",
                label="Alembic Conversion Preset",
                items={
                    "custom": "custom",
                    "maya": "maya"
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
            conversion_settings = unreal.AbcConversionSettings(
                preset= unreal.AbcConversionPreset.MAYA)
        else:
            conversion_settings = unreal.AbcConversionSettings(
                preset=unreal.AbcConversionPreset.CUSTOM,
                flip_u=False, flip_v=True,
                rotation=[-90.0, 0.0, 180.0],
                scale=[100.0, 100.0, 100.0])

        task.set_editor_property('filename', filename)
        task.set_editor_property('destination_path', asset_dir)
        task.set_editor_property('destination_name', asset_name)
        task.set_editor_property('replace_existing', replace)
        task.set_editor_property('automated', True)
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
        frame_start, frame_end, loaded_options=None
    ):
        unreal.EditorAssetLibrary.make_directory(asset_dir)

        task = self.get_task(
            filepath, asset_dir, asset_name, False, frame_start, frame_end, loaded_options)

        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
        # avoid duplicate container asset data being created
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
        frame_start,
        frame_end,
        product_type,
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
        folder_name = folder_entity["name"]
        folder_attributes = folder_entity["attrib"]

        suffix = "_CON"
        path = self.filepath_from_context(context)
        ext = os.path.splitext(path)[-1].lstrip(".")
        asset_name = f"{folder_name}_{name}_{ext}" if folder_name else f"{name}_{ext}"
        version = context["version"]["version"]
        # Check if version is hero version and use different name
        if version < 0:
            name_version = f"{name}_hero"
        else:
            name_version = f"{name}_v{version:03d}"
        tools = unreal.AssetToolsHelpers().get_asset_tools()
        asset_dir, container_name = tools.create_unique_asset_name(
            f"{self.root}/{folder_name}/{name_version}", suffix=f"_{ext}")

        container_name += suffix

        frame_start = folder_attributes.get("frameStart")
        frame_end = folder_attributes.get("frameEnd")

        # If frame start and end are the same, we increase the end frame by
        # one, otherwise Unreal will not import it
        if frame_start == frame_end:
            frame_end += 1

        if not unreal.EditorAssetLibrary.does_directory_exist(asset_dir):
            path = self.filepath_from_context(context)
            loaded_options = {
                "abc_conversion_preset": options.get(
                    "abc_conversion_preset", self.abc_conversion_preset)
            }
            self.import_and_containerize(
                path, asset_dir, asset_name, container_name,
                frame_start, frame_end, loaded_options)

        self.imprint(
            folder_path,
            asset_dir,
            container_name,
            asset_name,
            context["representation"],
            frame_start,
            frame_end,
            context["product"]["productType"]
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
        folder_name = context["folder"]["name"]
        product_name = context["product"]["name"]
        product_type = context["product"]["productType"]
        version = context["version"]["version"]
        repre_entity = context["representation"]
        asset_dir = container["namespace"]
        unreal.log("asset directory")
        unreal.log(asset_dir)
        suffix = "_CON"
        path = get_representation_path(repre_entity)
        ext = os.path.splitext(path)[-1].lstrip(".")
        asset_name = f"{product_name}_{ext}"
        if folder_name:
            asset_name = f"{folder_name}_{product_name}"

        # Check if version is hero version and use different name
        if version < 0:
            name_version = f"{product_name}_hero"
        else:
            name_version = f"{product_name}_v{version:03d}"
        tools = unreal.AssetToolsHelpers().get_asset_tools()
        asset_dir, container_name = tools.create_unique_asset_name(
            f"{self.root}/{folder_name}/{name_version}", suffix=f"_{ext}")

        container_name += suffix

        frame_start = int(container.get("frame_start"))
        frame_end = int(container.get("frame_end"))

        if not unreal.EditorAssetLibrary.does_directory_exist(asset_dir):
            path = get_representation_path(repre_entity)
            loaded_options = {
                "abc_conversion_preset": self.abc_conversion_preset
            }
            self.import_and_containerize(
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
            product_type
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
