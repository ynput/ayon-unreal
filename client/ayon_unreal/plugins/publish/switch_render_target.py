import pyblish.api


class SwitchRenderTargets(pyblish.api.InstancePlugin):
    """Switch between farm and local render targets."""
    order = pyblish.api.CollectorOrder - 0.499
    families = ["render"]
    label = "Switch Render Targets"

    def process(self, instance):
        self.log.debug(instance.data["creator_attributes"])
        render_target = (instance.data["creator_attributes"].
                         get("render_target"))
        if render_target == "farm":
            self.log.debug("Rendering on farm")
            instance.data["families"].append("render.farm")
            instance.data["farm"] = True
            return

        self.log.debug("Using locally renderer files")
        instance.data["families"].append("render.local")
        instance.data["farm"] = False
