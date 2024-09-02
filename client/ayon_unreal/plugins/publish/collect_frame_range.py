# -*- coding: utf-8 -*-
import unreal  # noqa
import pyblish.api
from ayon_unreal.api.pipeline import get_frame_range




class CollectFrameRange(pyblish.api.InstancePlugin):
    """Collect Frame Range"""

    order = pyblish.api.CollectorOrder + 0.2
    label = "Collect Frame Range"
    hosts = ['unreal']
    families = ["camera"]

    def process(self, instance):
        for member in instance.data.get('members'):
            ar = unreal.AssetRegistryHelpers.get_asset_registry()
            data = ar.get_asset_by_object_path(member)
            is_level_sequence = (
                data.asset_class_path.asset_name == "LevelSequence")
            if is_level_sequence:
                sequence = data.get_asset()
                frameStart, frameEnd = get_frame_range(sequence)
                instance.data["clipIn"] = frameStart
                instance.data["clipOut"] = frameEnd
