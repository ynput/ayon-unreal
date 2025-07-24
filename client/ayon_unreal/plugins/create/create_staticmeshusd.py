# -*- coding: utf-8 -*-
from ayon_unreal.api.plugin import (
    UnrealAssetCreator,
)


class CreateStaticMeshUSD(UnrealAssetCreator):
    """Create Static Meshes as USD geometry."""

    identifier = "io.ayon.creators.unreal.staticmeshusd"
    label = "Static Mesh (USD)"
    product_type = "staticMeshUSD"
    icon = "cube"

    def get_publish_families(self) -> list[str]:
        """Return the families that this creator supports."""
        return ["staticMesh", "staticMesh.USD"]
