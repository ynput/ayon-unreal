import pyblish.api
from pathlib import Path
from copy import deepcopy

import unreal

from ayon_core.pipeline import Anatomy, PublishError
from ayon_core.lib import StringTemplate

from ayon_unreal.api.rendering import (
    SUPPORTED_EXTENSION_MAP,
    set_graph_output_overrides,
)


class CollectRemoteRenderFiles(pyblish.api.InstancePlugin):
    order = pyblish.api.CollectorOrder + 0.497
    label = "Collect Remote Render Files"
    hosts = ["unreal"]
    families = ["render.farm"]

    def process(self, instance):
        if not instance.context.data.get("auto_handle_mrq"):
            self.log.info(
                "MRQ isn't automatically built. Skipping render output override."
            )
            return

        self.job = instance.data["mrq_job"]
        self.render_format = (
            instance.context.data["project_settings"]["unreal"]
            ["render_setup"]["render_format"]
        )
        self.anatomy_data = deepcopy(instance.data["anatomyData"])
        self.project_data = deepcopy(instance.data["projectEntity"])

        if instance.data.get("render_config_is_graph"):
            work_dir, work_file = self._get_work_paths()
            self._set_graph_output_overrides(work_dir, work_file)
        else:
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

        # override expected files, `<name>.<frame>.<ext>`
        exp_files_override = []
        file_names_override = []
        for exp_file in instance.data["expectedFiles"]:
            _, frame, ext = Path(exp_file).name.rsplit(".", 2)
            exp_file_override = work_dir / f"{work_file}.{frame}.{ext}"
            exp_files_override.append(exp_file_override.as_posix())
            file_name = f"{work_file}.{'#' * len(frame)}.{ext}"
            if file_name not in file_names_override:
                file_names_override.append(file_name)
        instance.data["expectedFiles"] = exp_files_override
        # used by Deadline submission for job output path
        instance.data["file_names"] = file_names_override

    def _set_graph_output_overrides(self, work_dir, work_file):
        """Point Movie Render Graph job output to the AYON work directory.

        Missing variables are reported by `ValidateMovieGraphOutput`.

        Args:
            work_dir (Path): Output directory.
            work_file (str): Output file name without frame and extension.

        """
        try:
            missing = set_graph_output_overrides(
                self.job,
                Path(work_dir).as_posix(),
                f"{work_file}.{{frame_number}}",
            )
        except ValueError as exc:
            raise PublishError(str(exc)) from exc
        for variable_name in missing:
            self.log.warning(
                f"Movie Render Graph '{self.job.get_graph_preset().get_name()}'"
                f" doesn't expose '{variable_name}' variable."
            )

    def get_path_overrides(self):
        # build output directory
        output_cls = SUPPORTED_EXTENSION_MAP.get(self.render_format.lower())
        if not output_cls:
            raise PublishError(
                f"Unsupported render format '{self.render_format}'.")
        if not self.job_config.find_setting_by_class(output_cls):
            raise PublishError(
                f"No '{self.render_format}' output found in the job "
                "configuration.")

        return self._get_work_paths()

    def _get_work_paths(self):
        """Get work directory and file name (without extension) for output.

        Returns:
            tuple[Path, str]: Work directory and file name.

        """
        self._get_work_file_template()

        # initialize template data
        anatomy = Anatomy(self.project_data["name"])
        template_data = self.anatomy_data
        template_data["root"] = anatomy.roots
        template_data["ext"] = self.render_format

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
        # AYON templates always use forward slashes
        for part in _dir_template.split("/"):
            if "version" in part:
                continue
            _dir_template_parts.append(part)

        # NOTE: i should get a separate template for ue renders
        #       _file_template is rather the ue project name template
        _file_template = project_templates["work"]["unreal"]["file"]
        _file_template_parts = _file_template.split(".")

        self.dir_template = StringTemplate(Path(*_dir_template_parts).as_posix())
        folder_name = self.anatomy_data["folder"]["name"]
        product_name = self.anatomy_data["product"]["name"]
        self.file_template = StringTemplate(
            f"{_file_template_parts[0]}_{folder_name}_{product_name}.{_file_template_parts[1]}"
        )
