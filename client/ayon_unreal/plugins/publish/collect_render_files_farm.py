import os
import pyblish.api
from pathlib import Path
from copy import deepcopy

import unreal

from ayon_core.pipeline import Anatomy
from ayon_core.lib import StringTemplate

from ayon_unreal.api.rendering import SUPPORTED_EXTENSION_MAP


class CollectRemoteRenderFiles(pyblish.api.InstancePlugin):
    order = pyblish.api.CollectorOrder + 0.497
    label = "Collect Remote Render Files"
    hosts = ["unreal"]
    families = ["render", "render.farm"]

    def process(self, instance):
        if not instance.context.data.get("auto_handle_mrq"):
            self.log.info(
                "MRQ isn't automatically built. Skipping render output override."
            )
            return

        self.job = instance.data["mrq_job"]
        self.mrq = instance.context.data["mrq"]
        self.anatomy_data = deepcopy(instance.data["anatomyData"])
        self.project_data = deepcopy(instance.data["projectEntity"])

        self.job_config = self.job.get_configuration()
        (work_dir, work_file) = self.get_path_overrides()

        # overrides jobs output directory and file name
        ue_dir_override = unreal.DirectoryPath()
        ue_dir_override.path = Path(work_dir).as_posix()
        ue_file_override = work_file + ".{frame_number}"
        job_output_settings = self.job_config.find_setting_by_class(
            unreal.MoviePipelineOutputSetting
        )
        job_output_settings.set_editor_property("output_directory", ue_dir_override)
        job_output_settings.set_editor_property("file_name_format", ue_file_override)

        # override expected files
        exp_files_override = []
        for exp_file in instance.data["expectedFiles"]:
            splits = exp_file.split(".")
            exp_file_override = work_dir / f"{work_file}.{splits[1]}.{splits[2]}"
            exp_files_override.append(exp_file_override.as_posix())
        instance.data["expectedFiles"] = exp_files_override

    def get_path_overrides(self):
        self._get_work_file_template()

        # build output directory
        exr_settings = self.job_config.find_setting_by_class(
            unreal.MoviePipelineImageSequenceOutput_EXR
        )
        if not exr_settings:
            raise Exception("No EXR settings found in the job configuration.")

        # initialize template data
        anatomy = Anatomy(self.project_data["name"])
        template_data = self.anatomy_data
        template_data["root"] = anatomy.roots
        template_data["ext"] = "exr"

        # format the publish path
        project_templates = self.project_data["config"]["templates"]
        template_data["version"] = (
            f"v{template_data['version']:0{project_templates['common']['version_padding']}d}"
        )
        work_dir = self.dir_template.format_strict(template_data)
        work_file = self.file_template.format_strict(template_data)

        return (Path(work_dir), Path(work_file).stem)

    def _get_work_file_template(self):
        # get work file template
        #   how can i build a @token?
        project_templates = self.project_data["config"]["templates"]
        _dir_template = project_templates["work"]["default"]["directory"]
        _dir_template_parts = []
        for part in _dir_template.split(os.path.sep):
            if "version" in part:
                continue
            _dir_template_parts.append(part)

        _file_template = project_templates["work"]["unreal"]["file"]

        self.dir_template = StringTemplate(Path(*_dir_template_parts).as_posix())
        self.file_template = StringTemplate(_file_template)
