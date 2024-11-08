from pathlib import Path

import pyblish.api
import unreal
import os
from ayon_core.pipeline import get_current_project_name, Anatomy
from ayon_core.pipeline import publish
from ayon_core.pipeline.publish import PublishError
from ayon_unreal.api import pipeline


class ExtractIntermediateRepresentation(publish.Extractor):
    """ This extractor will try to find
    all the rendered frames, converting them into the mp4 file and publish it.
    """

    hosts = ["unreal"]
    order = pyblish.api.ExtractorOrder - 0.45
    families = ["editorial_pkg"]
    label = "Extract Intermediate Representation"

    def process(self, instance):
        self.log.debug("Collecting rendered files")
        data = instance.data
        ar = unreal.AssetRegistryHelpers.get_asset_registry()
        sequence = ar.get_asset_by_object_path(
            data.get('sequence')).get_asset()

        try:
            project = get_current_project_name()
            anatomy = Anatomy(project)
            root = anatomy.roots['renders']
        except Exception as e:
            raise Exception((
                "Could not find render root "
                "in anatomy settings.")) from e
        render_dir = f"{root}/{project}/editorial_pkg/{data.get('output')}"
        render_path = Path(render_dir)
        if not os.path.exists(render_path):
            msg = (
                f"Render directory {render_path} not found."
                " Please render with the render instance"
            )
            self.log.error(msg)
            raise PublishError(msg, title="Render directory not found.")
        self.log.debug(f"Collecting render path: {render_path}")
        frames = [str(x) for x in render_path.iterdir() if x.is_file()]
        frames = pipeline.get_sequence(frames)
        image_format = next((os.path.splitext(x)[-1].lstrip(".")
                                for x in frames), "exr")

        if "representations" not in instance.data:
            instance.data["representations"] = []

        representation = {
            'frameStart': int(sequence.get_playback_start()),
            'frameEnd': int(sequence.get_playback_end()),
            'name': "intermediate",
            'ext': image_format,
            'files': frames,
            'stagingDir': render_dir,
            'tags': ['review', 'remove']
        }
        instance.data["representations"].append(representation)
