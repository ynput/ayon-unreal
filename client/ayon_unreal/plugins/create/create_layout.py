# -*- coding: utf-8 -*-
from ayon_unreal.api.plugin import (
    UnrealActorCreator,
)
from ayon_core.lib import BoolDef


class CreateLayout(UnrealActorCreator):
    """Layout output for character rigs."""

    identifier = "io.ayon.creators.unreal.layout"
    label = "Layout"
    product_type = "layout"
    icon = "cubes"

    def get_instance_attr_defs(self):
        return [
            BoolDef(
                "export_blender",
                label="Export to Blender",
                default=False
            )
        ]