# -*- coding: utf-8 -*-
from pathlib import Path
import unreal

from ayon_core.pipeline import CreatorError
from ayon_unreal.api.pipeline import get_subsequences, get_movie_shot_tracks
from ayon_unreal.api.plugin import (
    UnrealAssetCreator
)
from ayon_core.lib import BoolDef, EnumDef, TextDef, UILabelDef, NumberDef


class CreateEditorialPackage(UnrealAssetCreator):
    """Create Editorial Package."""

    identifier = "io.ayon.creators.unreal.editorial_pkg"
    label = "Editorial Package"
    product_type = "editorial_pkg"
    icon = "camera"

    def create_instance(
            self, instance_data, product_name, pre_create_data,
            selected_asset_path, master_seq, master_lvl
    ):
        instance_data["members"] = [selected_asset_path]
        instance_data["sequence"] = selected_asset_path
        instance_data["master_sequence"] = master_seq
        instance_data["master_level"] = master_lvl

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

        seq_data = None

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
                unreal.log("sequences")
                unreal.log(sequences)
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

        self.create_instance(
            instance_data, product_name, pre_create_data,
            selected_asset_path, master_seq, master_lvl)

    def get_instance_attr_defs(self):
        def header_label(text):
            return f"<br><b>{text}</b>"
        return [
            # hierarchyData
            UILabelDef(
                label=header_label("Shot Template Keywords")
            ),
            TextDef(
                "folder",
                label="{folder}",
                tooltip="Name of folder used for root of generated shots.\n",
                default="shot",
            ),
            TextDef(
                "episode",
                label="{episode}",
                tooltip=f"Name of episode.\n",
                default="ep01",
            ),
            TextDef(
                "sequence",
                label="{sequence}",
                tooltip=f"Name of sequence of shots.\n",
                default="sq01",
            ),
            TextDef(
                "track",
                label="{track}",
                tooltip=f"Name of timeline track.\n",
                default="{_track_}",
            ),
            TextDef(
                "shot",
                label="{shot}",
                tooltip="Name of shot. '#' is converted to padded number.",
                default="sh###",
            ),

            # renameHierarchy
            UILabelDef(
                label=header_label("Shot Hierarchy and Rename Settings")
            ),
            TextDef(
                "hierarchy",
                label="Shot Parent Hierarchy",
                tooltip="Parents folder for shot root folder, "
                        "Template filled with *Hierarchy Data* section",
                default="{folder}/{sequence}",
            ),
            BoolDef(
                "clipRename",
                label="Rename Shots/Clips",
                tooltip="Renaming selected clips on fly",
                default=False,
            ),
            TextDef(
                "clipName",
                label="Rename Template",
                tooltip="template for creating shot names, used for "
                        "renaming (use rename: on)",
                default="{sequence}{shot}",
            ),
            NumberDef(
                "countFrom",
                label="Count Sequence from",
                tooltip="Set where the sequence number starts from",
                default=10,
            ),
            NumberDef(
                "countSteps",
                label="Stepping Number",
                tooltip="What number is adding every new step",
                default=10,
            ),

            # verticalSync
            UILabelDef(
                label="Vertical Synchronization of Attributes"
            ),
            BoolDef(
                "vSyncOn",
                label="Enable Vertical Sync",
                tooltip="Switch on if you want clips above "
                        "each other to share its attributes",
                default=True,
            ),
            EnumDef(
                "vSyncTrack",
                label="Hero Track",
                tooltip="Select driving track name which should "
                        "be mastering all others",
                items= ["<nothing to select>"],
            ),

            # publishSettings
            UILabelDef(
                label=header_label("Clip Publish Settings")
            ),
            EnumDef(
                "clip_variant",
                label="Product Variant",
                tooltip="Chosen variant which will be then used for "
                        "product name, if <track_name> "
                        "is selected, name of track layer will be used",
                items=['<track_name>', 'main', 'bg', 'fg', 'bg', 'animatic'],
            ),
            EnumDef(
                "productType",
                label="Product Type",
                tooltip="How the product will be used",
                items=['plate'],  # it is prepared for more types
            ),
            BoolDef(
                "export_audio",
                label="Include audio",
                tooltip="Process subsets with corresponding audio",
                default=False,
            ),
            BoolDef(
                "sourceResolution",
                label="Source resolution",
                tooltip="Is resolution taken from timeline or source?",
                default=False,
            ),

            # shotAttr
            UILabelDef(
                label=header_label("Shot Attributes"),
            ),
            NumberDef(
                "workfileFrameStart",
                label="Workfiles Start Frame",
                tooltip="Set workfile starting frame number",
                default=1001,
            ),
            NumberDef(
                "handleStart",
                label="Handle Start (head)",
                tooltip="Handle at start of clip",
                default=0,
            ),
            NumberDef(
                "handleEnd",
                label="Handle End (tail)",
                tooltip="Handle at end of clip",
                default=0,
            ),
        ]
