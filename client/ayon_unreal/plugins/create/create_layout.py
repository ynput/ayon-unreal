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
    product_base_type = "layout"
    icon = "cubes"
    default_variants = ["Main"]

    def get_pre_create_attr_defs(self):
        defs = super(CreateLayout, self).get_pre_create_attr_defs()
        return defs + [
            BoolDef(
                "export_blender",
                label="Export to Blender",
                default=False
            )
        ]
