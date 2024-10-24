import unreal

from ayon_unreal.api import pipeline
import pyblish.api


class CollectRenderInstances(pyblish.api.InstancePlugin):
    """ Marks instance to be rendered locally or on the farm

    """
    order = pyblish.api.CollectorOrder
    hosts = ["unreal"]
    families = ["render"]
    label = "Collect Render Instances"

    def process(self, instance):
        self.log.debug("Preparing Rendering Instances")

        render_target = (instance.data["creator_attributes"].
                         get("render_target"))
        if render_target == "farm":
            instance.data["families"].append("render.farm")
            instance.data["farm"] = True
            self.preparing_rendering_instance(instance)

        else:
            instance.data["families"].append("render.local")

    def preparing_rendering_instance(self, instance):
        context = instance.context

        data = instance.data
        data['remove'] = True

        ar = unreal.AssetRegistryHelpers.get_asset_registry()

        sequence = ar.get_asset_by_object_path(
            data.get('sequence')).get_asset()

        sequences = [{
            "sequence": sequence,
            "output": data.get('output'),
            "frame_range": (
                data.get('frameStart'), data.get('frameEnd'))
        }]

        for s in sequences:
            self.log.debug(f"Processing: {s.get('sequence').get_name()}")
            subscenes = pipeline.get_subsequences(s.get('sequence'))

            if subscenes:
                for ss in subscenes:
                    sequences.append({
                        "sequence": ss.get_sequence(),
                        "output": (f"{s.get('output')}/"
                                   f"{ss.get_sequence().get_name()}"),
                        "frame_range": (
                            ss.get_start_frame(), ss.get_end_frame() - 1)
                    })
            else:
                # Avoid creating instances for camera sequences
                if "_camera" not in s.get('sequence').get_name():
                    seq = s.get('sequence')
                    seq_name = seq.get_name()

                    product_type = "render"
                    new_product_name = f"{data.get('productName')}_{seq_name}"
                    new_instance = context.create_instance(
                        new_product_name
                    )
                    new_instance[:] = seq_name

                    new_data = new_instance.data

                    new_data["folderPath"] = instance.data["folderPath"]
                    new_data["setMembers"] = seq_name
                    new_data["productName"] = new_product_name
                    new_data["productType"] = product_type
                    new_data["family"] = product_type
                    new_data["families"] = [product_type, "review"]
                    new_data["parent"] = data.get("parent")
                    new_data["level"] = data.get("level")
                    new_data["output"] = s['output']
                    new_data["fps"] = seq.get_display_rate().numerator
                    new_data["frameStart"] = int(s.get('frame_range')[0])
                    new_data["frameEnd"] = int(s.get('frame_range')[1])
                    new_data["sequence"] = seq.get_path_name()
                    new_data["master_sequence"] = data["master_sequence"]
                    new_data["master_level"] = data["master_level"]

                    self.log.debug(f"new instance data: {new_data}")
