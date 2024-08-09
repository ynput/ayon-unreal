# -*- coding: utf-8 -*-
"""Load Skeletal Mesh alembics."""
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


class SkeletalMeshAlembicLoader(plugin.Loader):
    """Load Unreal SkeletalMesh from Alembic"""

    product_types = {"pointcache", "skeletalMesh"}
    label = "Import Alembic Skeletal Mesh"
    representations = {"abc"}
    icon = "cube"
    color = "orange"

    root = AYON_ASSET_DIR
    
    show_dialog = False

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
                default="maya"
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
    

    @classmethod  
    def apply_settings(cls, project_settings):  
        super(SkeletalMeshAlembicLoader, cls).apply_settings(project_settings)  
        
        # Apply import settings  
        import_settings = (  
            project_settings.get("unreal", {}).get("import_settings", {})  
        )  

        cls.show_dialog = import_settings.get("show_dialog", 
                                                cls.show_dialog)   


    @staticmethod
    def get_task(cls, filename, asset_dir, asset_name, replace, loaded_options):
        task = unreal.AssetImportTask()
        options = unreal.AbcImportSettings()
        mat_settings = unreal.AbcMaterialSettings()
        conversion_settings = unreal.AbcConversionSettings(
            preset=unreal.AbcConversionPreset.CUSTOM,
            flip_u=False, flip_v=False,
            rotation=[0.0, 0.0, 0.0],
            scale=[1.0, 1.0, 1.0])

        task.set_editor_property('filename', filename)
        task.set_editor_property('destination_path', asset_dir)
        task.set_editor_property('destination_name', asset_name)
        task.set_editor_property('replace_existing', replace)
        task.set_editor_property('automated', not cls.show_dialog)
        task.set_editor_property('save', True)

        options.set_editor_property(
            'import_type', unreal.AlembicImportType.SKELETAL)

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
                conversion_settings = unreal.AbcConversionSettings(
                    preset= unreal.AbcConversionPreset.MAYA)
            else:
                conversion_settings = unreal.AbcConversionSettings(
                    preset=unreal.AbcConversionPreset.CUSTOM,
                    flip_u=False, flip_v=False,
                    rotation=[0.0, 0.0, 0.0],
                    scale=[1.0, 1.0, 1.0])
            options.conversion_settings = conversion_settings

            options.material_settings = mat_settings

        task.options = options

        return task

    def import_and_containerize(
        self, filepath, asset_dir, asset_name, container_name,
        loaded_options
    ):
        unreal.EditorAssetLibrary.make_directory(asset_dir)

        task = self.get_task(
            filepath, asset_dir, asset_name, False, loaded_options)

        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

        # Create Asset Container
        create_container(container=container_name, path=asset_dir)

    def imprint(
        self,
        folder_path,
        asset_dir,
        container_name,
        asset_name,
        representation,
        product_type
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
        folder_path = context["folder"]["path"]
        folder_name = context["folder"]["name"]
        suffix = "_CON"
        asset_name = f"{folder_name}_{name}" if folder_name else f"{name}"
        version = context["version"]["version"]
        # Check if version is hero version and use different name
        if version < 0:
            name_version = f"{name}_hero"
        else:
            name_version = f"{name}_v{version:03d}"

        loaded_options = {
            "default_conversion": options.get("default_conversion", False),
            "abc_conversion_preset": options.get("abc_conversion_preset", "maya"),
            "abc_material_settings": options.get("abc_material_settings", "no_material")
        }

        tools = unreal.AssetToolsHelpers().get_asset_tools()
        asset_dir, container_name = tools.create_unique_asset_name(
            f"{self.root}/{folder_name}/{name_version}", suffix="")

        container_name += suffix

        if not unreal.EditorAssetLibrary.does_directory_exist(asset_dir):
            path = self.filepath_from_context(context)

            self.import_and_containerize(path, asset_dir, asset_name,
                                         container_name, loaded_options)

        product_type = context["product"]["productType"]
        self.imprint(
            folder_path,
            asset_dir,
            container_name,
            asset_name,
            context["representation"],
            product_type
        )

        asset_content = unreal.EditorAssetLibrary.list_assets(
            asset_dir, recursive=True, include_folder=True
        )

        for a in asset_content:
            unreal.EditorAssetLibrary.save_asset(a)

        return asset_content

    def update(self, container, context):
        folder_path = context["folder"]["path"]
        folder_name = context["folder"]["name"]
        product_name = context["product"]["name"]
        product_type = context["product"]["productType"]
        version = context["version"]["version"]
        repre_entity = context["representation"]

        # Create directory for folder and Ayon container
        suffix = "_CON"
        asset_name = product_name
        if folder_name:
            asset_name = f"{folder_name}_{product_name}"
        # Check if version is hero version and use different name
        if version < 0:
            name_version = f"{product_name}_hero"
        else:
            name_version = f"{product_name}_v{version:03d}"
        tools = unreal.AssetToolsHelpers().get_asset_tools()
        asset_dir, container_name = tools.create_unique_asset_name(
            f"{self.root}/{folder_name}/{name_version}", suffix="")

        container_name += suffix

        if not unreal.EditorAssetLibrary.does_directory_exist(asset_dir):
            path = get_representation_path(repre_entity)
            loaded_options = {"default_conversion": False}
            self.import_and_containerize(path, asset_dir, asset_name,
                                         container_name, loaded_options)

        self.imprint(
            folder_path,
            asset_dir,
            container_name,
            asset_name,
            repre_entity,
            product_type,
        )

        asset_content = unreal.EditorAssetLibrary.list_assets(
            asset_dir, recursive=True, include_folder=False
        )

        for a in asset_content:
            unreal.EditorAssetLibrary.save_asset(a)

    def remove(self, container):
        path = container["namespace"]
        parent_path = os.path.dirname(path)

        unreal.EditorAssetLibrary.delete_directory(path)

        asset_content = unreal.EditorAssetLibrary.list_assets(
            parent_path, recursive=False
        )

        if len(asset_content) == 0:
            unreal.EditorAssetLibrary.delete_directory(parent_path)
