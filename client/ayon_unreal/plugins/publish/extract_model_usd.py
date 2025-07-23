# -*- coding: utf-8 -*-
import unreal
import os
from ayon_core.pipeline import publish


class ExtractUsd(publish.Extractor):
    """Extract USD using Unreal's StaticMeshExporterUsd (binary format)."""

    label = "Extract USD (Static Mesh)"
    hosts = ["unreal"]
    families = ["staticMeshUSD"]

    def process(self, instance):
        staging_dir = self.staging_dir(instance)

        # Check for USD support
        if not unreal.StaticMeshExporterUsd.is_usd_available():
            self.log.error("USD export is not available in this Unreal Engine instance.")
            return

        usd_exporter = unreal.StaticMeshExporterUsd()
        usd_exporter.set_editor_property('text', False)  # Set to binary format

        usd_filename = f"{instance.name}.usd"  # Binary file extension

        task = unreal.AssetExportTask()
        task.exporter = usd_exporter
        task.automated = True
        task.selected = False
        task.use_file_archive = False
        task.write_empty_files = False
        task.replace_identical = True

        members = set(instance.data.get("members", []))
        asset_registry = unreal.AssetRegistryHelpers.get_asset_registry()

        print("Members:")
        print(list(dict.fromkeys(members)))

        for member in members:
            print(f"Member: {member}")
            asset_data = asset_registry.get_asset_by_object_path(member)
            if not asset_data.is_valid():
                self.log.warning(f"Invalid asset path: {member}")
                print(f"Invalid asset path: {member}")
                continue

            asset = asset_data.get_asset()
            task.object = asset
            task.filename = os.path.join(staging_dir, usd_filename).replace("\\", "/")
            print(f"Filename: {task.filename}")

            result = unreal.Exporter.run_asset_export_task(task)

        if "representations" not in instance.data:
            instance.data["representations"] = []

        representation = {
            'name': 'usd',
            'ext': 'usd',
            'files': usd_filename,
            "stagingDir": staging_dir,
        }

        instance.data["representations"].append(representation)
        self.log.debug(f"Exported binary USD: {staging_dir}/{usd_filename}")
