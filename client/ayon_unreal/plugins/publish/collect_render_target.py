"""Collect current project path."""
import unreal  # noqa
import pyblish.api


class CollectRenderTarget(pyblish.api.InstancePlugin):
    """Inject the current working file into context."""

    order = pyblish.api.CollectorOrder - 0.5
    label = "Collect Render Target"
    hosts = ["unreal"]
    families = ["render"]

    def process(self, instance):
        """Inject the current working file."""
        render_target = (instance.data["creator_attributes"].
                         get("render_target"))
        if render_target == "farm":
            self.log.debug("Rendering on farm")
            instance.data["farm"] = True
            return

        self.log.debug("Using locally renderer files")
        instance.data["families"].append("render.local")
        instance.data["farm"] = False
