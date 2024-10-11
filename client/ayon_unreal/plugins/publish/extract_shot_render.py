# -*- coding: utf-8 -*-
"""Extract Editorial from Unreal."""
import os

import unreal

from ayon_core.pipeline import publish



class ExtractEditorial(publish.Extractor):
    """Extract Editorial"""

    label = "Extract Shot Render(Clip)"
    hosts = ["unreal"]
    families = ["clip"]

    def process(self, instance):
        staging_dir = self.staging_dir(instance)
        filename = "{}.mov".format(instance.name)

        if "representations" not in instance.data:
            instance.data["representations"] = []

        representation = {
            'name': 'mov',
            'ext': 'mov',
            'files': filename,
            "stagingDir": staging_dir,
        }
        instance.data["representations"].append(representation)
