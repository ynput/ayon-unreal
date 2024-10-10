from pathlib import Path

import unreal

from ayon_core.pipeline import get_current_project_name
from ayon_core.pipeline import Anatomy
from ayon_unreal.api import pipeline
import pyblish.api


class CollectEditorial(pyblish.api.InstancePlugin):
    """ This collector will collect all the editorial info
    """
    order = pyblish.api.CollectorOrder
    hosts = ["unreal"]
    families = ["editorial"]
    label = "Collect Editorial"

    def process(self, instance):
        ar = unreal.AssetRegistryHelpers.get_asset_registry()
        sequence = ar.get_asset_by_object_path(
            instance.data.get('sequence')).get_asset()

        subscenes = pipeline.get_subsequences(sequence)
        sub_seq_obj_list = []
        if subscenes:
            for sub_seq in subscenes:
                sub_seq_obj = sub_seq.get_sequence()
                if sub_seq_obj is None:
                    continue
                curr_editorial_data = {
                    "shot_name": sub_seq_obj.get_name(),
                    "sequence": sub_seq_obj,
                    "output": (f"{sequence.get_name()}/"
                               f"{sub_seq_obj.get_name()}"),
                    "frame_range": (
                        sub_seq.get_start_frame(),
                        sub_seq.get_end_frame()
                    )
                }
                sub_seq_obj_list.append(curr_editorial_data)
        instance.data.update({"sequence_data": sub_seq_obj_list})
