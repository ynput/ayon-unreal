# -*- coding: utf-8 -*-
from pathlib import Path
import ast
import unreal

from ayon_core.pipeline import CreatorError, CreatedInstance
from ayon_unreal.api.lib import get_shot_tracks
from ayon_unreal.api.plugin import (
    UnrealAssetCreator
)
from ayon_core.lib import BoolDef, EnumDef, TextDef, UILabelDef, NumberDef


class CreateShotClip(UnrealAssetCreator):
    """Create Clip
    Process publishes shot from the selected level sequences
    """

    identifier = "io.ayon.creators.unreal.clip"
    label = "Editorial Clip"
    product_type = "clip"
    icon = "film"
    sel_objects = unreal.EditorUtilityLibrary.get_selected_assets()

    def _default_collect_instances(self):
        # cache instances if missing
        self.get_cached_instances(self.collection_shared_data)
        for instance in self.collection_shared_data[
                "unreal_cached_subsets"].get(self.identifier, []):
            # Unreal saves metadata as string, so we need to convert it back
            instance['creator_attributes'] = ast.literal_eval(
                instance.get('creator_attributes', '{}'))
            instance['publish_attributes'] = ast.literal_eval(
                instance.get('publish_attributes', '{}'))
            instance['members'] = ast.literal_eval(
                instance.get('members', '[]'))
            instance['families'] = ast.literal_eval(
                instance.get('families', '[]'))
            instance['active'] = ast.literal_eval(
                instance.get('active', ''))
            created_instance = CreatedInstance.from_existing(instance, self)
            self._add_instance_to_context(created_instance)

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

        if not get_shot_tracks(sel_objects):
            raise CreatorError("No movie shot tracks found in the selected level sequence")

        instance_data["members"] = selection
        instance_data["level"] = master_lvl

        super(CreateShotClip, self).create(
            product_name,
            instance_data,
            pre_create_data)
    # TODO: create sub-instances for publishing

    def get_pre_create_attr_defs(self):
        attrs = super().get_pre_create_attr_defs()
        def header_label(text):
            return f"<br><b>{text}</b>"
        gui_tracks = get_shot_tracks(self.sel_objects)

        return attrs + [
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
                items=gui_tracks or ["<nothing to select>"],
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
            EnumDef(
                "reviewTrack",
                label="Use Review Track",
                tooltip="Generate preview videos on fly, if "
                        "'< none >' is defined nothing will be generated.",
                items=['< none >'] + gui_tracks,
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
