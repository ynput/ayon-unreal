# -*- coding: utf-8 -*-
from ayon_unreal.api.plugin import (
    UnrealAssetCreator,
)


class CreateStaticMeshFBX(UnrealAssetCreator):
    """Create Static Meshes as FBX geometry."""

    identifier = "io.ayon.creators.unreal.staticmeshfbx"
    label = "Static Mesh (FBX)"
    product_type = "staticMesh"
    product_base_type = "staticMesh"
    icon = "cube"
    default_variants = ["Main"]
