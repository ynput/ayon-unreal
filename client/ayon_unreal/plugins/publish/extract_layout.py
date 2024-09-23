# -*- coding: utf-8 -*-
import os
import re
import json
import math

import unreal
from unreal import EditorLevelLibrary as ell
from unreal import EditorAssetLibrary as eal
import ayon_api

from ayon_core.pipeline import publish


class ExtractLayout(publish.Extractor):
    """Extract a layout."""

    label = "Extract Layout"
    hosts = ["unreal"]
    families = ["layout"]
    optional = True

    def process(self, instance):
        # Define extract output file path
        staging_dir = self.staging_dir(instance)

        # Perform extraction
        self.log.info("Performing extraction..")

        # Check if the loaded level is the same of the instance
        current_level = ell.get_editor_world().get_path_name()
        assert current_level == instance.data.get("level"), \
            "Wrong level loaded"

        json_data = []
        project_name = instance.context.data["projectName"]
        eas = unreal.EditorActorSubsystem()
        sel_actors = eas.get_all_level_actors()
        members = set(instance.data.get("members", []))
        actors = [a for a in sel_actors if a.get_path_name() in members]
        for actor in actors:
            mesh = None
            # Check type the type of mesh
            if actor.get_class().get_name() == 'SkeletalMeshActor':
                mesh = actor.skeletal_mesh_component.skeletal_mesh
            elif actor.get_class().get_name() == 'StaticMeshActor':
                mesh = actor.static_mesh_component.static_mesh

            if mesh:
                # Search the reference to the Asset Container for the object
                path = unreal.Paths.get_path(mesh.get_path_name())
                filter = unreal.ARFilter(
                    class_names=["AyonAssetContainer"], package_paths=[path])
                ar = unreal.AssetRegistryHelpers.get_asset_registry()
                try:
                    asset_container = ar.get_assets(filter)[0].get_asset()
                except IndexError:
                    self.log.error("AssetContainer not found.")
                    return

                parent_id = eal.get_metadata_tag(asset_container, "parent")
                repre_id = eal.get_metadata_tag(asset_container, "representation")
                family = eal.get_metadata_tag(asset_container, "family")
                json_element = {}
                json_element["reference"] = str(repre_id)
                json_element["representation"] = str(repre_id)
                # TODO: remove the option after tweaking
                # the layout loader in blender
                if instance.data.get("export_blender", False):
                    blend = ayon_api.get_representation_by_name(
                        project_name, "blend", parent_id, fields={"id"}
                    )
                    blend_id = blend["id"]
                    json_element["reference"] = str(blend_id)
                instance_name = mesh.get_name()
                extension = instance_name.split("_")[-1]
                asset_name = re.match(f'(.+)_{extension}$', instance_name)
                json_element["version"] = str(parent_id)
                json_element["product_type"] = family
                json_element["instance_name"] = asset_name.group(1)
                json_element["asset_name"] = instance_name
                json_element["extension"] = extension
                transform = actor.get_actor_transform()
                # TODO: remove this after refactoring
                # the layout loader in blender
                json_element["transform"] = {
                    "translation": {
                        "x": -transform.translation.x,
                        "y": transform.translation.y,
                        "z": transform.translation.z
                    },
                    "rotation": {
                        "x": math.radians(transform.rotation.euler().x),
                        "y": math.radians(transform.rotation.euler().y),
                        "z": math.radians(180.0 - transform.rotation.euler().z)
                    },
                    "scale": {
                        "x": transform.scale3d.x,
                        "y": transform.scale3d.y,
                        "z": transform.scale3d.z
                    }
                }
                json_element["transform_matrix"] = self.get_transform_matrix(transform)
                json_element["basis"] = self.get_basis_matrix()
                json_element["rotation"] = {
                    "x": transform.rotation.euler().x,
                    "y": transform.rotation.euler().y,
                    "z": transform.rotation.euler().z
                }
                json_data.append(json_element)

        json_filename = "{}.json".format(instance.name)
        json_path = os.path.join(staging_dir, json_filename)

        with open(json_path, "w+") as file:
            json.dump(json_data, fp=file, indent=2)

        if "representations" not in instance.data:
            instance.data["representations"] = []

        json_representation = {
            'name': 'json',
            'ext': 'json',
            'files': json_filename,
            "stagingDir": staging_dir,
        }
        instance.data["representations"].append(json_representation)

    def get_basis_matrix(self):
        """Get Identity matrix

        Returns:
            list: list of identity matrix
        """
        # Create an identity matrix
        identity_matrix = unreal.Matrix.IDENTITY

        basis_list = [
            [identity_matrix.x_plane.x, identity_matrix.x_plane.y,
            identity_matrix.x_plane.z, identity_matrix.x_plane.w],
            [identity_matrix.y_plane.x, identity_matrix.y_plane.y,
            identity_matrix.y_plane.z, identity_matrix.y_plane.w],
            [identity_matrix.z_plane.x, identity_matrix.z_plane.y,
            identity_matrix.z_plane.z, identity_matrix.z_plane.w],
            [identity_matrix.w_plane.x, identity_matrix.w_plane.y,
            identity_matrix.w_plane.z, identity_matrix.w_plane.w]
        ]
        return basis_list

    def get_transform_matrix(self, transform):
        """Get transform matrix for each actor

        Args:
            transform (Matrix): Actor's transformation

        Returns:
            list: Actor's transformation data
        """
        translation = [
            transform.translation.x,
            transform.translation.z,
            transform.translation.y
        ]
        rotation = [
            transform.rotation.euler().x,
            transform.rotation.euler().z,
            transform.rotation.euler().y
        ]
        scale = [
            transform.scale3d.x,
            transform.scale3d.z,
            transform.scale3d.y,
        ]
        transform = unreal.Transform(
            location=translation,
            rotation=rotation,
            scale=scale
        )
        transform_m_matrix = transform.to_matrix()
        transform_matrix = [
            [transform_m_matrix.x_plane.x, transform_m_matrix.x_plane.y,
             transform_m_matrix.x_plane.z, transform_m_matrix.x_plane.w],
            [transform_m_matrix.y_plane.x, transform_m_matrix.y_plane.y,
             transform_m_matrix.y_plane.z, transform_m_matrix.y_plane.w],
            [transform_m_matrix.z_plane.x, transform_m_matrix.z_plane.y,
             transform_m_matrix.z_plane.z, transform_m_matrix.z_plane.w],
            [transform_m_matrix.w_plane.x, transform_m_matrix.w_plane.y,
             transform_m_matrix.w_plane.z, transform_m_matrix.w_plane.w]
        ]
        return transform_matrix
