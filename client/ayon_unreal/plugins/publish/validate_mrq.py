import pyblish.api

import unreal

from ayon_core.pipeline.publish import PublishValidationError


class ValidateMRQ(pyblish.api.InstancePlugin):
    label = "Validate Media Render Queue"
    order = pyblish.api.ValidatorOrder
    hosts = ["unreal"]
    families = ["render.farm"]

    def process(self, instance):
        self.curr_mrq = instance.data["mrq"]

        self.validate_no_dirty_packages()
        self.validate_map()

    def validate_no_dirty_packages(self):
        # The user must save their work and check it in so that Deadline can sync it.
        # NOTE: this only checks and reports - it must never save on the
        # user's behalf. Forcing a save here would resave any dirty package
        # found (including ones that became dirty for unrelated reasons,
        # e.g. an engine/plugin version bump touching unrelated assets on
        # load) as a side effect of merely running validation, which then
        # shows up as an unwanted checkout/change in Perforce.
        dirty_packages = []
        dirty_packages.extend(
            unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
        )
        dirty_packages.extend(
            unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
        )

        if dirty_packages:
            message = (
                "One or more jobs in the queue have unsaved map/content "
                "changes:\n{packages}\n"
                "Please save and check in all work before submission.".format(
                    packages="\n".join(
                        item.get_name() for item in dirty_packages
                    )
                )
            )
            raise PublishValidationError(
                message, title="Unsaved changes in Media Render Queue"
            )

    def validate_map(self):
        is_valid_map = (
            unreal.MoviePipelineEditorLibrary.is_map_valid_for_remote_render(
                self.curr_mrq.get_jobs()
            )
        )
        if not is_valid_map:
            raise PublishValidationError(
                "One or more jobs in the queue have an unsaved map as their "
                "target map. These unsaved maps cannot be loaded by an "
                "external process. Please save the map and try again.",
                title="Unsaved Maps",
            )
