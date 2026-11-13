from pathlib import Path
import os
import unreal

from ayon_core.pipeline import get_current_project_name
from ayon_core.pipeline.publish import PublishError
from ayon_unreal.api import pipeline, rendering
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

        render_dirs = self._get_render_dirs(instance)

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

                product_base_type = "render"
                new_product_name = f"{data.get('productName')}_{seq_name}"
                new_instance = context.create_instance(
                    new_product_name
                )
                new_instance[:] = seq_name

                new_data = new_instance.data

                new_data["folderPath"] = instance.data["folderPath"]
                new_data["setMembers"] = seq_name
                new_data["productName"] = new_product_name
                new_data["productType"] = product_base_type
                new_data["productBaseType"] = product_base_type
                new_data["family"] = product_base_type
                new_data["families"] = [product_base_type, "review"]
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

                render_dir = self._find_render_dir(
                    render_dirs, s.get('output'))
                render_path = Path(render_dir)

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

    def _get_render_dirs(self, instance):
        """Get base directories local renders can be found in.

        Work directory (same as farm renders) first, legacy
        `{root[renders]}/{project}` second when project has `renders` root.

        Returns:
            list[str]: Base render directories.

        """
        project_name = get_current_project_name()
        task_name = (
            instance.data.get("task")
            or instance.context.data.get("task")
            or os.environ.get("AYON_TASK_NAME")
        )
        render_dirs = [
            rendering.get_render_dir_by_names(
                project_name, instance.data["folderPath"], task_name)
        ]
        legacy_dir = rendering.get_legacy_render_dir(project_name)
        if legacy_dir:
            render_dirs.append(legacy_dir)
        return render_dirs

    def _find_render_dir(self, render_dirs, output):
        """Find first existing render directory for sequence output.

        Raises:
            PublishError: When no directory exists.

        """
        candidates = [f"{base}/{output}" for base in render_dirs]
        for candidate in candidates:
            if os.path.isdir(candidate):
                return candidate

        msg = (
            "Render directory not found, searched: "
            f"{', '.join(candidates)}. Please render with the render instance."
        )
        self.log.error(msg)
        raise PublishError(msg, title="Render directory not found.")
