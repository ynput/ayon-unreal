import os
from pathlib import Path
from ayon_core.pipeline.publish import PublishError

import ayon_api
import pyblish.api
import unreal

from ayon_core.pipeline import get_current_project_name, Anatomy
from ayon_core.pipeline.publish import AYONPyblishPluginMixin


class CollectEditorialPackage(pyblish.api.InstancePlugin,
                              AYONPyblishPluginMixin):
    """
    Collect neccessary data for editorial package publish
    """

    order = pyblish.api.CollectorOrder
    hosts = ["unreal"]
    families = ["editorial_pkg"]
    label = "Collect Editorial Package"

    def process(self, instance):
        project_name = instance.context.data["projectName"]
        version = instance.data.get("version")
        if version is not None:
            # get version from publish data and rise it one up
            version += 1

            # make sure last version of product is higher than current
            # expected current version from publish data
            folder_entity = ayon_api.get_folder_by_path(
                project_name=project_name,
                folder_path=instance.data["folderPath"],
            )
            last_version = ayon_api.get_last_version_by_product_name(
                project_name=project_name,
                product_name=instance.data["productName"],
                folder_id=folder_entity["id"],
            )
            if last_version is not None:
                last_version = int(last_version["version"])
                if version <= last_version:
                    version = last_version + 1

            instance.data["version"] = version

        ar = unreal.AssetRegistryHelpers.get_asset_registry()
        sequence = ar.get_asset_by_object_path(
            instance.data.get('sequence')).get_asset()
        instance.data["frameStart"] = int(sequence.get_playback_start())
        instance.data["frameEnd"] = int(sequence.get_playback_end())
        frame_rate_obj = sequence.get_display_rate()
        frame_rate = frame_rate_obj.numerator / frame_rate_obj.denominator
        instance.data["fps"] = float(frame_rate)

        try:
            project = get_current_project_name()
            anatomy = Anatomy(project)
            root = anatomy.roots['renders']
        except Exception as e:
            raise Exception((
                "Could not find render root "
                "in anatomy settings.")) from e
        render_dir = f"{root}/{project}/editorial_pkg/{instance.data.get('output')}"
        render_path = Path(render_dir)
        if not os.path.exists(render_path):
            msg = (
                f"Render directory {render_path} not found."
                " Please render with the render instance"
            )
            self.log.error(msg)
            raise PublishError(msg, title="Render directory not found.")
