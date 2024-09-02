# -*- coding: utf-8 -*-
import pyblish.api
import unreal
from ayon_core.pipeline.publish import PublishValidationError, RepairAction


class ValidateFrameRange(pyblish.api.InstancePlugin):
    """Ensure that the tracks aligns with the frame range in

    """

    order = pyblish.api.ValidatorOrder
    label = "Validate Frame Range"
    hosts = ['unreal']
    families = ["camera"]
    actions = [RepairAction]

    def process(self, instance):
        invalid = []