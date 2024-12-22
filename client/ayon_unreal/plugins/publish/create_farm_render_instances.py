import os
import attr
import unreal

import pyblish.api

from ayon_core.pipeline import publish, PublishError
from ayon_core.pipeline.publish import RenderInstance

from ayon_unreal.api import pipeline

from ayon_unreal.api.pipeline import UNREAL_VERSION
from ayon_unreal.api.rendering import (
    SUPPORTED_EXTENSION_MAP,
    get_render_config,
    set_output_extension_from_settings
)


@attr.s
class UnrealRenderInstance(RenderInstance):
    # extend generic, composition name is needed
    fps = attr.ib(default=None)
    projectEntity = attr.ib(default=None)
    stagingDir = attr.ib(default=None)
    publish_attributes = attr.ib(default={})
    file_names = attr.ib(default=[])
    master_level = attr.ib(default=None)
    mrq_job = attr.ib(default=None)
    config_path = attr.ib(default=None)
    app_version = attr.ib(default=None)
    output_settings = attr.ib(default=None)
    render_queue_path = attr.ib(default=None)


class CreateFarmRenderInstances(publish.AbstractCollectRender):

    order = pyblish.api.CollectorOrder + 0.21
    label = "Create Farm Render Instances"

    def preparing_rendering_instance(self, instance):
        context = instance.context

        data = instance.data
        data["remove"] = True

        ar = unreal.AssetRegistryHelpers.get_asset_registry()

        sequence = ar.get_asset_by_object_path(
            data.get("sequence")).get_asset()

        sequences = [{
            "sequence": sequence,
            "output": data.get("output"),
            "frame_range": (
                data.get("frameStart"), data.get("frameEnd"))
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
                if "_camera" not in s.get('sequence').get_name():
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
                    new_data["review"] = instance.data.get("review", False)
                    new_data["farm"] = instance.data.get("farm", False)

                    self.log.debug(f"new instance data: {new_data}")

    def get_instances(self, context):
        instances = []
        instances_to_remove = []

        current_file = context.data["currentFile"]
        version = 1  # TODO where to get this without change list

        project_name = context.data["projectName"]
        project_settings = context.data['project_settings']
        render_settings = project_settings["unreal"]["render_setup"]
        config_path, config = get_render_config(project_name, render_settings)
        if not config:
            raise RuntimeError("Please provide stored render config at path "
                "set in `ayon+settings://unreal/render_setup/render_config_path`")

        output_ext_from_settings = render_settings["render_format"]
        config = set_output_extension_from_settings(output_ext_from_settings,
                                                    config)

        ext = self._get_ext_from_config(config)
        if not ext:
            raise RuntimeError("Please provide output extension in config!")

        output_settings = config.find_or_add_setting_by_class(
            unreal.MoviePipelineOutputSetting)

        resolution = output_settings.output_resolution
        resolution_width = resolution.x
        resolution_height = resolution.y

        output_fps = output_settings.output_frame_rate
        fps = f"{output_fps.denominator}.{output_fps.numerator}"

        render_queue_path = (
            project_settings["unreal"]["render_queue_path"]
        )
        self.log.debug(f"{render_queue_path = }")
        auto_handle_mrq = False
        if not unreal.EditorAssetLibrary.does_asset_exist(
                render_queue_path):
            # TODO: temporary until C++ blueprint is created as it is not
            #   possible to create renderQueue. Also, we could
            #   use Render Graph from UE 5.4

            mrq = unreal.MoviePipelineQueue()
            auto_handle_mrq = True
            mrq.delete_all_jobs()
        else:
            mrq = unreal.EditorAssetLibrary.load_asset(
                project_settings["unreal"]["render_queue_path"]
            )

        for inst in context:
            instance_families = inst.data.get("families", [])
            product_name = inst.data["productName"]

            if not inst.data.get("active", True):
                continue

            family = inst.data["family"]
            if family not in ["render"]:
                continue

            # skip if local render instances
            if "render.local" in instance_families:
                continue

            if not inst.data.get("farm", False):
                self.log.info("Skipping local render instance")
                continue
            # Get current jobs
            jobs = mrq.get_jobs()

            # backward compatibility
            task_name = inst.data.get("task") or inst.data.get("task_name")
            self.log.debug(f"Task name:{task_name}")

            ar = unreal.AssetRegistryHelpers.get_asset_registry()
            sequence = (ar.get_asset_by_object_path(inst.data["sequence"]).
                        get_asset())
            if not sequence:
                raise PublishError(f"Cannot find {inst.data['sequence']}")

            # Get current job
            job = next(
                (
                    job
                    for job in jobs
                    if job.sequence.export_text() == inst.data["sequence"]
                ),
                None,
            )
            if not job and not auto_handle_mrq:
                raise PublishError(
                    f"Cannot find job with sequence {inst.data['sequence']}"
                )
            else:
                # create job for instance
                job = mrq.allocate_new_job()
                job.map = unreal.SoftObjectPath(inst.data["master_level"])
                job.sequence = unreal.SoftObjectPath(inst.data["sequence"])

                # TODO: present render presets as combobox on ui item
                # TODO: set output paths on config
                job.set_configuration(config)

            # current frame range - might be different from created
            frame_start = sequence.get_playback_start()
            # in Unreal 1 of 60 >> 0-59
            frame_end = sequence.get_playback_end() - 1

            inst.data["frameStart"] = frame_start
            inst.data["frameEnd"] = frame_end

            frame_placeholder = "#" * output_settings.zero_pad_frame_numbers
            version = (
                version
                if output_settings.auto_version
                else output_settings.version_number
            )

            exp_file_name = self._get_expected_file_name(
                output_settings.file_name_format,
                ext,
                frame_placeholder,
                job,
                version,
            )

            publish_attributes = {}

            try:
                review = bool(inst.data["creator_attributes"].get("review"))
            except KeyError:
                review = inst.data.get("review", False)

            new_instance = UnrealRenderInstance(
                family="render",
                families=["render.farm"],
                version=version,
                time="",
                source=current_file,
                label=f"{product_name} - {family}",
                productName=product_name,
                productType="render",
                folderPath=inst.data["folderPath"],
                task=task_name,
                attachTo=False,
                setMembers='',
                publish=True,
                name=product_name,
                resolutionWidth=resolution_width,
                resolutionHeight=resolution_height,
                pixelAspect=1,
                tileRendering=False,
                tilesX=0,
                tilesY=0,
                review=review,
                frameStart=frame_start,
                frameEnd=frame_end,
                frameStep=1,
                fps=fps,
                publish_attributes=publish_attributes,
                file_names=[exp_file_name],
                app_version=f"{UNREAL_VERSION.major}.{UNREAL_VERSION.minor}",
                output_settings=output_settings,
                config_path=config_path,
                master_level=inst.data["master_level"],
                render_queue_path=render_queue_path,
                mrq_job=job,
                deadline=inst.data.get("deadline"),
            )
            context.data["mrq"] = mrq
            new_instance.farm = True

            instances.append(new_instance)
            instances_to_remove.append(inst)

        for instance in instances_to_remove:
            self.log.debug(f"Removing instance: {instance}")
            context.remove(instance)
        return instances

    def _get_expected_file_name(
        self,
        file_name_format,
        ext,
        frame_placeholder,
        job: unreal.MoviePipelineExecutorJob,
        version: int,
    ):
        """Calculate file name that should be rendered."""
        sequence_path = job.sequence.export_text()
        map_path = job.map.export_text()

        sequence_name = os.path.splitext(os.path.basename(sequence_path))[0]
        map_name = os.path.splitext(os.path.basename(map_path))[0]

        file_name_format = file_name_format.replace("{sequence_name}", sequence_name)
        file_name_format = file_name_format.replace("{level_name}", map_name)
        file_name_format = file_name_format.replace("{job_name}", job.job_name)
        file_name_format = file_name_format.replace("{version}", f"v{version:03d}")
        file_name_format = file_name_format.replace("{frame_number}", frame_placeholder)
        return f"{file_name_format}.{ext}"

    def get_expected_files(self, render_instance: UnrealRenderInstance):
        """
            Returns list of rendered files that should be created by
            Deadline. These are not published directly, they are source
            for later 'submit_publish_job'.

        Args:
            render_instance (UnrealRenderInstance): to pull anatomy and parts used
                in url

        Returns:
            (list) of absolute urls to rendered file
        """
        start = render_instance.frameStart
        end = render_instance.frameEnd

        base_dir = self._get_output_dir(render_instance)
        expected_files = []
        for file_name in render_instance.file_names:
            if "#" in file_name:
                _spl = file_name.split("#")
                _len = (len(_spl) - 1)
                placeholder = "#"*_len
                for frame in range(start, end+1):
                    new_file_name = file_name.replace(placeholder,
                                                      str(frame).zfill(_len))
                    path = os.path.join(base_dir, new_file_name)
                    expected_files.append(path)

        return expected_files

    def _get_output_dir(self, render_instance):
        """
            Returns dir path of rendered files, used in submit_publish_job
            for metadata.json location.
            Should be in separate folder inside work area.

        Args:
            render_instance (RenderInstance):

        Returns:
            (str): absolute path to rendered files
        """
        # render to folder of project
        output_dir = render_instance.output_settings.output_directory.path
        base_dir = os.path.dirname(render_instance.source)
        output_dir = output_dir.replace("{project_dir}", base_dir)

        return output_dir

    def _get_ext_from_config(self, config):
        """Get set extension in render config.

        Bit weird approach to loop through supported extensions and bail on
        found.
        Assumes that there would be only single extension!

        Arg:
            config (unreal.MoviePipelineMasterConfig): render config
        """
        for ext, cls in SUPPORTED_EXTENSION_MAP.items():
            current_sett = config.find_setting_by_class(cls)
            if current_sett:
                return ext
