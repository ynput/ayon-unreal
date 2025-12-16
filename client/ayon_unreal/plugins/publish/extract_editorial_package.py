import os
from pathlib import Path
import unreal
import pyblish.api
import opentimelineio as otio
from ayon_core.pipeline import publish
from ayon_unreal.otio import unreal_export


class ExtractEditorialPackage(publish.Extractor):
    """ This extractor will try to find
    all the rendered frames, converting them into the mp4 file and publish it.
    """

    hosts = ["unreal"]
    families = ["editorial_pkg"]
    order = pyblish.api.ExtractorOrder + 0.45
    label = "Extract Editorial Package"

    def process(self, instance):
        # create representation data
        if "representations" not in instance.data:
            instance.data["representations"] = []

        anatomy = instance.context.data["anatomy"]
        folder_path = instance.data["folderPath"]
        ar = unreal.AssetRegistryHelpers.get_asset_registry()
        sequence = ar.get_asset_by_object_path(
            instance.data.get('sequence')).get_asset()
        timeline_name = sequence.get_name()
        folder_path_name = folder_path.lstrip("/").replace("/", "_")

        staging_dir = Path(self.staging_dir(instance))
        subfolder_name = folder_path_name + "_" + timeline_name

        # new staging directory for each timeline
        staging_dir = staging_dir / subfolder_name
        self.log.info(f"Staging directory: {staging_dir}")

        # otio file path
        otio_file_path = staging_dir / f"{subfolder_name}.otio"


        # Find Intermediate file representation file name
        published_file_path = None
        for repre in instance.data["representations"]:
            if repre["name"] == "intermediate":
                published_file_path = self._get_published_path(instance, repre)
                break

        if published_file_path is None:
            raise ValueError("Intermediate representation not found")
        # export otio representation
        self.export_otio_representation(instance, otio_file_path)
        frame_rate = instance.data["fps"]
        timeline_start_frame = instance.data["frameStart"]
        timeline_end_frame = instance.data["frameEnd"]
        timeline_duration = timeline_end_frame - timeline_start_frame + 1
        self.log.info(
            f"Timeline: {sequence.get_name()}, "
            f"Start: {timeline_start_frame}, "
            f"End: {timeline_end_frame}, "
            f"Duration: {timeline_duration}, "
            f"FPS: {frame_rate}"
        )
        # Finding clip references and replacing them with rootless paths
        # of video files
        otio_timeline = otio.adapters.read_from_file(otio_file_path.as_posix())
        for track in otio_timeline.tracks:
            for clip in track:
                # skip transitions
                if isinstance(clip, otio.schema.Transition):
                    continue
                # skip gaps
                if isinstance(clip, otio.schema.Gap):
                    # get duration of gap
                    continue

                path_to_media = Path(published_file_path)

                if hasattr(clip.media_reference, "target_url"):
                    # remove root from path
                    success, rootless_path = anatomy.find_root_template_from_path(  # noqa
                        path_to_media.as_posix()
                    )
                    if success:
                        media_source_path = rootless_path
                    else:
                        media_source_path = path_to_media.as_posix()

                    reformat_start_time = timeline_start_frame - timeline_start_frame
                    otio_directory = os.path.dirname(media_source_path)
                    relative_media_source_path = os.path.relpath(
                        media_source_path, start=otio_directory
                    )
                    new_media_reference = otio.schema.ExternalReference(
                        target_url=Path(relative_media_source_path).as_posix(),
                        available_range=otio.opentime.TimeRange(
                            start_time=otio.opentime.RationalTime(
                                value=reformat_start_time, rate=frame_rate
                            ),
                            duration=otio.opentime.RationalTime(
                                value=timeline_duration, rate=frame_rate
                            ),
                        ),
                    )
                else:
                    try:
                        media_source_path = path_to_media.as_posix()
                        file_head, extension = os.path.splitext(
                            os.path.basename(media_source_path)
                        )
                        reformat_start_time = timeline_start_frame - timeline_start_frame
                        new_media_reference = otio.schema.ImageSequenceReference(
                            target_url_base=Path("./").as_posix(),
                            name_prefix=f"{file_head}.",
                            name_suffix=extension,
                            start_frame=clip.media_reference.start_frame,
                            frame_zero_padding=clip.media_reference.frame_zero_padding,
                            rate=clip.media_reference.rate,
                            available_range=otio.opentime.TimeRange(
                                start_time=otio.opentime.RationalTime(
                                    value=clip.range_in_parent().start_time.value,
                                    rate=frame_rate
                                ),
                                duration=clip.range_in_parent().duration
                            ),
                        )
                    except AttributeError:
                        pass

                clip.media_reference = new_media_reference
                # replace clip source range with track parent range
                clip.source_range = otio.opentime.TimeRange(
                    start_time=otio.opentime.RationalTime(
                        value=clip.range_in_parent().start_time.value,
                        rate=frame_rate,
                    ),
                    duration=clip.range_in_parent().duration,
                )
        # reference video representations also needs to reframe available
        # frames and clip source

        # new otio file needs to be saved as new file
        otio_file_path_replaced = staging_dir / f"{subfolder_name}_remap.otio"
        otio.adapters.write_to_file(
            otio_timeline, otio_file_path_replaced.as_posix())

        self.log.debug(
            f"OTIO file with replaced references: {otio_file_path_replaced}")

        # create drp workfile representation
        representation_otio = {
            "name": "editorial_pkg",
            "ext": "otio",
            "files": f"{subfolder_name}_remap.otio",
            "stagingDir": staging_dir.as_posix(),
        }
        self.log.debug(f"OTIO representation: {representation_otio}")
        instance.data["representations"].append(representation_otio)

        self.log.info(
            "Added OTIO file representation: "
            f"{otio_file_path}"
        )

    def export_otio_representation(self, instance, filepath):
        otio_timeline = unreal_export.create_otio_timeline(instance)
        unreal_export.write_to_file(otio_timeline, filepath.as_posix())

        # check if file exists
        if not filepath.exists():
            raise FileNotFoundError(f"OTIO file not found: {filepath}")

    def _get_published_path(self, instance, representation):
        """Calculates expected `publish` folder"""
        # determine published path from Anatomy.
        template_data = instance.data.get("anatomyData")
        template_data["representation"] = representation["name"]
        template_data["ext"] = representation["ext"]
        template_data["comment"] = None

        anatomy = instance.context.data["anatomy"]
        template_data["root"] = anatomy.roots
        template = anatomy.get_template_item("publish", "default", "path")
        template_filled = template.format_strict(template_data)

        return Path(template_filled).as_posix()
