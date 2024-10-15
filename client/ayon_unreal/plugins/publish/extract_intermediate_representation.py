# -*- coding: utf-8 -*-
"""Extract Editorial from Unreal."""
import os

import unreal
import pyblish.api

from ayon_core.pipeline import publish
from ayon_unreal.api.rendering import editorial_rendering, clear_render_queue
from ayon_unreal.api.lib import get_shot_tracks


class ExtractIntermediateRepresentation(publish.Extractor):
    """Extract Intermediate Files for Editorial Package"""

    label = "Extract Intermediate Representation"
    order = pyblish.api.ExtractorOrder - 0.45
    families = ["editorial_pkg"]

    def process(self, instance):
        if "representations" not in instance.data:
            instance.data["representations"] = []
        staging_dir = self.staging_dir(instance)
        master_level = instance.data["level"]
        members = instance.data["members"]
        files = []
        representation_list = []
        clear_render_queue()
        for track in get_shot_tracks(members):
            folder_path = instance.data["folderPath"]
            folder_path_name = folder_path.lstrip("/").replace("/", "_")

            staging_dir = self.staging_dir(instance)
            timeline_name = track.get_shot_display_name()
            subfolder_name = folder_path_name + "_" + timeline_name

            staging_dir = os.path.normpath(
                os.path.join(staging_dir, subfolder_name))
            filename = f"{instance.name}_{timeline_name}"
            filename_ext =  f"{instance.name}_{timeline_name}.exr"
            editorial_rendering(
                track, timeline_name, members[0], master_level, staging_dir, filename)
            files.append(filename_ext)

            representation = {
                "name": "intermediate",
                "ext": "exr",
                'files': files,
                "stagingDir": staging_dir,
                'tags': ['review']
            }
            representation_list.append(representation)
        instance.data["representations"].extend(representation_list)
