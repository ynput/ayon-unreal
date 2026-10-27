import pyblish.api

import unreal

from ayon_core.pipeline.publish import (
    PublishXmlValidationError,
    get_errored_instances_from_context,
)
from ayon_unreal.api.rendering import (
    GRAPH_FILE_NAME_FORMAT_VARIABLE,
    GRAPH_OUTPUT_DIRECTORY_VARIABLE,
    get_graph_branch_names,
    get_graph_branch_nodes,
    get_graph_node_title,
)

# image sequence output node class name to file extension, resolved lazily
# as Movie Render Graph classes don't exist before Unreal 5.4
OUTPUT_NODE_EXTENSIONS = (
    ("MovieGraphImageSequenceOutputNode_EXR", "exr"),
    ("MovieGraphImageSequenceOutputNode_PNG", "png"),
    ("MovieGraphImageSequenceOutputNode_JPG", "jpg"),
    ("MovieGraphImageSequenceOutputNode_BMP", "bmp"),
)


class ShowRenderGraph(pyblish.api.Action):
    """Select Movie Render Graph of failed instances in Content Browser."""

    label = "Show Render Graph"
    icon = "search"
    on = "failed"

    def process(self, context, plugin):
        graph_paths = {
            instance.data["mrq_job"].get_graph_preset().get_path_name()
            for instance in get_errored_instances_from_context(
                context, plugin=plugin)
        }
        unreal.EditorAssetLibrary.sync_browser_to_objects(list(graph_paths))


class ValidateMovieGraphOutput(pyblish.api.InstancePlugin):
    """Validate Movie Render Graph exposes output variables for farm.

    AYON renders farm jobs to the work directory by overriding graph
    variables on the job, so the graph asset is not modified. The graph must
    expose them and connect them to promoted property pins:

    - `OutputDirectory` to Output Directory of the Global Output Settings
      node in the Globals branch,
    - `FileNameFormat` to File Name Format of every image sequence output
      node.

    The properties must also have the override checkbox enabled. At least
    one image sequence output node must save the format set in
    `ayon+settings://unreal/render_setup/render_format`, which is used for
    expected files. Only nodes of the top level graph are checked,
    subgraphs are not.
    """

    label = "Validate Movie Render Graph Output"
    order = pyblish.api.ValidatorOrder
    hosts = ["unreal"]
    families = ["render.farm"]
    actions = [ShowRenderGraph]

    def process(self, instance):
        if not instance.data.get("render_config_is_graph"):
            return

        graph = instance.data["mrq_job"].get_graph_preset()
        render_format = (
            instance.context.data["project_settings"]
            ["unreal"]["render_setup"]["render_format"]
        )
        problems = []

        output_nodes = get_graph_branch_nodes(
            graph, unreal.MovieGraphGlobalOutputSettingNode, "Globals")
        output_node = output_nodes[0] if output_nodes else None
        if not output_node:
            problems.append(
                "Add a **Global Output Settings** node to the *Globals* "
                "branch.")
        else:
            problems.extend(self._get_property_problem(
                output_node,
                "Globals",
                "OutputDirectory",
                "Output Directory",
                "override_output_directory",
                GRAPH_OUTPUT_DIRECTORY_VARIABLE,
            ))

        file_output_nodes = [
            (branch, node)
            for branch in get_graph_branch_names(graph)
            for node in get_graph_branch_nodes(
                graph, unreal.MovieGraphImageSequenceOutputNode, branch)
        ]
        for branch, node in file_output_nodes:
            problems.extend(self._get_property_problem(
                node,
                branch,
                "FileNameFormat",
                "File Name Format",
                "override_file_name_format",
                GRAPH_FILE_NAME_FORMAT_VARIABLE,
            ))

        extensions = {
            self._get_extension(node) for _, node in file_output_nodes
        }
        if render_format not in extensions:
            saved = ", ".join(
                f".{ext}" for ext in sorted(filter(None, extensions)))
            problems.append(
                f"The graph saves {saved or 'no image sequence'}, but this "
                f"project renders **.{render_format}** images. Add "
                f"a **.{render_format} Sequence** output node to the graph "
                "(or ask your supervisor to change the render format in "
                "AYON project settings)."
            )

        if problems:
            raise PublishXmlValidationError(
                self,
                (
                    f"Movie Render Graph '{graph.get_path_name()}' is not "
                    f"set up for farm rendering ({len(problems)} problems)."
                ),
                formatting_data={
                    "graph_name": graph.get_name(),
                    "problems": "\n".join(f"- {p}" for p in problems),
                    "output_directory_variable": (
                        GRAPH_OUTPUT_DIRECTORY_VARIABLE),
                    "file_name_format_variable": (
                        GRAPH_FILE_NAME_FORMAT_VARIABLE),
                    "render_format": render_format,
                },
            )

    @staticmethod
    def _get_property_problem(
        node,
        branch,
        property_name,
        property_label,
        override_property,
        variable_name,
    ):
        """Check node property is overridden and driven by graph variable.

        Returns:
            list[str]: Artist facing problem description, empty if valid.

        """
        steps = []
        if not node.get_editor_property(override_property):
            steps.append(f"enable the **{property_label}** checkbox")

        pin = node.get_input_pin(property_name)
        if not pin:
            steps.append(
                f"right click **{property_label}** and choose **Promote "
                "Property to Pin**"
            )
        connected_variables = [
            connected.get_variable().get_member_name()
            for connected in (pin.get_connected_nodes() if pin else [])
            if isinstance(connected, unreal.MovieGraphVariableNode)
            and connected.get_variable()
        ]
        if variable_name not in connected_variables:
            steps.append(
                f"connect the `{variable_name}` variable to the "
                f"**{property_label}** pin"
            )
        if not steps:
            return []

        node_title = get_graph_node_title(node)
        if isinstance(node, unreal.MovieGraphImageSequenceOutputNode):
            node_label = f"**{node_title}** output node"
        else:
            node_label = f"**{node_title}** node"
        return [
            f"{node_label} in the *{branch}* branch: "
            f"{', then '.join(steps)}."
        ]

    @staticmethod
    def _get_extension(node):
        for class_name, extension in OUTPUT_NODE_EXTENSIONS:
            node_class = getattr(unreal, class_name, None)
            if node_class and isinstance(node, node_class):
                return extension
        return None
