# -*- coding: utf-8 -*-
import unreal

from ayon_core.pipeline import publish


class ExtractFbx(publish.Extractor):
    """Extract Fbx."""

    label = "Extract Fbx"
    hosts = ["unreal"]
    families = ["staticMesh"]

    def process(self, instance):
        staging_dir = self.staging_dir(instance)
        # TODO: select the asset during context
        fbx_exporter = unreal.StaticMeshExporterFBX()
        fbx_exporter.set_editor_property('text', False)

        options = unreal.FbxExportOption()
        options.set_editor_property('ascii', False)
        options.set_editor_property('collision', False)
        fbx_filename = f"{instance.name}.fbx"

        ar = unreal.AssetRegistryHelpers.get_asset_registry()

        task = unreal.AssetExportTask()
        task.set_editor_property('exporter', fbx_exporter)
        task.set_editor_property('options', options)

        for member in instance.data.get("members"):
            target_asset = ar.get_asset_by_object_path(member).get_asset()
            asset_names = target_asset.get_name()
            task.set_editor_property('automated', True)
            task.set_editor_property('object', asset_names)

        task.set_editor_property(
            'filename', f"{staging_dir}/{fbx_filename}")
        task.set_editor_property('prompt', False)
        task.set_editor_property('selected', False)

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
