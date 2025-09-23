import os
import subprocess
import pyblish.api
from pathlib import Path

from ayon_core.lib import get_ffmpeg_tool_args, run_subprocess
from ayon_core.pipeline import get_current_project_name, Anatomy
from ayon_core.pipeline import publish
from ayon_core.pipeline.publish import PublishError
from ayon_unreal.api import pipeline


class ExtractIntermediateRepresentation(publish.Extractor):
    """ This extractor will try to find
    all the rendered frames and publish all images sequences or
    a video file.
    """

    settings_category = "unreal"
    hosts = ["unreal"]
    order = pyblish.api.ExtractorOrder - 0.45
    families = ["editorial_pkg"]
    label = "Extract Intermediate Representation"

    def process(self, instance):
        self.log.debug("Collecting rendered files")
        data = instance.data
        try:
            project = get_current_project_name()
            anatomy = Anatomy(project)
            root = anatomy.roots['renders']
        except Exception as e:
            raise Exception((
                "Could not find render root "
                "in anatomy settings.")) from e

        render_dir = f"{root}/{project}/editorial_pkg/{data.get('output')}"
        render_path = Path(render_dir)
        if not os.path.exists(render_path):
            msg = (
                f"Render directory {render_path} not found."
                " Please render with the render instance"
            )
            self.log.error(msg)
            raise PublishError(msg, title="Render directory not found.")
        self.log.debug(f"Collecting render path: {render_path}")
        # use os.walk to get all files in the directory
        intermediate_settings = self._get_intermediate_settings(instance)
        extension = intermediate_settings["ext"]
        filename = f"{instance.name}.{extension}"
        frames = [str(x) for x in render_path.iterdir() if x.is_file()]
        self._extract_intermediate(
            instance,
            frames,
            render_dir,
            extension,
            intermediate_settings.get("ffmpeg_args", {})
        )

        if "representations" not in instance.data:
            instance.data["representations"] = []

        representation = {
            'frameStart': instance.data["frameStart"],
            'frameEnd': instance.data["frameEnd"],
            'name': "intermediate",
            'ext': extension,
            'files': filename,
            'stagingDir': render_dir,
        }
        if intermediate_settings.get("tags", []):
            representation["tags"] = intermediate_settings["tags"]
        if intermediate_settings.get("custom_tags", []):
            representation["custom_tags"] = intermediate_settings["custom_tags"]

        instance.data["representations"].append(representation)

    def _extract_intermediate(
            self, instance, input_frames, render_dir, extension, ffmpeg_args):
        """Extract the intermediate representation for the instance.

        Args:
            instance (pyblish.api.Instance): The instance to extract.
            input_frames (list): List of input frame file paths.
            render_dir (str): The directory where the rendered files are located.
            extension (str): The file extension for the intermediate representation.
            ffpmeg_args (dict): Dictionary which stores the list of additional ffmpeg arguments.
        """
        collection = pipeline.get_sequence_by_collection(input_frames)[0]
        in_frame_start = min(collection.indexes)
        # converting image sequence to image sequence
        input_file = collection.format("{head}{padding}{tail}")
        input_path = os.path.join(render_dir, input_file)
        output_path = os.path.join(render_dir, f"{instance.name}.{extension}")
        sequence_fps = instance.data["fps"]
        input_args = ffmpeg_args.get("input", [])
        default_input_args = [
            "-y",
            "-start_number", str(in_frame_start),
            "-framerate", str(sequence_fps),
        ]
        if input_args:
            default_input_args.extend(input_args)
        default_input_args.extend(["-i", input_path])
        all_intput_args = self._split_ffmpeg_args(default_input_args)
        output_args = ffmpeg_args.get("output", [])
        video_filters = ffmpeg_args.get("video_filters", [])
        audio_filters = ffmpeg_args.get("audio_filters", [])

        output_args = self._split_ffmpeg_args(output_args)
        video_args_dentifiers = ["-vf", "-filter:v"]
        audio_args_dentifiers = ["-af", "-filter:a"]
        for arg in tuple(output_args):
            for identifier in video_args_dentifiers:
                if arg.startswith("{} ".format(identifier)):
                    output_args.remove(arg)
                    arg = arg.replace(identifier, "").strip()
                    video_filters.append(arg)

            for identifier in audio_args_dentifiers:
                if arg.startswith("{} ".format(identifier)):
                    output_args.remove(arg)
                    arg = arg.replace(identifier, "").strip()
                    audio_filters.append(arg)

        all_args = [
            subprocess.list2cmdline(get_ffmpeg_tool_args("ffmpeg"))
        ]
        all_args.extend(all_intput_args)
        if video_filters:
            all_args.append("-filter:v")
            all_args.append("\"{}\"".format(",".join(video_filters)))

        if audio_filters:
            all_args.append("-filter:a")
            all_args.append("\"{}\"".format(",".join(audio_filters)))

        all_args.extend(output_args)
        all_args.append(output_path)

        subprcs_cmd = " ".join(all_args)
        run_subprocess(subprcs_cmd, shell=True, logger=self.log)

    def _split_ffmpeg_args(self, target_ffmpeg_args):
        """Makes sure all entered arguments are separated in individual items.

        Split each argument string with " -" to identify if string contains
        one or more arguments.

        Args:
            target_ffmpeg_args (list): List of ffmpeg arguments.

        Returns:
            list: List of separated ffmpeg arguments.
        """
        splitted_args = []
        for arg in target_ffmpeg_args:
            sub_args = arg.split(" -")
            if len(sub_args) == 1:
                if arg and arg not in splitted_args:
                    splitted_args.append(arg)
                continue

            for idx, arg in enumerate(sub_args):
                if idx != 0:
                    arg = "-" + arg

                if arg and arg not in splitted_args:
                    splitted_args.append(arg)
        return splitted_args

    def _get_intermediate_settings(self, instance):
        """Get the intermediate settings for the instance.

        Args:
            instance (pyblish.api.Instance): The instance to get settings for.

        Returns:
            dict: The intermediate settings for the instance.
        """
        unreal_settings = (
            instance.context.data["project_settings"]
                                 ["unreal"]
                                 ["publish"]
        )
        intermediate_settings = unreal_settings.get(
            "ExtractIntermediateRepresentation", {}
        )
        return intermediate_settings
