# -*- coding: utf-8 -*-

import pyblish.api
import unreal
from ayon_core.pipeline.publish import PublishValidationError, RepairAction
from ayon_unreal.api.pipeline import get_tracks, add_track


class ValidateCameraTracks(pyblish.api.InstancePlugin):
    """Ensure that the camera tracks existing
    in the selected level sequence for publishing

    """

    order = pyblish.api.ValidatorOrder
    label = "Validate Camera Tracks"
    hosts = ['unreal']
    families = ["camera"]
    actions = [RepairAction]

    def get_invalid(self, instance):
        invalid = []
        ar = unreal.AssetRegistryHelpers.get_asset_registry()
        members = instance.data.get("members", {})
        if not members:
            invalid.append("No assets selected for publishing.")
            return invalid
        for member in members:
            data = ar.get_asset_by_object_path(member)
            is_level_sequence = (
                data.asset_class_path.asset_name == "LevelSequence")
            if not is_level_sequence:
                invalid.append(
                    "The published assets must be Level Sequence")
            sequence = data.get_asset()
            seq_name = sequence.get_name()
            all_tracks = get_tracks(sequence)
            if not all_tracks:
                message = (
                    f"No tracks found in Level Sequence {seq_name}. You can perform\n "
                    "repair action to add camera track into the sequence\n "
                    "and assign the camera to the track you want to publish\n"
                )
                invalid.append(message)
            has_movie_tracks = False
            for track in all_tracks:
                if str(track).count("MovieSceneCameraCutTrack"):
                    has_movie_tracks = True
                    break
            if not has_movie_tracks:
                message = (
                    f"The level sequence {seq_name} does not include any Movie\n "
                    " Scene Camera Cut Track. Please make sure the published level\n "
                    "sequence must include Movie Scene Camera Cut Track."
                )
                invalid.append(message)
        return invalid

    def process(self, instance):
        invalid = self.get_invalid(instance)
        if invalid:
            report = "{}".format(err for err in invalid)
            raise PublishValidationError(report, title="Invalid Camera Tracks")

    @classmethod
    def repair(cls, instance):
        ar = unreal.AssetRegistryHelpers.get_asset_registry()
        members = instance.data.get("members", {})
        for member in members:
            data = ar.get_asset_by_object_path(member)
            is_level_sequence = (
                data.asset_class_path.asset_name == "LevelSequence")
            if is_level_sequence:
                sequence = data.get_asset()
                add_track(sequence, unreal.MovieSceneCameraCutTrack)
