# -*- coding: utf-8 -*-
from pathlib import Path

import unreal

from ayon_core.pipeline import CreatorError
from ayon_unreal.api.plugin import (
    UnrealAssetCreator
)


class CreateEditorial(UnrealAssetCreator):
    """Create Editorial
    Process publishes the selected level sequences with metadata info
    """

    identifier = "io.ayon.creators.unreal.editorial"
    label = "Editorial"
    product_type = "editorial"
    icon = "camera"

    def create_instance(
            self, instance_data, product_name, pre_create_data,
            selection, level
    ):
        instance_data["members"] = selection
        instance_data["sequence"] = selection[0]
        instance_data["level"] = level

        super(CreateEditorial, self).create(
            product_name,
            instance_data,
            pre_create_data)

    def create(self, product_name, instance_data, pre_create_data):
        ar = unreal.AssetRegistryHelpers.get_asset_registry()

        sel_objects = unreal.EditorUtilityLibrary.get_selected_assets()
        selection = [
            a.get_path_name() for a in sel_objects
            if a.get_class().get_name() == "LevelSequence"]

        if len(selection) == 0:
            raise CreatorError("Please select at least one Level Sequence.")

        master_lvl = None

        for sel in selection:
            search_path = Path(sel).parent.as_posix()
            # Get the master level.
            try:
                ar_filter = unreal.ARFilter(
                    class_names=["World"],
                    package_paths=[search_path],
                    recursive_paths=False)
                levels = ar.get_assets(ar_filter)
                master_lvl = levels[0].get_asset().get_path_name()
            except IndexError:
                raise CreatorError("Could not find any map for the selected sequence.")

        self.create_instance(
            instance_data, product_name, pre_create_data,
            selection, master_lvl)
