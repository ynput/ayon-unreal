# -*- coding: utf-8 -*-
from pathlib import Path
import ast
import unreal

from ayon_core.pipeline import CreatorError, CreatedInstance
from ayon_unreal.api.lib import get_shot_track_names
from ayon_unreal.api.plugin import (
    UnrealAssetCreator
)


class CreateEditorialPackage(UnrealAssetCreator):
    """Create Editorial Package."""

    identifier = "io.ayon.creators.unreal.editorial_pkg"
    label = "Editorial Package"
    product_type = "editorial_pkg"
    icon = "camera"

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

        shot_sections = get_shot_track_names(sel_objects)
        if not shot_sections:
            raise CreatorError("No movie shot tracks found in the selected level sequence")

        instance_data["members"] = selection
        instance_data["level"] = master_lvl

        super(CreateEditorialPackage, self).create(
            product_name,
            instance_data,
            pre_create_data)