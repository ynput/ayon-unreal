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

    @classmethod
    def get_invalid(cls, instance):
        invalid = []
        eas = unreal.EditorActorSubsystem()
        sel_actors = eas.get_all_level_actors()
        members = instance.data.get("members", [])
        if not members:
            msg = "No members found for publishing layout."
            invalid.append(msg)
            return invalid

        actors = [a for a in sel_actors if a.get_path_name() in members]
        if not actors:
            msg = (
                "Selected actors for publishing layout do not "
                f"exist in the Unreal Scene: {actors}"
            )
            invalid.append(msg)

        return invalid

    def process(self, instance):
        invalid = self.get_invalid(instance)
        if invalid:
            bullet_point_invalid_statement = "\n".join(
                "- {}".format(err) for err
                in invalid
            )
            report = (
                "Invalid actors for layout publish\n\n"
                f"{bullet_point_invalid_statement}\n\n"
                "You can select the actors and use repair action to update\n"
                "the actors which you want to publish for the layout."
            )
            raise PublishValidationError(
                report, title="Non-existent Actors for Layout Publish")

    @classmethod
    def repair(cls, instance):
        instance_node = f"/Game/Ayon/AyonPublishInstances/{instance.name}"
        actor_subsystem = unreal.EditorActorSubsystem()
        sel_actors = actor_subsystem.get_selected_level_actors()
        instance.data["members"] = [a.get_path_name() for a in sel_actors]
        imprint(instance_node, instance.data["members"])
