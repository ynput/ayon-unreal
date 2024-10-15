# -*- coding: utf-8 -*-
"""Extract Editorial from Unreal."""
import os

import unreal
import pyblish.api

from ayon_core.pipeline import publish



class ExtractIntermediateRepresentation(publish.Extractor):
    """Extract Intermediate Files for Editorial Package"""

    label = "Extract Intermediate Representation"
    order = pyblish.api.ExtractorOrder - 0.45
    families = ["editorial_pkg"]

    def process(self, instance):
        staging_dir = self.staging_dir(instance)
        filename = "{}.mov".format(instance.name)

        if "representations" not in instance.data:
            instance.data["representations"] = []

        representation = {
            "name": "intermediate",
            "ext": "mov",
            'files': filename,
            "stagingDir": staging_dir,
        }
        instance.data["representations"].append(representation)
