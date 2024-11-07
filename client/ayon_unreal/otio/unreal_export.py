""" compatibility OpenTimelineIO 0.12.0 and newer
"""

import os
import unreal
from pathlib import Path
from ayon_core.pipeline import get_current_project_name, Anatomy
from ayon_unreal.api.lib import get_shot_tracks, get_screen_resolution
from ayon_unreal.api.pipeline import get_sequence_for_otio
import opentimelineio as otio


TRACK_TYPES = {
    "MovieSceneSubTrack": otio.schema.TrackKind.Video,
    "MovieSceneAudioTrack": otio.schema.TrackKind.Audio
}


class CTX:
    project_fps = None
    timeline = None
    include_tags = True


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


def create_otio_reference(instance, section, section_number,
                          frame_start, frame_duration, is_sequence=False):
    metadata = {}

    project = get_current_project_name()
    anatomy = Anatomy(project)
    root = anatomy.roots['renders']
    track_name = section.get_shot_display_name()
    render_dir = f"{root}/{project}/editorial_pkg/{instance.data.get('output')}"
    render_dir = f"{render_dir}/{track_name}_{section_number + 1}"
    render_path = Path(render_dir)
    frames = [str(x) for x in render_path.iterdir() if x.is_file()]
    # get padding and other file infos
    file_head, padding, extension = get_sequence_for_otio(frames)
    fps = CTX.project_fps

    if is_sequence:
        metadata.update({
            "isSequence": True,
            "padding": padding
        })

    # add resolution metadata
    resolution = get_screen_resolution()
    metadata.update({
        "ayon.source.width": resolution.x,
        "ayon.source.height": resolution.y,
    })

    otio_ex_ref_item = None

    if is_sequence:
        # if it is file sequence try to create `ImageSequenceReference`
        # the OTIO might not be compatible so return nothing and do it old way
        try:
            otio_ex_ref_item = otio.schema.ImageSequenceReference(
                target_url_base=render_dir + os.sep,
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
        section_filepath = f"{render_dir}/{file_head}.mp4"
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
    add_otio_metadata(otio_ex_ref_item, metadata)

    return otio_ex_ref_item


def create_otio_clip(instance, target_track):
     for section_number, section in enumerate(target_track.get_sections()):
        # flip if speed is in minus
        shot_start = section.get_start_frame()
        duration = int(section.get_end_frame() - section.get_start_frame()) + 1

        fps = CTX.project_fps
        name = section.get_shot_display_name()

        media_reference = create_otio_reference(instance, section, section_number, shot_start, duration)
        source_range = create_otio_time_range(
            int(shot_start),
            int(duration),
            fps
        )

        otio_clip = otio.schema.Clip(
            name=name,
            source_range=source_range,
            media_reference=media_reference
        )

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


def _create_otio_timeline(instance)
    resolution = get_screen_resolution()
    metadata = {
        "ayon.timeline.width": int(resolution.x),
        "ayon.timeline.height": int(resolution.y),
        # "ayon.project.ocioConfigName": unreal.OpenColorIOConfiguration().get_name(),
        # "ayon.project.ocioConfigPath": unreal.OpenColorIOConfiguration().configuration_file
    }

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


def add_otio_gap(track_section, otio_track, prev_out):
    gap_length = track_section.get_start_frame() - prev_out
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


def add_otio_metadata(otio_item, metadata):
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
    for target_track in get_shot_tracks(members):
        # convert track to otio
        otio_track = create_otio_track(
            target_track.get_class().get_name(),
            target_track.get_display_name())

        # create otio clip and add it to track
        otio_clip = create_otio_clip(instance, target_track)
        otio_track.append(otio_clip)

        # add track to otio timeline
        otio_timeline.tracks.append(otio_track)

    return otio_timeline


def write_to_file(otio_timeline, path):
    otio.adapters.write_to_file(otio_timeline, path)
