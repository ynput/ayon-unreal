# -*- coding: utf-8 -*-

import pyblish.api
from ayon_core.pipeline.publish import PublishValidationError


class ValidateIntermediateSettings(pyblish.api.InstancePlugin):
    """Ensure that the required intermediate settings are present
    in Core Addon for generating the video.

    """
    order = pyblish.api.ValidatorOrder
    label = "Validate Intermediate Settings"
    hosts = ['unreal']
    families = ["editorial_pkg"]
    video_exts = {"mov", "mp4"}

    def get_invalid(self, instance):
        invalid = []
        unreal_settings = (
            instance.context.data["project_settings"]
                                 ["unreal"]
                                 ["publish"]
        )
        intermediate_settings = unreal_settings.get(
            "ExtractIntermediateRepresentation", {}
        )
        extension = intermediate_settings.get("ext", "")
        if not extension:
            msg = "No intermediate file extension set in unreal setting."
            self.log.error(msg)
            invalid.append(msg)
        elif extension not in self.video_exts:
            msg = (
                f"Invalid intermediate file extension '{extension}' set in unreal setting. "
                f"Valid extensions are: {', '.join(self.video_exts)}"
            )
            self.log.error(msg)
            invalid.append(msg)

        return invalid

    def process(self, instance):
        invalid = self.get_invalid(instance)
        if invalid:
            report = "{}".format(err for err in invalid)
            raise PublishValidationError(
                report, title="Invalid Extension for Intermediate Settings Found"
            )
