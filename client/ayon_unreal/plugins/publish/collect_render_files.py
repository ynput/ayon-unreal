from pathlib import Path
import os
import unreal

from ayon_core.pipeline import get_current_project_name, Anatomy
from ayon_core.pipeline.publish import PublishError
from ayon_unreal.api import pipeline
import pyblish.api


class CollectRenderFiles(pyblish.api.InstancePlugin):
    """ This collector will try to find all the rendered frames.

    Secondary step after local rendering. Should collect all rendered files and
    add them as representation.
    """
    order = pyblish.api.CollectorOrder + 0.001
    families = ["render.local"]
    label = "Collect Render Files"

    def process(self, instance):
        self.log.debug("Collecting rendered files")
        context = instance.context

        data = instance.data
        data['remove'] = True

        ar = unreal.AssetRegistryHelpers.get_asset_registry()

        sequence = ar.get_asset_by_object_path(
            data.get('sequence')).get_asset()

        sequences = [{
            "sequence": sequence,
            "output": data.get('output'),
            "frame_range": (
                data.get('frameStart'), data.get('frameEnd'))
        }]

        for s in sequences:
            self.log.debug(f"Processing: {s.get('sequence').get_name()}")
            subscenes = pipeline.get_subsequences(s.get('sequence'))

            if subscenes:
                for ss in subscenes:
                    sequences.append({
                        "sequence": ss.get_sequence(),
                        "output": (f"{s.get('output')}/"
                                   f"{ss.get_sequence().get_name()}"),
                        "frame_range": (
                            ss.get_start_frame(), ss.get_end_frame() - 1)
                    })
            else:
                # Avoid creating instances for camera sequences
                if "_camera" in s.get('sequence').get_name():
                    continue
                seq = s.get('sequence')
                seq_name = seq.get_name()

                product_type = "render"
                new_product_name = f"{data.get('productName')}_{seq_name}"
                new_instance = context.create_instance(
                    new_product_name
                )
                new_instance[:] = seq_name

                new_data = new_instance.data

                new_data["folderPath"] = instance.data["folderPath"]
                new_data["setMembers"] = seq_name
                new_data["productName"] = new_product_name
                new_data["productType"] = product_type
                new_data["family"] = product_type
                new_data["families"] = [product_type, "review"]
                new_data["parent"] = data.get("parent")
                new_data["level"] = data.get("level")
                new_data["output"] = s['output']
                new_data["fps"] = seq.get_display_rate().numerator
                new_data["frameStart"] = int(s.get('frame_range')[0])
                new_data["frameEnd"] = int(s.get('frame_range')[1])
                new_data["sequence"] = seq.get_path_name()
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

                render_dir = f"{root}/{project}/{s.get('output')}"
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
                    'frameStart': instance.data["frameStart"],
                    'frameEnd': instance.data["frameEnd"],
                    'name': image_format,
                    'ext': image_format,
                    'files': frames,
                    'stagingDir': render_dir,
                    'tags': ['review']
                }
                new_instance.data["representations"].append(repr)
