from pathlib import Path

import unreal
import os
from ayon_core.pipeline import get_current_project_name, Anatomy
from ayon_core.pipeline.publish import PublishError
from ayon_unreal.api import pipeline
from ayon_unreal.api.lib import get_shot_tracks
import pyblish.api


class CollectIntermediateRender(pyblish.api.InstancePlugin):
    """ This collector will try to find 
    all the rendered frames for intermediate rendering

    Secondary step after local rendering. Should collect all rendered files and
    add them as representation.
    """
    order = pyblish.api.CollectorOrder + 0.001
    hosts = ["unreal"]
    families = ["editorial_pkg"]
    label = "Collect Intermediate Render"

    def process(self, instance):
        self.log.debug("Collecting rendered files")
        context = instance.context

        data = instance.data
        data['remove'] = True
        ar = unreal.AssetRegistryHelpers.get_asset_registry()
        sequence = ar.get_asset_by_object_path(
            data.get('sequence')).get_asset()
        members = instance.data["members"]
        for i, track in enumerate(get_shot_tracks(members)):
            track_name = track.get_shot_display_name()

            product_type = "render"
            new_product_name = (
                f"{data.get('productName')}_{track_name}_{i + 1}"
            )
            new_instance = context.create_instance(
                new_product_name
            )
            new_instance[:] = track_name

            new_data = new_instance.data

            new_data["folderPath"] = instance.data["folderPath"]
            new_data["setMembers"] = track_name
            new_data["productName"] = new_product_name
            new_data["productType"] = product_type
            new_data["family"] = product_type
            new_data["families"] = [product_type, "review"]
            new_data["parent"] = data.get("parent")
            new_data["level"] = data.get("level")
            new_data["output"] = data['output']
            new_data["fps"] = sequence.get_display_rate().numerator
            new_data["frameStart"] = int(track.get_start_frame())
            new_data["frameEnd"] = int(track.get_end_frame())
            new_data["sequence"] = track_name
            new_data["master_sequence"] = data["master_sequence"]
            new_data["master_level"] = data["master_level"]

            self.log.debug(f"new instance data: {new_data}")

            try:
                project = get_current_project_name()
                anatomy = Anatomy(project)
                root = anatomy.roots['renders']
            except Exception as e:
                raise Exception((
                    "Could not find render root "
                    "in anatomy settings.")) from e
            render_dir = f"{root}/{project}/editorial_pkg/{data.get('output')}"
            render_dir = f"{render_dir}/{track_name}_{i + 1}"
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

            if "representations" not in new_instance.data:
                new_instance.data["representations"] = []

            repr = {
                'frameStart': int(track.get_start_frame()),
                'frameEnd': int(track.get_end_frame()),
                'name': image_format,
                'ext': image_format,
                'files': frames,
                'stagingDir': render_dir,
                'tags': ['review']
            }
            new_instance.data["representations"].append(repr)
