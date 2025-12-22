Changelog:

## [0.8.5b8]

- Changed: use pyproject.toml instead of setup.py
- Updated: migration scripts are modular, each module file being a standalone
  migration cli.
- Fixed: make invalid file id a validation error
- Changed: providing additional inputs to the service is now an error.
- Added: local-queue jobs timeout.
- Fixed: create intermediate directories if "symlink" parameter requires it.
- Changed: minimal python version set to 3.10
- Changed: services directory is scanned recursively searching for service
  files.
- Added: services directory can be set using SLIVKA\_DIR\_SERVICES environment
  variable.
- Added: allow multiple service directories by separating them with ":"
  or ";" (system-specific) in the configuration.
- Added: --example/--no-example option to the init command that control adding
  example files to the new project.
- Added: --force option to the init command to overwrite existing project
  directory.
- Added: ability to define name aliases for services within configuration
  files. Services can now be accessed via the web API using the aliases.
- Fixed: Canonicalize stored paths before computing paths relative to jobs or
  uploads directory.
- Deprecated: --daemon and --pid-file command line arguments because they did
  not work reliably. Using supervisord or systemd is a preferred way of
  creating and managing daemon processes.

## [0.8.5b7]

- Added: filename can be specified when referring to a file using its id by
  appending `;filename=<name>` option to the id.
- Fixed: disallow absolute paths and references to parent directories in
  uploaded file names.
- Fixed: make sure input files are staged in the working directory specific to
  the job.

## [0.8.5b6]

- Added: you can use $(filename), $(filename.stem) and $(filename.ext)
  placeholders when defining the name for the
  symlink in the service configuration file. Those are substituted for the
  names given to the uploaded files using
  `Content-Disposition` header or an actual filesystem name for job results.
- Changed: symlink names no longer have indices appended to them for file
  arrays. You need to specify c-style format
  placeholder explicitly e.g. %d.
- Changed: operate on timezone aware date-times. API returns date-times with
  timezones.
- Changed: store and retrieve date-times in UTC format in the database
- Added: database migration script converting date-times to correct UTC dates.

## [0.8.5] - (upcoming)

- Added: support for Python 3.11, 3.12 and 3.13
- Fixed: logging configuration crashing on Python 3.12.
- Fixed: invalid file path resolution when the path contained symlinks and the
  SLIVKA_HOME was provided explicitly.
- Updated: transition from using *distutils* to *packaging* for package version
  information.
- Added: database documents tests
- Fixed: missing status entries in job status cache for up to 5 seconds after
  new jobs are submitted. Now, every time a new job is submitted, the cache is
  invalidated.
- Fixed: API responses involving result file return actual location of the
  resource instead of the path inferred form the job id
- Changed: the flat structire of job directories is changed into a tree with
  the first two levels consisting of the counter part of the object id and
  the last level of the remaining part.
- Changed: bumped the version of werkzeug library used
- Fixed: explicitly defined pytest.marks used in tests internally
- Added: migration tool converting old project structure to the new one
- Changed: ShellRunner spawns a subprocess instead of running the command in a
  default shell which caused issues with some command line tools.
- Added: 60-seconds timeout to job-status-checking command, to prevent the
  scheduler from hanging indefinitely on execution system failure.
- Changed: extend settings file validation to allow beta pre-releases in slivka
  version field.
- Added: jobs dasboard API where existing jobs can be retrieved.
- Added: defining and editing titles and media-types of uploaded files.
- Added: `slivka validate` command for checking the settings files.
- Added: settings can be loaded from environment variables
- Added: command line option to keep test output files
- Fixed: slurm status checking function not showing jobs from all partitions
- Added: logging commands run to `.command` file in the job's work directory
- Changed: `mongodb.database` parameter is no longer used as the default
  authentication database. Specify the authentication database using uri path.
- Added: additional mongodb options can be set using `mongodb.query` or
  `mongodb.options` properties.
- Deprecated: settings query parameters in the `mongodb.host` uri

## [0.8.4] - 2024-02-05

- Changed: prefix middleware no longer squashes repeating slashes.
- Changed: prefix middleware removes single trailing slash in prefix.
- Fixed: tests of prefix middleware.
- Changed: the choice field only allows the keys of the `choices` mapping as
  valid input values.
- Changed: the JSON response for job resource contains the choice keys instead
  of values for choice inputs.
- Changed: name of the settings file changed to *settings.yaml* from
  *config.yaml* in the documentation.
- Added: Ability to run jobs with LSF workload manager.
- Added: Interval parameter for service tests that controls the frequency with
  which the tests are run.

## [0.8.3b3] - 2024-08-08

- Added: argument constants can be specified in the runner definition and
  applied conditionally to the command line when that runner is selected.
- Added: additional environment variables can be specified in the runner
  definition and applied conditionally when that runner is selected.
- Added: selectors can be additionally parametrized from the runner
  config. Selector functions can take an extra *context* argument where
  there are given the service name, list of runner names and additional
  values associated with each runner. It allows writing reusable selectors
  and moves constraints from code to config file.

## [0.8.3b2] - 2024-06-25

- Added: filtering options to the usage statistics repository. Entries can be
  filtered by service name, date ranges and completion status.
- Added: tests of the filtering option.
- Added: python-dateutil dependency which provides rich datetime manipulation
  functions.
- Added: OpenAPI documentation of the `/stats` endpoint

## [0.8.3b1] - 2024-06-18

- Added: service usage statistics repository which reads the number of jobs run
  each month
- Added: service usage view API endpoint
- Added: tests of the usage statistics repository

## [0.8.3b0] - 2023-12-13

- Added: periodic service health checks
    - added "tests" section to service configuration
    - tests are run every hour (not currently configurable) and the reports are
      stored in the database
    - service status is no longer determined from user jobs
- Deprecated: `slivka.db.documents.ServiceState` class. Usages should be
  replaced by `slivka.db.repositories.ServiceStatusRepository`
- Changed: main configuration and service files version changed to 0.8.3.
  Versions 0.3 for configuration and 0.8 for services are still supported.
- Added: new documentation entries describing automated tests feature.

## [0.8.2b0] - 2023-11-21

- Changed: migrated all tests from a deprecated nose framework to pytest
- Removed: nose removed from project dependencies.
- Fixed: fixed failures caused by the resource loader being inconsistent
  across different python versions.
- Changed: server returns 1970-01-01T01:00:00 (unix timestamp 0) as the service
  status timestamp when the status is undefined instead of returning the
  current time.
- Changed: switched to python-daemon library for managing daemons and pid
  files.
- Fixed: automatically resolve pid file path to the absolute path. Fixes
  permission errors when relative path was combined with a `--daemon` flag.

## [0.8.1b1] - 2023-07-11

- Changed: dependency updates
    - setuptools dependency changed to >=65.5.1
    - removed upper version limit from all dependencies
- Removed: requirements.txt file no longer present in the repository.
  Install with _editable_ mode during development.
- Fixed: _api_ blueprint name clash
- Fixed: replaced usages of deprecated `pkg_resources` with a newer
  `importlib.resources` module

## [0.8.1b0] - 2022-12-14

- Added: new SlurmRunner which executes jobs using Slurm workload manager.
- Added: custom parameters can be specified for the sbatch in the
  configuration using sbatchargs option
- Changed: SlurmRunner uses C-ansi escaping for control characters
  present in the command
- Fixed: use sources from the current commit for building conda package
- Fixed: include runner.bash.tpl in the manifest file
- Fix: include media type name in a warning message issued when the
  media type validator is not defined

## [0.8.0b20] - 2022-11-11

- Changed: use Redoc as a default openapi documentation generator.
- Changed: serve _redoc-index.html_ and _openapi.yaml_ from project
  static directory allowing per-instance customisation.
- Fixed: reset mock database state before every scheduler test fixing
  job requests from previous tests from leaking to later tests.
- Fixed: integer and decimal fields no longer match boolean values and
  integer fields no longer match floats which are not integers
- Added: unit tests for REST API endpoints
- Fixed: MongoDocument returns None instead of raising an exception
  when searching documents using improperly formatted document id
- Changed: hide min or max exclusive constraints if corresponding min
  or max constraint is not set

## [0.8.0b19] - 2021-10-26

- Changed: indicate request execution failure with exceptions
  instead of status tuples.
- Fixed: use full list of environment variables (user + system) when
  interpolating variables specified inside the command line
- Fixed: starting slivka as a daemon no longer crashes when launched
  without explicit _--home_ parameter. *SLIVKA_HOME* variable is
  always configured before the process is forked.

## [0.8.0b18] - 2021-10-25

- Changed: merged _JobMetadata_ object into _JobRequest_ object. It
  improves code clarity and avoids fake relations between database
  documents.

## [0.8.0b17] - 2021-10-22

- Fixed: set database server selection timeout to 2ms making
  connection issues throw quickly instead of blocking for a minute.
- Fixed: all calls to the database are executed within a *retry_call*
  preventing entire application crash in case of the database
  connection failure.

## [0.8.0b16] - 2021-08-10

- Removed python client documentation from slivka framework
  documentation.
- Updated framework documentation.
- Fixed: update _completion time_ property of job objects when job
  completes.
- Changed: use b64-encoded database id to identify jobs instead of
  randomly generated uuid. it makes ids shorter and utilized database
  indexing.

## [0.8.0b15] - 2021-07-28

- Changed: file id is now used as an output file label if the name is
  not specified explicitly. no more null labels.
