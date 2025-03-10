import os
import shutil
import requests
from pathlib import Path
from copy import deepcopy

import unreal

pipeline_subsystem = unreal.get_editor_subsystem(
    unreal.MoviePipelineQueueSubsystem
)

pie_executor = None

@unreal.uclass()
class UE_MovieRenderExecutorWrapper(unreal.MoviePipelinePythonHostExecutor):
    """Wrapper executor to handle the MoviePipelinePIEExecutor"""
    job_id = unreal.uproperty(str)
    manifest_name = unreal.uproperty(str)

    @unreal.ufunction(ret=None)
    def start_job(self):
        global pie_executor
        pie_executor = unreal.MoviePipelinePIEExecutor()
        pie_executor.on_executor_finished_delegate.add_callable(self.on_job_finished)

        mrq = pipeline_subsystem.get_queue()
        mrq.delete_all_jobs()
        manifest_to_load = f"MovieRenderPipeline/{self.manifest_name}"
        mrq = unreal.MoviePipelineLibrary.load_manifest_file_from_string(manifest_to_load)
        pipeline_subsystem.load_queue(mrq)
        active_job = next(job for job in mrq.get_jobs() if job.is_enabled())
        map_package = unreal.MoviePipelineLibrary.get_map_package_name(active_job)
        unreal.EditorLoadingAndSavingUtils.load_map(map_package)

        pipeline_subsystem.render_queue_with_executor_instance(pie_executor)

    def on_job_finished(self, executor, success):
        payload = {
            "Command": "complete" if success else "fail",
            "JobID": self.job_id,
        }
        resp = requests.put( # TODO: get Deadline REST API URL from env
            "http://localhost:8081/api/jobs",
            json=payload,
        )
        unreal.log(f"{resp.text = }")


def main():
    # get context data
    env: dict = deepcopy(os.environ)
    cmd_tokens, cmd_switches, cmd_parameters = unreal.SystemLibrary.parse_command_line(
        unreal.SystemLibrary.get_command_line()
    )

    # check context data
    if not env.get("AYON_DEADLINE_JOBID"):
        raise ValueError("No Deadline job ID found in environment variables")
    if not cmd_parameters.get("MRQManifest"):
        raise ValueError("No MRQ manifest found in command line parameters")

    # get job_id and work MRQ
    job_id = env["AYON_DEADLINE_JOBID"]
    work_mrq = Path(cmd_parameters["MRQManifest"])

    # copy work MRQ locally
    saved_dir = Path(unreal.Paths.project_saved_dir()) / "MovieRenderPipeline"
    mrq_dest: Path = saved_dir / work_mrq.name
    if not saved_dir.exists():
        saved_dir.mkdir(parents=True)
    shutil.copyfile(work_mrq, mrq_dest)
    unreal.log(f"Copied WorkMRQ to: {mrq_dest}")

    # instantiate executor wrapper and start it
    exec_wrapper = UE_MovieRenderExecutorWrapper()
    exec_wrapper.job_id = job_id
    exec_wrapper.manifest_name = mrq_dest.name
    exec_wrapper.start_job()


if __name__ == "__main__":
    main()
