# this mustn't be called outside unreal

from deadline_rpc import BaseRPC


import os
import shutil
from pathlib import Path

import unreal

# executor = None
pipeline_subsystem = unreal.get_editor_subsystem(
    unreal.MoviePipelineQueueSubsystem
)

@unreal.uclass()
class RemoteRenderExecutor(unreal.MoviePipelinePythonHostExecutor):
    mrq = unreal.uproperty(unreal.MoviePipelineQueue)
    executor = unreal.uproperty(unreal.MoviePipelinePIEExecutor)

    # Constructor that gets called when created either via C++ or Python
    def _post_init(self):
        cmd_tokens, cmd_switches, cmd_parameters = unreal.SystemLibrary.parse_command_line(
            unreal.SystemLibrary.get_command_line()
        )
        for token in cmd_tokens:
            unreal.log(f"{token = }")
        for switch in cmd_switches:
            unreal.log(f"{switch = }")
        for key, value in cmd_parameters.items():
            unreal.log(f"{key = }, {value = }")

        self.mrq = self.get_mrq_manifest(cmd_parameters)
        self.executor = unreal.MoviePipelinePIEExecutor()

        self.executor.on_executor_finished_delegate.add_function_unique(self, "on_job_finished")
        # add a callable to the executor to be executed when the pipeline is done rendering
        self.executor.on_executor_finished_delegate.add_callable(
            lambda: unreal.SystemLibrary.quit_editor()
        )
        # add a callable to the executor to be executed when the pipeline fails to render
        self.executor.on_executor_errored_delegate.add_callable(
            lambda: unreal.SystemLibrary.quit_editor()
        )

    def get_mrq_manifest(self, cmd_parameters):
        if not cmd_parameters.get("PublishedMRQManifest"):
            unreal.log_error("Missing '-PublishedMRQManifest' argument")
            raise Exception("Missing '-PublishedMRQManifest' argument")

        game_root = Path(unreal.Paths.project_dir())
        published_manifest = Path(cmd_parameters["PublishedMRQManifest"])

        # was copied over in JobPreLaunch
        # mrq = unreal.MoviePipelineLibrary.load_manifest_file_from_string(f"MovieRenderPipeline/{published_manifest.name}")
        mrq = unreal.MoviePipelineLibrary.load_manifest_file_from_string(f"MovieRenderPipeline/QueueManifest.utxt")
        if not mrq:
            raise Exception("Failed to load manifest file")

        if len(mrq.get_jobs()) == 0:
            raise Exception("No jobs in queue to process.")

        if len(mrq.get_jobs()) > 1:
            active_jobs =[job for job in mrq.get_jobs() if job.is_enabled()]
            if len(active_jobs) > 1:
                raise Exception("Only 1 job per queue supported")

        unreal.log(f"{mrq = }")
        return mrq

    @unreal.ufunction(override=True)
    def execute_delayed(self, queue):
        self.start_job()

    @unreal.ufunction(ret=None)
    def start_job(self):
        curr_job = self.mrq.get_jobs()[0]

        # load map
        map_package = unreal.MoviePipelineLibrary.get_map_package_name(curr_job)
        _map_load_start = unreal.MathLibrary.utc_now()
        unreal.EditorLoadingAndSavingUtils.load_map(map_package)
        _map_load_end = unreal.MathLibrary.utc_now()
        load_duration = unreal.MathLibrary.get_total_seconds(
            unreal.MathLibrary.subtract_date_time_date_time(
                _map_load_end, _map_load_start
            )
        )
        unreal.log(f"Map load duration: {load_duration} seconds")

        self.executor.execute(self.mrq)

    @unreal.ufunction(ret=None, params=[unreal.MoviePipelineExecutorBase, bool])
    def on_job_finished(self, executor, fatal_error):
        unreal.log("Progress: 100.0%")
        unreal.log("Progress: 100,0%")
        unreal.log("Progress: 100%")
        unreal.log("Progress: 100 %")
        self.task_complete = True
        self.on_executor_finished_impl()
        # unreal.SystemLibrary.quit_editor()

    # @unreal.ufunction(override=True)
    # def is_rendering(self):
    #     # This will block anyone from trying to use the UI to launch other
    #     # jobs and cause confusion
    #     return self.executor is not None



class UnrealRPC(BaseRPC):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._render_cmd = ["rendering_remote.py"]

        # # Keep track of the task data
        # self._shot_data = None
        # self._queue = None
        # self._manifest = None
        # self._sequence_data = None

    def execute(self):
        render_executor = RemoteRenderExecutor(self.proxy)
        pipeline_subsystem.render_queue_with_executor_instance(render_executor)
        unreal.log(f"{self.proxy.get_job_user() = }")
        unreal.log(f"{dir(self.proxy)}")
        self.proxy.complete_job()
        return render_executor

if __name__ == "__main__":
    rpc = UnrealRPC()
