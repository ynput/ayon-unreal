# -*- coding: utf-8 -*-
from pathlib import Path
import unreal

from ayon_core.pipeline import CreatorError
from ayon_unreal.api.plugin import (
    UnrealAssetCreator
)


class CreateEditorialPackage(UnrealAssetCreator):
    """Create Editorial Package."""

    identifier = "io.ayon.creators.unreal.editorial_pkg"
    label = "Editorial Package"
    product_type = "editorial_pkg"
    icon = "camera"

    def create_instance(
            self, instance_data, product_name, pre_create_data,
            selected_asset_path, master_seq, master_lvl, seq_data
    ):
        instance_data["members"] = [selected_asset_path]
        instance_data["sequence"] = selected_asset_path
        instance_data["master_sequence"] = master_seq
        instance_data["master_level"] = master_lvl
        instance_data["output"] = seq_data.get('output')
        instance_data["frameStart"] = seq_data.get('frame_range')[0]
        instance_data["frameEnd"] = seq_data.get('frame_range')[1]


        super(CreateEditorialPackage, self).create(
            product_name,
            instance_data,
            pre_create_data)

    def create(self, product_name, instance_data, pre_create_data):
        self.create_from_existing_sequence(
            product_name, instance_data, pre_create_data)

    def create_from_existing_sequence(
            self, product_name, instance_data, pre_create_data
    ):
        ar = unreal.AssetRegistryHelpers.get_asset_registry()

        sel_objects = unreal.EditorUtilityLibrary.get_selected_assets()
        selection = [
            a.get_path_name() for a in sel_objects
            if a.get_class().get_name() == "LevelSequence"]

        if len(selection) == 0:
            raise CreatorError("Please select at least one Level Sequence.")

        seq_data = {}

        for sel in selection:
            selected_asset = ar.get_asset_by_object_path(sel).get_asset()
            selected_asset_path = selected_asset.get_path_name()
            selected_asset_name = selected_asset.get_name()
            search_path = Path(selected_asset_path).parent.as_posix()
            package_name = f"{search_path}/{selected_asset_name}"
            # Get the master sequence and the master level.
            # There should be only one sequence and one level in the directory.
            try:
                ar_filter = unreal.ARFilter(
                    class_names=["LevelSequence"],
                    package_names=[package_name],
                    package_paths=[search_path],
                    recursive_paths=False)
                sequences = ar.get_assets(ar_filter)
                master_seq_obj = sequences[0].get_asset()
                master_seq = master_seq_obj.get_path_name()
                ar_filter = unreal.ARFilter(
                    class_names=["World"],
                    package_paths=[search_path],
                    recursive_paths=False)
                levels = ar.get_assets(ar_filter)
                master_lvl = levels[0].get_asset().get_path_name()
            except IndexError:
                raise RuntimeError(
                    "Could not find the hierarchy for the selected sequence.")
            seq_data.update({
                "output": f"{selected_asset_name}",
                "frame_range": (
                    selected_asset.get_playback_start(),
                    selected_asset.get_playback_end())
            })
        self.create_instance(
            instance_data, product_name, pre_create_data,
            selected_asset_path, master_seq, master_lvl, seq_data)
