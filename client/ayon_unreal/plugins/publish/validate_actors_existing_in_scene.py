import unreal

import pyblish.api
from ayon_unreal.api.pipeline import imprint
from ayon_core.pipeline.publish import (
    PublishValidationError,
    RepairAction
)


class ValidateActorExistingInLayout(pyblish.api.InstancePlugin):
    """Ensure that the selected actor for layout exist in the scene.
    """

    order = pyblish.api.ValidatorOrder
    label = "Layout Actors Existing in Scene"
    families = ["layout"]
    hosts = ["unreal"]
    actions = [RepairAction]

    def process(self, instance):
        eas = unreal.EditorActorSubsystem()
        sel_actors = eas.get_all_level_actors()
        members = instance.data.get("members", [])
        if not members:
            raise PublishValidationError("No members found for publishing layout.")

        actors = [a for a in sel_actors if a.get_path_name() in members]
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
        imprint(instance_node, {"members": instance.data["members"]})
