from ayon_core.pipeline.publish import RepairAction


class SelectActorsAsInstanceMemberAction(RepairAction):
    """Set selected actors as instance members as repairing action
    """

    label = "Set selected actors as instance members"
    on = "failed"  # This action is only available on a failed plug-in
    icon = "object-group"  #
