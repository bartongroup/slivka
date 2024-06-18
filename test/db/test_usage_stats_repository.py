from datetime import date

import mongomock
import pytest
import yaml
from hamcrest import assert_that, contains_inanyorder

from slivka.compat import resources
from slivka.db.documents import JobRequest
from slivka.db.helpers import insert_many
from slivka.db.repositories import (
    UsageStats,
    UsageStatsMongoDBRepository
)


@pytest.fixture()
def usage_stats_repository(database):
    return UsageStatsMongoDBRepository(database)


@pytest.fixture()
def job_requests(request, database):
    stream = resources.open_text(__package__, request.param)
    data = [JobRequest(**kwargs) for kwargs in yaml.load(stream, yaml.SafeLoader)]
    insert_many(database, data)
    return data


@pytest.mark.parametrize(
    "job_requests, expected_output",
    [
        (
            "testdata/requests_set_1.yaml",
            [
                UsageStats(date(2020, 3, 1), "example-0", 3),
            ]
        ),
        (
            "testdata/requests_set_2.yaml",
            [
                UsageStats(date(2020, 5, 1), "example-0", 2),
                UsageStats(date(2020, 5, 1), "example-1", 3),
                UsageStats(date(2020, 5, 1), "example-2", 1),
            ]
        ),
        (
            "testdata/requests_set_3.yaml",
            [
                UsageStats(date(2020, 3, 1), "example-0", 3),
                UsageStats(date(2020, 4, 1), "example-0", 3),
                UsageStats(date(2020, 5, 1), "example-0", 3),
                UsageStats(date(2021, 3, 1), "example-0", 3),
                UsageStats(date(2021, 4, 1), "example-0", 3),
                UsageStats(date(2021, 5, 1), "example-0", 3),
                UsageStats(date(2022, 3, 1), "example-0", 3),
                UsageStats(date(2022, 4, 1), "example-0", 3),
                UsageStats(date(2022, 5, 1), "example-0", 3),
            ]
        ),
        (
            "testdata/requests_set_4.yaml",
            [
                UsageStats(date(2020, 10, 1), "example-0", 4),
                UsageStats(date(2020, 11, 1), "example-0", 4),
                UsageStats(date(2020, 10, 1), "example-1", 8),
                UsageStats(date(2020, 11, 1), "example-1", 8),
                UsageStats(date(2020, 10, 1), "example-2", 12),
                UsageStats(date(2020, 11, 1), "example-2", 12),
                UsageStats(date(2020, 10, 1), "example-3", 16),
                UsageStats(date(2020, 11, 1), "example-3", 16),
            ]
        )
    ],
    indirect=['job_requests']
)
def test_usage_stats_list_all(
        mongo_client,
        usage_stats_repository,
        job_requests,
        expected_output):
    if isinstance(mongo_client, mongomock.MongoClient):
        pytest.skip("Unable to test with mongomock database")
    assert_that(usage_stats_repository.list_all(), contains_inanyorder(*expected_output))
