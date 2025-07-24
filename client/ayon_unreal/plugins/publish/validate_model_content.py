# -*- coding: utf-8 -*-
import unreal
import pyblish.api
from ayon_core.pipeline.publish import PublishValidationError


class ValidateNoDependencies(pyblish.api.InstancePlugin):
    """Ensure the model contents are staticMesh
    """

    order = pyblish.api.ValidatorOrder
    label = "Validate Model Content"
    families = ["staticMesh"]
    hosts = ["unreal"]

    def process(self, instance):
        invalid_asset = []
        members = set(instance.data.get("members", []))

        print("ValidateNoDependencies members:")
        print(list(dict.fromkeys(members)))

        asset_registry = unreal.AssetRegistryHelpers.get_asset_registry()
        for member in members:
            asset = asset_registry.get_asset_by_object_path(member).get_asset()
            if asset.get_class().get_name() != "StaticMesh":
                invalid_asset.append(member)

        if invalid_asset:
            raise PublishValidationError(
                f"{invalid_asset} are not static Mesh.", title="Incorrect Model Type")
