# -*- coding: utf-8 -*-
"""Extract Editorial from Unreal."""
import os

import unreal

from ayon_core.pipeline import publish



class ExtractEditorial(publish.Extractor):
    """Extract Editorial"""

    label = "Extract Editorial"
    hosts = ["unreal"]
    families = ["editorial"]

    def process(self, instance):
        pass
        staging_dir = self.staging_dir(instance)
        sequence_data = instance.data.get("sequence_data")
        filename = "{}.edl".format(instance.name)

        if "representations" not in instance.data:
            instance.data["representations"] = []

            representation = {
                'name': 'edl',
                'ext': 'edl',
                'files': filename,
                "stagingDir": staging_dir,
            }
        instance.data["representations"].append(representation)
