Changelog:

## [0.8.5] - (upcoming)

- Added: support for Python 3.11 and 3.12
- Fixed: logging configuration crashing on Python 3.12.
- Fixed: invalid file path resolution when the path contained symlinks and the
  SLIVKA_HOME was provided explicitly.
- Updated: transition from using *distutils* to *packaging* for package version
  information.
- Added: database documents tests
- Fixed: missing status entries in job status cache for up to 5 seconds after
  new jobs are submitted. Now, every time a new job is submitted, the cache is
  invalidated.

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
