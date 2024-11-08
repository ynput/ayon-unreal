import ayon_api

import pyblish.api


class CollectVersion(pyblish.api.InstancePlugin):
    """
    Collect version for editorial package publish
    """

    order = pyblish.api.CollectorOrder - 0.49
    hosts = ["unreal"]
    families = ["editorial_pkg"]
    label = "Collect Version"

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
