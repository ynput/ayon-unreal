""" compatibility OpenTimelineIO 0.12.0 and newer
"""

import os
import re
import ast
import unreal
from ayon_unreal.api.lib import get_shot_tracks
import opentimelineio as otio


TRACK_TYPES = {
    "MovieSceneSubTrack": otio.schema.TrackKind.Video,
    "audio": otio.schema.TrackKind.Audio
}
MARKER_COLOR_MAP = {
    "magenta": otio.schema.MarkerColor.MAGENTA,
    "red": otio.schema.MarkerColor.RED,
    "yellow": otio.schema.MarkerColor.YELLOW,
    "green": otio.schema.MarkerColor.GREEN,
    "cyan": otio.schema.MarkerColor.CYAN,
    "blue": otio.schema.MarkerColor.BLUE,
}


class CTX:
    project_fps = None
    timeline = None
    include_tags = True
    instance = None


def flatten(list_):
    for item_ in list_:
        if isinstance(item_, (list, tuple)):
            for sub_item in flatten(item_):
                yield sub_item
        else:
            yield item_


def create_otio_rational_time(frame, fps):
    return otio.opentime.RationalTime(
        float(frame),
        float(fps)
    )


def create_otio_time_range(start_frame, frame_duration, fps):
    return otio.opentime.TimeRange(
        start_time=create_otio_rational_time(start_frame, fps),
        duration=create_otio_rational_time(frame_duration, fps)
    )


def _get_metadata(item):
    if hasattr(item, 'metadata'):
        return {key: value for key, value in dict(item.metadata()).items()}
    return {}


def create_otio_reference(clip):
    metadata = _get_metadata(clip)
    media_source = clip.mediaSource()

    # get file info for path and start frame
    file_info = media_source.fileinfos().pop()
    frame_start = file_info.startFrame()
    path = file_info.filename()

    # get padding and other file infos
    padding = media_source.filenamePadding()
    file_head = media_source.filenameHead()
    is_sequence = not media_source.singleFile()
    frame_duration = media_source.duration()
    fps = CTX.project_fps
    extension = os.path.splitext(path)[-1]

    if is_sequence:
        metadata.update({
            "isSequence": True,
            "padding": padding
        })

    # add resolution metadata
    metadata.update({
        "ayon.source.width": 1920,
        "ayon.source.height": 1080,
        "ayon.source.pixelAspect": float(media_source.pixelAspect())
    })

    otio_ex_ref_item = None

    if is_sequence:
        # if it is file sequence try to create `ImageSequenceReference`
        # the OTIO might not be compatible so return nothing and do it old way
        try:
            dirname = os.path.dirname(path)
            otio_ex_ref_item = otio.schema.ImageSequenceReference(
                target_url_base=dirname + os.sep,
                name_prefix=file_head,
                name_suffix=extension,
                start_frame=frame_start,
                frame_zero_padding=padding,
                rate=fps,
                available_range=create_otio_time_range(
                    frame_start,
                    frame_duration,
                    fps
                )
            )
        except AttributeError:
            pass

    if not otio_ex_ref_item:
        section_filepath = "something.mp4"
        # in case old OTIO or video file create `ExternalReference`
        otio_ex_ref_item = otio.schema.ExternalReference(
            target_url=section_filepath,
            available_range=create_otio_time_range(
                frame_start,
                frame_duration,
                fps
            )
        )

    # add metadata to otio item
    add_otio_metadata(otio_ex_ref_item, media_source, **metadata)

    return otio_ex_ref_item


def get_marker_color(tag):
    icon = tag.icon()
    pat = r'icons:Tag(?P<color>\w+)\.\w+'

    res = re.search(pat, icon)
    if res:
        color = res.groupdict().get('color')
        if color.lower() in MARKER_COLOR_MAP:
            return MARKER_COLOR_MAP[color.lower()]

    return otio.schema.MarkerColor.RED


def create_otio_markers(otio_item, item):
    for tag in item.tags():
        if not tag.visible():
            continue

        if tag.name() == 'Copy':
            # Hiero adds this tag to a lot of clips
            continue

        frame_rate = CTX.project_fps

        marked_range = otio.opentime.TimeRange(
            start_time=otio.opentime.RationalTime(
                tag.inTime(),
                frame_rate
            ),
            duration=otio.opentime.RationalTime(
                int(tag.metadata().dict().get('tag.length', '0')),
                frame_rate
            )
        )
        # add tag metadata but remove "tag." string
        metadata = {}

        for key, value in tag.metadata().dict().items():
            _key = key.replace("tag.", "")

            try:
                # capture exceptions which are related to strings only
                _value = ast.literal_eval(value)
            except (ValueError, SyntaxError):
                _value = value

            metadata.update({_key: _value})

        # Store the source item for future import assignment
        metadata['hiero_source_type'] = item.__class__.__name__

        marker = otio.schema.Marker(
            name=tag.name(),
            color=get_marker_color(tag),
            marked_range=marked_range,
            metadata=metadata
        )

        otio_item.markers.append(marker)


def create_otio_clip(track_item):
    clip = track_item.source()
    speed = track_item.playbackSpeed()
    # flip if speed is in minus
    source_in = track_item.sourceIn() if speed > 0 else track_item.sourceOut()

    duration = int(track_item.duration())

    fps = CTX.project_fps
    name = track_item.name()

    media_reference = create_otio_reference(clip)
    source_range = create_otio_time_range(
        int(source_in),
        int(duration),
        fps
    )

    otio_clip = otio.schema.Clip(
        name=name,
        source_range=source_range,
        media_reference=media_reference
    )

    # Add tags as markers
    if CTX.include_tags:
        create_otio_markers(otio_clip, track_item)
        create_otio_markers(otio_clip, track_item.source())

    # # only if video
    # if not clip.mediaSource().hasAudio():
    #     # Add effects to clips
    #     create_time_effects(otio_clip, track_item)

    return otio_clip


def create_otio_gap(gap_start, clip_start, tl_start_frame, fps):
    return otio.schema.Gap(
        source_range=create_otio_time_range(
            gap_start,
            (clip_start - tl_start_frame) - gap_start,
            fps
        )
    )


def _create_otio_timeline(instance):
    project = CTX.timeline.get_name()
    metadata = _get_metadata(instance)

    metadata.update({
        "ayon.timeline.width": int(CTX.timeline.format().width()),
        "ayon.timeline.height": int(CTX.timeline.format().height()),
        "ayon.timeline.pixelAspect": int(CTX.timeline.format().pixelAspect()),  # noqa
        "ayon.project.useOCIOEnvironmentOverride": project.useOCIOEnvironmentOverride(),  # noqa
        "ayon.project.lutSetting16Bit": project.lutSetting16Bit(),
        "ayon.project.lutSetting8Bit": project.lutSetting8Bit(),
        "ayon.project.lutSettingFloat": project.lutSettingFloat(),
        "ayon.project.lutSettingLog": project.lutSettingLog(),
        "ayon.project.lutSettingViewer": project.lutSettingViewer(),
        "ayon.project.lutSettingWorkingSpace": project.lutSettingWorkingSpace(),  # noqa
        "ayon.project.lutUseOCIOForExport": project.lutUseOCIOForExport(),
        "ayon.project.ocioConfigName": project.ocioConfigName(),
        "ayon.project.ocioConfigPath": project.ocioConfigPath()
    })

    start_time = create_otio_rational_time(
        CTX.timeline.timecodeStart(), CTX.project_fps)

    return otio.schema.Timeline(
        name=CTX.timeline.name(),
        global_start_time=start_time,
        metadata=metadata
    )


def create_otio_track(track_type, track_name):
    return otio.schema.Track(
        name=track_name,
        kind=TRACK_TYPES[track_type]
    )


def add_otio_gap(track_item, otio_track, prev_out):
    gap_length = track_item.timelineIn() - prev_out
    if prev_out != 0:
        gap_length -= 1

    gap = otio.opentime.TimeRange(
        duration=otio.opentime.RationalTime(
            gap_length,
            CTX.project_fps
        )
    )
    otio_gap = otio.schema.Gap(source_range=gap)
    otio_track.append(otio_gap)


def add_otio_metadata(otio_item, media_source, **kwargs):
    metadata = _get_metadata(media_source)

    # add additional metadata from kwargs
    if kwargs:
        metadata.update(kwargs)

    # add metadata to otio item metadata
    for key, value in metadata.items():
        otio_item.metadata.update({key: value})


def create_otio_timeline(instance):
    ar = unreal.AssetRegistryHelpers.get_asset_registry()
    sequence = ar.get_asset_by_object_path(
        instance.data.get('sequence')).get_asset()
    # get current timeline
    CTX.timeline = sequence
    CTX.project_fps = CTX.timeline.get_display_rate()
    # convert timeline to otio
    otio_timeline = _create_otio_timeline(instance)
    members = instance.data["members"]
    # loop all defined track types
    for track in get_shot_tracks(members):
        # convert track to otio
        otio_track = create_otio_track(
            track.get_class().get_name(), track.get_display_name())

        # create otio clip and add it to track
        otio_clip = create_otio_clip(track)
        otio_track.append(otio_clip)

        # Add tags as markers
        if CTX.include_tags:
            create_otio_markers(otio_track, track)

        # add track to otio timeline
        otio_timeline.tracks.append(otio_track)

    return otio_timeline


def write_to_file(otio_timeline, path):
    otio.adapters.write_to_file(otio_timeline, path)
