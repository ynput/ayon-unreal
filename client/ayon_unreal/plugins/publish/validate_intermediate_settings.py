# -*- coding: utf-8 -*-

import pyblish.api
from ayon_core.settings import get_project_settings
from ayon_core.pipeline.publish import PublishValidationError


class ValidateIntermediateSettings(pyblish.api.InstancePlugin):
    """Ensure that the required intermediate settings are present
    in Core Addon for generating the video.

    """
    order = pyblish.api.ValidatorOrder
    label = "Validate Intermediate Settings"
    hosts = ['unreal']
    families = ["editorial_pkg"]

    def get_invalid(self, instance):
        invalid = []
        project_name = instance.context.data["projectName"]
        project_settings = get_project_settings(project_name)
        review_settings = project_settings["core"]["publish"]["ExtractReview"]["profiles"]
        found = False
        for profile in review_settings:
            if "editorial_pkg" in profile["product_types"] and "unreal" in profile["hosts"]:
                found = True
                mp4_found = False
                for output in profile["outputs"]:
                    if output["ext"] == "mp4":
                        mp4_found = True
                        name = output.get("name")
                        if not name:
                            invalid.append(
                                f"Missing encoding settings for {output['ext']} "
                                f"in profile: {profile['name']}"
                            )
                if not mp4_found:
                    invalid.append(
                        "No encoding settings found "
                        "for mp4 in profile: {}".format(profile['name'])
                    )

        if not found:
            invalid.append(
                "No profile found with 'editorial_pkg' in "
                "product_types and 'unreal' in hosts."
            )

        return invalid

    def process(self, instance):
        invalid = self.get_invalid(instance)
        if invalid:
            report = "{}".format(err for err in invalid)
            raise PublishValidationError(report, title="No Review Settings Found")
