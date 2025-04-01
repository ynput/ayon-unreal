import pyblish.api

import unreal


class ValidateMRQ(pyblish.api.InstancePlugin):
    label = "Validate Media Render Queue"
    order = pyblish.api.ValidatorOrder
    hosts = ["unreal"]
    families = ["render", "render.farm"]

    def process(self, instance):
        self.curr_mrq = instance.context.data["mrq"]

        self.validate_no_dirty_packages()
        self.validate_map()
        self.validate_instance_in_mrq(instance)

    def validate_no_dirty_packages(self):
        # The user must save their work and check it in so that Deadline can sync it.
        dirty_packages = []
        dirty_packages.extend(
            unreal.EditorLoadingAndSavingUtils.get_dirty_content_packages()
        )
        dirty_packages.extend(
            unreal.EditorLoadingAndSavingUtils.get_dirty_map_packages()
        )

        # Sometimes the dialog will return `False` even when there are no packages to save. so we are
        # being explict about the packages we need to save
        if dirty_packages:
            if not unreal.EditorLoadingAndSavingUtils.save_dirty_packages_with_dialog(
                True, True
            ):
                message = (
                    "One or more jobs in the queue have an unsaved map/content. "
                    "\n{packages}\n"
                    "Please save and check-in all work before submission.".format(
                        packages="\n".join(
                            [item.get_name() for item in dirty_packages]
                        )
                    )
                )

                raise Exception(message)

    def validate_map(self):
        is_valid_map = (
            unreal.MoviePipelineEditorLibrary.is_map_valid_for_remote_render(
                self.curr_mrq.get_jobs()
            )
        )
        if not is_valid_map:
            unreal.EditorDialog.show_message(
                "Unsaved Maps",
                "One or more jobs in the queue have an unsaved map as their target map. These unsaved maps cannot be loaded by an external process, and the render has been aborted.",
                unreal.AppMsgType.OK,
            )
            self.on_executor_finished_impl()
            return

    def validate_instance_in_mrq(self, instance):
        instance_in_mrq = False
        for job in self.curr_mrq.get_jobs():
            if job is instance.data["mrq_job"]:
                instance_in_mrq = True
        if not instance_in_mrq:
            raise Exception(
                "Instance not found in Media Render Queue. Try to clear your current MRQ and try again."
            )
