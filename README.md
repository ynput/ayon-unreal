## Unreal Engine AYON Integration

This is repository for addon to [AYON](https://ayon.ynput.io/) integration Unreal Engine Editor.

For more information go to [documentation](https://ayon.ynput.io/docs/addon_unreal_artist).

### Farm rendering (Deadline)

Render instances can be rendered on Deadline instead of locally. Set
**Render target** to **Farm rendering** on the render instance and publish.

#### How it works

1. Publish builds a Movie Render Queue job in memory and points its output to
   the AYON work directory (see [Output location](#output-location)). The
   queue is saved as an MRQ manifest to the work directory, the render queue
   asset in the project is not modified.
2. `ayon-deadline` submits an `UnrealEngine5` render job and a dependent
   publish job.
3. On the render node, Deadline `GlobalJobPreLoad` extracts the AYON
   environment for the job context, which runs AYON launch hooks (e.g.
   Perforce workspace sync).
4. The Deadline `UnrealEngine5` plugin starts `UnrealEditor-Cmd` with the
   project and
   `-execcmds="py from ayon_unreal.api import rendering_remote; rendering_remote.main()"`.
   `rendering_remote` loads the manifest and renders it.
5. When the render finishes, `rendering_remote` marks the Deadline job as
   completed (or failed) through the Deadline Web Service. The editor doesn't
   close by itself, the task ends when the job is completed.
6. The publish job publishes the rendered files.

#### Requirements

- `ayon-deadline` addon with `GlobalJobPreLoad.py` 1.3.0 or newer deployed to
  `<DeadlineRepository>/custom/plugins/`, and the AYON executable configured
  in the `Ayon` Deadline plugin.
- The stock `UnrealEngine5` Deadline plugin
  (`<DeadlineRepository>/plugins/UnrealEngine5`). Disable any custom
  `UnrealEngine5` plugin in `<DeadlineRepository>/custom/plugins/`.
- Unreal Engine installed on render nodes, with the same version as the
  application used to publish. Unreal application variants in AYON settings
  must be named `<major>-<minor>` (e.g. `5-8`).
- Deadline Web Service reachable from render nodes. Its URL is passed to the
  job as `AYON_DEADLINE_URL`.
- The AYON work directory (where output and the MRQ manifest are written)
  must be on storage shared by the workstation, render nodes and the node
  running the publish job.

#### Render presets

The render preset (instance **Render Preset**, or legacy
`ayon+settings://unreal/render_setup/render_config_path`) can be:

- **Movie Render Queue config** - output directory and file name are
  overridden on the job automatically. The config must contain EXR image
  sequence output.
- **Movie Render Graph** (Unreal 5.4+) - the graph asset is never modified,
  the output is overridden with job variable overrides. The top-level graph
  (nodes in subgraphs are not used) must drive these properties with graph
  variables:

  | Variable | Type | Node | Property |
  | --- | --- | --- | --- |
  | `OutputDirectory` | `DirectoryPath` or `String` | Global Output Settings (Globals branch) | Output Directory |
  | `FileNameFormat` | `String` | every image sequence output node (e.g. EXR Sequence) | File Name Format |

  For each property: enable its override checkbox, right click it and
  choose **Promote Property to Pin**, then connect the variable to the new
  pin. `Validate Movie Render Graph Output` fails the publish if this is not
  set up.

In both cases the rendered file type must match
`ayon+settings://unreal/render_setup/render_format`, which is used for the
expected files.

#### Output location

Files are rendered to the directory of the project anatomy `work` →
`default` template, without the version part, as
`<unreal work file name>_<folder>_<product>.<frame>.<ext>`.

#### Perforce

With `ayon-perforce` enabled for the project:

- The changelist and stream of the publishing workspace are sent with the job
  (`AYON_P4_CHANGELIST`, `AYON_P4_STREAM`).
- Each render node uses its own workspace, named by the `ayon-perforce`
  workspace template. It is created when missing. Its root is the Unreal
  project directory, so the project opened on the render node is
  `<workspace root>/<project>.uproject` (passed to the Deadline plugin as
  `UnrealUProject`).
- The workspace is synced to the job changelist before every task, so render
  nodes switching between jobs render the right changelist.
- The extracted AYON environment is cached per render node for Perforce jobs
  (`AYON_ENV_CACHE_PER_HOST`), even when render nodes share `AYON_SITE_ID`.
- `p4` must be on `PATH` of render nodes, logged in to the server for the
  render node user.

#### Troubleshooting

Check the Unreal log in the Deadline task log (`LogPython` lines).

- `No Deadline job ID found in environment variables` - `GlobalJobPreLoad`
  is older than 1.3.0.
- `AttributeError: 'NoneType' object has no attribute 'split'` in
  `ayon_unreal/api/pipeline.py` - `AYON_UNREAL_VERSION` is missing, update
  `ayon-unreal`.
- `AYON_P4_CHANGELIST is not set, syncing to head revision.` - the job was
  submitted without changelist (check that `Extract P4 Changelist info` ran
  during publish) or `GlobalJobPreLoad` is older than 1.3.0.
- Render finishes but the task never ends - the render node can't reach the
  Deadline Web Service at `AYON_DEADLINE_URL`.
- Publish job fails on missing files - expected files don't match the
  rendered files, check the render preset requirements above.

### Building

- run `python ./create_package.py`
- upload resulting zip for `package` directory to your AYON server instance.
- add installed version to your bundle
