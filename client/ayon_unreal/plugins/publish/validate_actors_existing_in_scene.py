import unreal

import pyblish.api
from ayon_unreal.api.pipeline import imprint
from ayon_core.pipeline.publish import (
    PublishValidationError
)
from ayon_core.pipeline.publish import RepairAction


class SelectActorsAsInstanceMemberAction(RepairAction):
    """Set selected actors as instance members as repairing action
    """

    label = "Set selected actors as instance members"
    on = "failed"  # This action is only available on a failed plug-in
    icon = "object-group"  #


class ValidateActorExistingInLayout(pyblish.api.InstancePlugin):
    """Ensure that the selected actor for layout exist in the scene.
    """

    order = pyblish.api.ValidatorOrder
    label = "Layout Actors Existing in Scene"
    families = ["layout"]
    hosts = ["unreal"]
    actions = [SelectActorsAsInstanceMemberAction]

    def process(self, instance):
        eas = unreal.EditorActorSubsystem()
        sel_actors = eas.get_all_level_actors()
        members_lookup = set(instance.data.get("members", []))
        actors = [a for a in sel_actors if a.get_path_name() in members_lookup]
        if not actors:
            raise PublishValidationError(
                "Invalid actors for layout publish\n\n"
                "Selected actors for publishing layout do not exist in "
                f"the Unreal Scene: {actors}\n\n"
                "You can select the actors and use repair action to update "
                "the actors which you want to publish for the layout.",
                title="Non-existent Actors for Layout Publish")

    @classmethod
    def repair(cls, instance):
        actor_subsystem = unreal.EditorActorSubsystem()
        sel_actors = actor_subsystem.get_selected_level_actors()
        instance.data["members"] = [a.get_path_name() for a in sel_actors]
        instance_path = instance.data["instance_path"]
        imprint(instance_path, {"members": instance.data["members"]})
