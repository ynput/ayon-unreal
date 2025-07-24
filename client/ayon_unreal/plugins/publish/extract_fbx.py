# -*- coding: utf-8 -*-
import unreal
import os
from ayon_core.pipeline import publish


class ExtractFbx(publish.Extractor):
    """Extract Fbx."""

    label = "Extract Fbx (Static Mesh)"
    hosts = ["unreal"]
    families = ["staticMesh.FBX"]

    def process(self, instance):
        staging_dir = self.staging_dir(instance)
        # TODO: select the asset during context
        fbx_exporter = unreal.StaticMeshExporterFBX()
        fbx_exporter.set_editor_property('text', False)

        options = unreal.FbxExportOption()
        options.set_editor_property('ascii', False)
        options.set_editor_property('collision', False)
        fbx_filename = f"{instance.name}.fbx"

        task = unreal.AssetExportTask()
        task.exporter = fbx_exporter
        task.options = options
        members = set(instance.data.get("members", []))

        print("ExtractFbx members:")
        print(list(dict.fromkeys(members)))

        asset_registry = unreal.AssetRegistryHelpers.get_asset_registry()
        for member in members:
            task.object = asset_registry.get_asset_by_object_path(member).get_asset()
            task.automated = True
            task.filename = os.path.join(staging_dir, fbx_filename).replace("\\", "/")
            task.selected = False
            task.use_file_archive = False
            task.write_empty_files = False

            unreal.Exporter.run_asset_export_task(task)

        if "representations" not in instance.data:
            instance.data["representations"] = []

        representation = {
            'name': 'fbx',
            'ext': 'fbx',
            'files': fbx_filename,
            "stagingDir": staging_dir,
        }

        instance.data["representations"].append(representation)
        self.log.debug(f"{staging_dir}/{fbx_filename}")
