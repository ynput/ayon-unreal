import shutil
from copy import deepcopy
from pathlib import Path

from ayon_core.pipeline import Anatomy
from ayon_core.pipeline import publish
from ayon_core.lib import StringTemplate


import unreal


class ExtractMRQAsManifest(publish.Extractor):
    label = "Extract Media Render Queue as Manifest"
    hosts = ["unreal"]
    families = ["render.farm"]

    def process(self, instance):
        self.anatomy_data = deepcopy(instance.data["anatomyData"])
        self.project_data = deepcopy(instance.data["projectEntity"])

        self.get_work_file_template()
        self.configure_mrq(instance)
        self.serialize_mrq(instance)
        self.copy_manifest_to_publish(instance)

    def get_work_file_template(self):
        # get work file template
        #   how can i build a @token?
        project_templates = self.project_data["config"]["templates"]
        _dir_template = project_templates["work"]["default"]["directory"]
        _file_template = project_templates["work"]["unreal"]["file"]

        self.dir_template = StringTemplate(_dir_template)
        self.file_template = StringTemplate(_file_template)

    def configure_mrq(self, instance):
        self.mrq = instance.context.data["mrq"]
        for job in self.mrq.get_jobs():
            if job is instance.data["mrq_job"]:
                job.set_is_enabled(True)
                continue
            job.set_is_enabled(False)

    def serialize_mrq(self, instance):
        # serialize mrq to file and string
        _, manifest = (
            unreal.MoviePipelineEditorLibrary.save_queue_to_manifest_file(
                self.mrq
            )
        )
        manifest_string = (
            unreal.MoviePipelineEditorLibrary.convert_manifest_file_to_string(
                manifest
            )
        )
        instance.data["mrq_manifest"] = (
            manifest_string  # save manifest string for potential submission via string
        )
        self.manifest_to_publish = Path(manifest).resolve()

    def copy_manifest_to_publish(self, instance):
        # initialize template data
        anatomy = Anatomy(self.project_data["name"])
        template_data = self.anatomy_data
        template_data["root"] = anatomy.roots

        # get current product name and append manifest, set ext to .utxt
        template_data["product"]["name"] += "Manifest"
        template_data["ext"] = "utxt"

        work_dir = Path(self.dir_template.format_strict(template_data))
        work_file = Path(self.file_template.format_strict(template_data))
        work_manifest = work_dir / work_file
        self.log.debug(f"{work_manifest = }")

        if not work_dir.exists():
            self.log.info(f"Creating publish directory: {work_dir}")
            work_dir.mkdir(parents=True)

        shutil.copyfile(self.manifest_to_publish, work_manifest)
        instance.data["work_mrq"] = work_manifest.as_posix()
        jobinfo = instance.data["deadline"].get("job_info")
        jobinfo.EnvironmentKeyValue.update(
            {"AYON_UNREAL_WORK_MRQ": work_manifest.as_posix()}
        )
        self.log.info(f"Manifest extracted to: {work_manifest}")
