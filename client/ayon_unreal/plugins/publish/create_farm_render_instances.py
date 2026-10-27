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
    apply_render_config_to_job,
    get_render_config,
    get_render_preset,
    is_movie_graph_config,
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
    mrq = attr.ib(default=None)
    mrq_job = attr.ib(default=None)
    config_path = attr.ib(default=None)
    app_version = attr.ib(default=None)
    output_settings = attr.ib(default=None)
    render_queue_path = attr.ib(default=None)
    render_config_is_graph = attr.ib(default=False)


class GraphRenderOutputSettings:
    def __init__(
        self,
        output_directory: str,
        file_name_format: str,
        version_number: int,
        zero_pad_frame_numbers: int = 4,
    ):
        self.output_directory = unreal.DirectoryPath()
        self.output_directory.path = output_directory
        self.file_name_format = file_name_format
        self.version_number = version_number
        self.zero_pad_frame_numbers = zero_pad_frame_numbers
        self.auto_version = False


class CreateFarmRenderInstances(publish.AbstractCollectRender):

    order = pyblish.api.CollectorOrder + 0.21
    label = "Create Farm Render Instances"
    families = ["render"]
    log = unreal.log

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
                sequences.extend(
                    {
                        "sequence": ss.get_sequence(),
                        "output": (
                            f"{s.get('output')}/" f"{ss.get_sequence().get_name()}"
                        ),
                        "frame_range": (
                            ss.get_start_frame(),
                            ss.get_end_frame() - 1,
                        ),
                    }
                    for ss in subscenes
                )
            elif "_camera" not in s.get('sequence').get_name():
                seq = s.get('sequence')
                seq_name = seq.get_name()

                new_product_name = f"{data.get('productName')}_{seq_name}"
                new_instance = context.create_instance(
                    new_product_name
                )
                new_instance[:] = seq_name

                new_data = new_instance.data

                new_data["folderPath"] = instance.data["folderPath"]
                new_data["setMembers"] = seq_name
                new_data["productName"] = new_product_name
                product_base_type = "render"
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
                new_data["review"] = instance.data.get("review", False)
                new_data["farm"] = instance.data.get("farm", False)

                self.log.debug(f"new instance data: {new_data}")

    def get_instances(self, context):
        instances = []
        instances_to_remove = []

        current_file = context.data["currentFile"]
        default_version = 1  # TODO where to get this without change list

        project_name = context.data["projectName"]
        project_settings = context.data['project_settings']
        render_settings = project_settings["unreal"]["render_setup"]

        output_ext_from_settings = render_settings["render_format"]

        for inst in context:
            render_preset =inst.data.get("creator_attributes", {}).get(
                "render_preset"
            )
            config_path, config = get_render_config(
                project_name, render_preset, render_settings
            )
            if not config:
                raise RuntimeError(
                    "Please provide stored render config at path "
                    "set in `ayon+settings://unreal/render_setup/render_config_path`"
                )
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

            is_graph_config = is_movie_graph_config(config)

            if is_graph_config:
                ext = output_ext_from_settings
                output_settings = None
                resolution_width = 1920
                resolution_height = 1080
                fps = 0
            else:
                # NOTE: do not mutate `config` here - it is the loaded,
                # Perforce-tracked render config/preset asset. Reading it
                # is fine, but `find_or_add_setting_by_class`/
                # `remove_setting` write directly into that on-disk asset
                # and dirty it on every publish. The forced output
                # extension is instead applied further below to the job's
                # own private configuration copy.
                ext = output_ext_from_settings

                output_settings = config.find_setting_by_class(
                    unreal.MoviePipelineOutputSetting
                )

                if output_settings:
                    resolution = output_settings.output_resolution
                    resolution_width = resolution.x
                    resolution_height = resolution.y

                    fps = None
                    if output_settings.use_custom_frame_rate:
                        output_fps = output_settings.output_frame_rate
                        fps = round(
                            output_fps.numerator / output_fps.denominator, 3
                        )
                else:
                    resolution_width = 1920
                    resolution_height = 1080
                    fps = None

            render_queue_path = render_settings["render_queue_path"]
            # Always build a transient, in-memory queue. The queue is only
            # ever serialized to a manifest file for Deadline (see
            # ExtractMRQAsManifest) - it is never saved back to
            # render_queue_path. Loading and mutating that persisted uasset
            # here used to dirty a Perforce-tracked asset on every publish
            # for no reason.
            mrq = unreal.MoviePipelineQueue()
            auto_handle_mrq = True
            context.data["auto_handle_mrq"] = auto_handle_mrq
            mrq.delete_all_jobs()

            # backward compatibility
            task_name = inst.data.get("task") or inst.data.get("task_name")
            self.log.debug(f"Task name:{task_name}")

            ar = unreal.AssetRegistryHelpers.get_asset_registry()
            sequence = (ar.get_asset_by_object_path(inst.data["sequence"]).
                        get_asset())
            if not sequence:
                raise PublishError(f"Cannot find {inst.data['sequence']}")

            # create job for instance
            job = mrq.allocate_new_job()
            job.map = unreal.SoftObjectPath(inst.data["master_level"])
            job.sequence = unreal.SoftObjectPath(inst.data["sequence"])
            if not fps:
                # no custom frame rate in render config, sequence rate is used
                display_rate = sequence.get_display_rate()
                fps = round(
                    display_rate.numerator / display_rate.denominator, 3
                )

            render_preset = inst.data['creator_attributes'].get("render_preset")
            if render_preset:
                config = get_render_preset(render_preset) or config

            apply_render_config_to_job(job, config)

            if not is_graph_config:
                # `set_configuration` duplicated `config` into a private
                # copy owned by the job - safe to mutate here, it never
                # touches the on-disk asset.
                job_config = set_output_extension_from_settings(
                    output_ext_from_settings, job.get_configuration()
                )
                ext = self._get_ext_from_config(job_config)
                if not ext:
                    raise RuntimeError(
                        "Please provide output extension in config!"
                    )

            # current frame range - might be different from created
            frame_start = sequence.get_playback_start()
            # in Unreal 1 of 60 >> 0-59
            frame_end = sequence.get_playback_end() - 1

            inst.data["frameStart"] = frame_start
            inst.data["frameEnd"] = frame_end

            if is_graph_config:
                shot_name = sequence.get_name()
                output_settings = GraphRenderOutputSettings(
                    output_directory=f"{inst.data['output']}",
                    file_name_format=f"{shot_name}.{{frame_number}}",
                    version_number=default_version,
                )
                display_rate = sequence.get_display_rate()
                fps = round(
                    display_rate.numerator / display_rate.denominator,
                    3,
                )

            frame_placeholder = "#" * output_settings.zero_pad_frame_numbers
            version = (
                default_version
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

            publish_attributes = inst.data.get("publish_attributes", {})

            try:
                review = bool(inst.data["creator_attributes"].get("review"))
            except KeyError:
                review = inst.data.get("review", False)

            self.log.debug(f"Creating UnrealRenderInstance for {product_name}", extra={"frameStart": frame_start, "frameEnd": frame_end})
            self.log.debug(f"Inst data: {inst.data}", extra={"frameStart": frame_start, "frameEnd": frame_end})
            try:
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
                    render_config_is_graph=is_graph_config,
                    mrq=mrq,
                    mrq_job=job,
                    deadline=inst.data.get("deadline"),
                )
            except ValueError as e:
                self.log.exception(f"Failed to create UnrealRenderInstance: {e}")
                raise PublishError(f"Failed to create UnrealRenderInstance: {e}") from e
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
