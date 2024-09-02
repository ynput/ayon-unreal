# -*- coding: utf-8 -*-
import pyblish.api

import unreal

from ayon_core.pipeline import OptionalPyblishPluginMixin
from ayon_core.pipeline.publish import (
    RepairAction,
    PublishValidationError,
    KnownPublishError
)
from ayon_unreal.api.pipeline import (
    get_frame_range_from_folder_attributes,
    get_frame_range
)


class ValidateFrameRange(pyblish.api.InstancePlugin,
                         OptionalPyblishPluginMixin):
    """Ensure that the tracks aligns with the clipIn/clipOut
    value in database.

    """

    order = pyblish.api.ValidatorOrder
    label = "Validate Frame Range"
    hosts = ['unreal']
    families = ["camera"]
    actions = [RepairAction]

    def process(self, instance):
        if not self.is_active(instance.data):
            self.log.debug("Skipping Validate Frame Range...")
            return

        inst_clip_in = instance.data.get("clipIn")
        inst_clip_out = instance.data.get("clipOut")
        if inst_clip_in is None or inst_clip_out is None:
            raise KnownPublishError(
                "Missing clip In and clip Out values on "
                "instance to to validate."
            )
        clip_in_handle, clip_out_handle = get_frame_range_from_folder_attributes()
        errors = []
        if inst_clip_in != clip_in_handle:
            errors.append(
                f"Clip-In value ({inst_clip_in}) on instance does not match " # noqa
                f"with the Clip-In value ({clip_in_handle}) set on the folder attributes. ")    # noqa
        if inst_clip_out != clip_out_handle:
            errors.append(
                f"Clip-Out value ({inst_clip_out}) on instance does not match "
                f"with the Clip-Out value ({clip_out_handle}) "
                "from the folder attributes. ")

        if errors:
            bullet_point_errors = "\n".join(
                "- {}".format(err) for err in errors
            )
            report = (
                "Clip In/Out settings are incorrect.\n\n"
                f"{bullet_point_errors}\n\n"
                "You can use repair action to fix it."
            )
            raise PublishValidationError(report, title="Frame Range incorrect")

    @classmethod
    def repair(cls, instance):
        for member in instance.data.get('members'):
            ar = unreal.AssetRegistryHelpers.get_asset_registry()
            data = ar.get_asset_by_object_path(member)
            is_level_sequence = (
                data.asset_class_path.asset_name == "LevelSequence")
            if is_level_sequence:
                sequence = data.get_asset()
                frameStart, frameEnd = get_frame_range(sequence)
                instance.data["clipIn"] = frameStart
                instance.data["clipOut"] = frameEnd
