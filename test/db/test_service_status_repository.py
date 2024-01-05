from datetime import datetime

import pytest
from hamcrest import assert_that, contains_inanyorder, has_entries

from slivka.db.repositories import (
    ServiceStatusInfo,
    ServiceStatusMongoDBRepository,
)


@pytest.fixture()
def repository(database):
    return ServiceStatusMongoDBRepository(database)


@pytest.fixture()
def raw_collection(database):
    return database[ServiceStatusMongoDBRepository._collection]


def test_insert_one_item(repository, raw_collection):
    repository.insert(
        ServiceStatusInfo(
            "example",
            "runner1",
            ServiceStatusInfo.OK,
            message="example message",
            timestamp=datetime(2020, 4, 14),
        )
    )
    # noinspection PyTypeChecker
    assert_that(
        list(raw_collection.find()),
        contains_inanyorder(
            has_entries(
                dict(
                    service="example",
                    runner="runner1",
                    state=ServiceStatusInfo.OK.value,
                    message="example message",
                    timestamp=datetime(2020, 4, 14),
                )
            )
        ),
    )


def test_insert_two_items(repository, raw_collection):
    repository.insert(
        ServiceStatusInfo(
            "example",
            "runner1",
            ServiceStatusInfo.OK,
            message="",
            timestamp=datetime(2020, 5, 10),
        )
    )
    repository.insert(
        ServiceStatusInfo(
            "other",
            "runner2",
            ServiceStatusInfo.WARNING,
            message="error message",
            timestamp=datetime(2020, 5, 11),
        )
    )
    # noinspection PyTypeChecker
    assert_that(
        list(raw_collection.find()),
        contains_inanyorder(
            has_entries(
                dict(
                    service="example",
                    runner="runner1",
                    state=ServiceStatusInfo.OK.value,
                    message="",
                    timestamp=datetime(2020, 5, 10),
                )
            ),
            has_entries(
                dict(
                    service="other",
                    runner="runner2",
                    state=ServiceStatusInfo.WARNING.value,
                    message="error message",
                    timestamp=datetime(2020, 5, 11),
                )
            ),
        ),
    )


def test_insert_item_twice(repository, raw_collection):
    status = ServiceStatusInfo(
        "example",
        "runner1",
        ServiceStatusInfo.OK,
        message="",
        timestamp=datetime(2020, 5, 10),
    )
    repository.insert(status)
    repository.insert(status)
    # noinspection PyTypeChecker
    assert_that(
        list(raw_collection.find()),
        contains_inanyorder(
            has_entries(
                dict(
                    service="example",
                    runner="runner1",
                    state=ServiceStatusInfo.OK.value,
                    message="",
                    timestamp=datetime(2020, 5, 10),
                )
            ),
            has_entries(
                dict(
                    service="example",
                    runner="runner1",
                    state=ServiceStatusInfo.OK.value,
                    message="",
                    timestamp=datetime(2020, 5, 10),
                )
            ),
        ),
    )


@pytest.mark.parametrize(
    "init_documents, expected",
    [
        (
            [
                dict(
                    service="example",
                    runner="runner1",
                    state=ServiceStatusInfo.OK.value,
                    message="example message",
                    timestamp=datetime(2020, 4, 26),
                )
            ],
            [
                ServiceStatusInfo(
                    "example",
                    "runner1",
                    ServiceStatusInfo.OK,
                    message="example message",
                    timestamp=datetime(2020, 4, 26),
                )
            ],
        ),
        (
            [
                dict(
                    service="example",
                    runner="runner1",
                    state=ServiceStatusInfo.WARNING.value,
                    message="service issue",
                    timestamp=datetime(2020, 3, 23),
                ),
                dict(
                    service="example",
                    runner="runner1",
                    state=ServiceStatusInfo.OK.value,
                    message="",
                    timestamp=datetime(2020, 1, 3),
                ),
            ],
            [
                ServiceStatusInfo(
                    "example",
                    "runner1",
                    ServiceStatusInfo.WARNING,
                    message="service issue",
                    timestamp=datetime(2020, 3, 23),
                ),
                ServiceStatusInfo(
                    "example",
                    "runner1",
                    ServiceStatusInfo.OK,
                    message="",
                    timestamp=datetime(2020, 1, 3),
                ),
            ],
        ),
        (
            [
                dict(
                    service="example",
                    runner=f"runner{i}",
                    state=ServiceStatusInfo.OK.value,
                    message="",
                    timestamp=datetime(2020, 10, 18),
                )
                for i in range(5)
            ],
            [
                ServiceStatusInfo(
                    "example",
                    f"runner{i}",
                    ServiceStatusInfo.OK,
                    message="",
                    timestamp=datetime(2020, 10, 18),
                )
                for i in range(5)
            ],
        ),
        (
            [
                dict(
                    service=f"example{i}",
                    runner="runner0",
                    state=ServiceStatusInfo.OK.value,
                    message="",
                    timestamp=datetime(2020, 8, 9),
                )
                for i in range(10)
            ],
            [
                ServiceStatusInfo(
                    f"example{i}",
                    "runner0",
                    ServiceStatusInfo.OK,
                    message="",
                    timestamp=datetime(2020, 8, 9),
                )
                for i in range(10)
            ],
        ),
    ],
)
def test_list_all_unfiltered(
    raw_collection, repository, init_documents, expected
):
    raw_collection.insert_many(map(dict, init_documents))
    # noinspection PyTypeChecker
    assert_that(repository.list_all(), contains_inanyorder(*expected))


@pytest.mark.parametrize(
    "service_filter, init_documents, expected",
    [
        (
            "example1",
            [
                dict(
                    service="example0",
                    runner="runner0",
                    state=ServiceStatusInfo.WARNING.value,
                    message="error message",
                    timestamp=datetime(2020, 10, 3),
                ),
                dict(
                    service="example1",
                    runner="runner0",
                    state=ServiceStatusInfo.OK.value,
                    message="",
                    timestamp=datetime(2020, 4, 19),
                ),
            ],
            [
                ServiceStatusInfo(
                    "example1",
                    "runner0",
                    ServiceStatusInfo.OK.value,
                    message="",
                    timestamp=datetime(2020, 4, 19),
                )
            ],
        ),
        (
            "example1",
            [
                dict(
                    service="example0",
                    runner="runner0",
                    state=ServiceStatusInfo.OK.value,
                    message="",
                    timestamp=datetime(2020, 12, 17),
                ),
                dict(
                    service="example1",
                    runner="runner0",
                    state=ServiceStatusInfo.OK.value,
                    message="",
                    timestamp=datetime(2020, 11, 30),
                ),
                dict(
                    service="example1",
                    runner="runner1",
                    state=ServiceStatusInfo.WARNING.value,
                    message="",
                    timestamp=datetime(2020, 11, 29),
                ),
                dict(
                    service="example2",
                    runner="runner0",
                    state=ServiceStatusInfo.OK.value,
                    message="",
                    timestamp=datetime(2020, 10, 7),
                ),
            ],
            [
                ServiceStatusInfo(
                    "example1",
                    "runner0",
                    ServiceStatusInfo.OK,
                    message="",
                    timestamp=datetime(2020, 11, 30),
                ),
                ServiceStatusInfo(
                    "example1",
                    "runner1",
                    ServiceStatusInfo.WARNING,
                    message="",
                    timestamp=datetime(2020, 11, 29),
                ),
            ],
        ),
        (
            "example1",
            [
                dict(
                    service="example0",
                    runner="runner0",
                    state=ServiceStatusInfo.DOWN.value,
                    message="",
                    timestamp=datetime(2020, 9, 1),
                )
            ],
            [],
        ),
        (
            "example2",
            [
                dict(
                    service=f"example{i}",
                    runner=f"runner{j}",
                    state=ServiceStatusInfo.DOWN,
                    message="",
                    timestamp=datetime(2020, 8, 10),
                )
                for i in range(4)
                for j in range(3)
            ],
            [
                ServiceStatusInfo(
                    "example2",
                    "runner0",
                    ServiceStatusInfo.DOWN,
                    message="",
                    timestamp=datetime(2020, 8, 10),
                ),
                ServiceStatusInfo(
                    "example2",
                    "runner1",
                    ServiceStatusInfo.DOWN,
                    message="",
                    timestamp=datetime(2020, 8, 10),
                ),
                ServiceStatusInfo(
                    "example2",
                    "runner2",
                    ServiceStatusInfo.DOWN,
                    message="",
                    timestamp=datetime(2020, 8, 10),
                ),
            ],
        ),
    ],
)
def test_list_all_filtered_by_service(
    raw_collection, repository, service_filter, init_documents, expected
):
    raw_collection.insert_many(map(dict, init_documents))
    # noinspection PyTypeChecker
    assert_that(
        repository.list_all(service=service_filter),
        contains_inanyorder(*expected),
    )


doc_tpl = dict(
    service="example0",
    runner="runner0",
    state=ServiceStatusInfo.OK.value,
    message="",
    timestamp=datetime(2019, 10, 1),
)


@pytest.mark.parametrize(
    "runner_filter, init_documents, expected",
    [
        (
            "runner1",
            [
                dict(
                    doc_tpl,
                    runner="runner0",
                    state=ServiceStatusInfo.WARNING.value,
                    timestamp=datetime(2020, 7, 14),
                ),
                dict(
                    doc_tpl,
                    runner="runner1",
                    state=ServiceStatusInfo.DOWN.value,
                    message="service failure",
                    timestamp=datetime(2020, 1, 20),
                ),
            ],
            [
                ServiceStatusInfo(
                    "example0",
                    "runner1",
                    ServiceStatusInfo.DOWN,
                    message="service failure",
                    timestamp=datetime(2020, 1, 20),
                )
            ],
        ),
        (
            "runner1",
            [
                dict(
                    service="example0",
                    runner="runner0",
                    state=ServiceStatusInfo.OK.value,
                    message="",
                    timestamp=datetime(2019, 12, 31),
                ),
                dict(
                    service="example0",
                    runner="runner1",
                    state=ServiceStatusInfo.OK.value,
                    message="",
                    timestamp=datetime(2019, 12, 30),
                ),
                dict(
                    service="example1",
                    runner="runner0",
                    state=ServiceStatusInfo.WARNING.value,
                    message="",
                    timestamp=datetime(2019, 12, 29),
                ),
                dict(
                    service="example1",
                    runner="runner1",
                    state=ServiceStatusInfo.WARNING.value,
                    message="",
                    timestamp=datetime(2019, 12, 28),
                ),
            ],
            [
                ServiceStatusInfo(
                    "example0",
                    "runner1",
                    ServiceStatusInfo.OK,
                    message="",
                    timestamp=datetime(2019, 12, 30),
                ),
                ServiceStatusInfo(
                    "example1",
                    "runner1",
                    ServiceStatusInfo.WARNING,
                    message="",
                    timestamp=datetime(2019, 12, 28),
                ),
            ],
        ),
        (
            "runner0",
            [
                dict(
                    doc_tpl,
                    state=ServiceStatusInfo.OK.value,
                    timestamp=datetime(2019, 11, 1),
                ),
                dict(
                    doc_tpl,
                    state=ServiceStatusInfo.WARNING.value,
                    timestamp=datetime(2019, 11, 2),
                ),
            ],
            [
                ServiceStatusInfo(
                    "example0",
                    "runner0",
                    ServiceStatusInfo.OK,
                    message="",
                    timestamp=datetime(2019, 11, 1),
                ),
                ServiceStatusInfo(
                    "example0",
                    "runner0",
                    ServiceStatusInfo.WARNING,
                    message="",
                    timestamp=datetime(2019, 11, 2),
                ),
            ],
        ),
        (
            "runner2",
            [
                dict(doc_tpl, service="example0", runner="runner0"),
                dict(doc_tpl, service="example0", runner="runner1"),
                dict(doc_tpl, service="example0", runner="runner0"),
                dict(doc_tpl, service="example1", runner="runner0"),
            ],
            [],
        ),
        (
            "runner2",
            [
                dict(doc_tpl, service=f"example{i}", runner=f"runner{j}")
                for i in range(3)
                for j in range(4)
            ],
            [
                ServiceStatusInfo(
                    "example0",
                    "runner2",
                    ServiceStatusInfo.OK,
                    message="",
                    timestamp=datetime(2019, 10, 1),
                ),
                ServiceStatusInfo(
                    "example1",
                    "runner2",
                    ServiceStatusInfo.OK,
                    message="",
                    timestamp=datetime(2019, 10, 1),
                ),
                ServiceStatusInfo(
                    "example2",
                    "runner2",
                    ServiceStatusInfo.OK,
                    message="",
                    timestamp=datetime(2019, 10, 1),
                ),
            ],
        ),
    ],
)
def test_list_all_filtered_by_runner(
    raw_collection, repository, runner_filter, init_documents, expected
):
    raw_collection.insert_many(map(dict, init_documents))
    # noinspection PyTypeChecker
    assert_that(
        repository.list_all(runner=runner_filter),
        contains_inanyorder(*expected),
    )


@pytest.mark.parametrize(
    "service_filter, runner_filter, init_documents, expected",
    [
        (
            "example1",
            "runner1",
            [
                dict(doc_tpl, service="example0", runner="runner0"),
                dict(doc_tpl, service="example1", runner="runner0"),
                dict(doc_tpl, service="example1", runner="runner1"),
                dict(doc_tpl, service="example1", runner="runner2"),
                dict(doc_tpl, service="example2", runner="runner0"),
                dict(doc_tpl, service="example2", runner="runner1"),
            ],
            [
                ServiceStatusInfo(
                    "example1",
                    "runner1",
                    ServiceStatusInfo.OK,
                    message="",
                    timestamp=datetime(2019, 10, 1),
                )
            ],
        ),
        (
            "example0",
            "runner0",
            [
                dict(doc_tpl, state=ServiceStatusInfo.WARNING.value),
                dict(doc_tpl, state=ServiceStatusInfo.OK.value),
                dict(doc_tpl, state=ServiceStatusInfo.OK.value),
            ],
            [
                ServiceStatusInfo(
                    "example0",
                    "runner0",
                    ServiceStatusInfo.WARNING,
                    message="",
                    timestamp=datetime(2019, 10, 1),
                ),
                ServiceStatusInfo(
                    "example0",
                    "runner0",
                    ServiceStatusInfo.OK,
                    message="",
                    timestamp=datetime(2019, 10, 1),
                ),
                ServiceStatusInfo(
                    "example0",
                    "runner0",
                    ServiceStatusInfo.OK,
                    message="",
                    timestamp=datetime(2019, 10, 1),
                ),
            ],
        ),
        (
            "example1",
            "runner1",
            [
                dict(doc_tpl, service="example0", runner="runner1"),
                dict(doc_tpl, service="example1", runner="runner0"),
                dict(doc_tpl, service="example1", runner="runner2"),
            ],
            [],
        ),
    ],
)
def test_list_all_filtered_by_service_and_runner(
    raw_collection,
    repository,
    service_filter,
    runner_filter,
    init_documents,
    expected,
):
    raw_collection.insert_many(map(dict, init_documents))
    # noinspection PyTypeChecker
    assert_that(
        repository.list_all(service=service_filter, runner=runner_filter),
        contains_inanyorder(*expected),
    )


def test_list_all_items_sorted_by_timestamp(raw_collection, repository):
    timestamps = [
        datetime(2020, 7, 5, 14, 24, 51),
        datetime(2020, 10, 4, 18, 21, 13),
        datetime(2020, 8, 12, 8, 0, 4),
        datetime(2020, 8, 12, 13, 0, 0),
    ]
    raw_collection.insert_many(
        {
            "service": "example",
            "runner": "runner1",
            "state": ServiceStatusInfo.OK.value,
            "message": "",
            "timestamp": ts,
        }
        for ts in timestamps
    )
    assert [it.timestamp for it in repository.list_all()] == [
        datetime(2020, 10, 4, 18, 21, 13),
        datetime(2020, 8, 12, 13, 0, 0),
        datetime(2020, 8, 12, 8, 0, 4),
        datetime(2020, 7, 5, 14, 24, 51),
    ]


def test_list_current_unfiltered(raw_collection, repository):
    raw_collection.insert_many(
        [
            dict(
                service=f"example{i}",
                runner=f"runner{j}",
                state=ServiceStatusInfo.OK.value,
                message="",
                timestamp=datetime(2024, 1, day),
            )
            for i in range(3)
            for j in range(2)
            for day in range(1, 10)
        ]
    )
    expected = [
        ServiceStatusInfo(
            f"example{i}",
            f"runner{j}",
            ServiceStatusInfo.OK,
            message="",
            timestamp=datetime(2024, 1, 9),
        )
        for i in range(3)
        for j in range(2)
    ]
    # noinspection PyTypeChecker
    assert_that(repository.list_current(), contains_inanyorder(*expected))


def test_list_current_filter_by_service(raw_collection, repository):
    raw_collection.insert_many(
        [
            dict(
                service=f"example{i}",
                runner=f"runner{j}",
                state=ServiceStatusInfo.OK.value,
                message="",
                timestamp=datetime(2024, 1, day),
            )
            for i in range(3)
            for j in range(2)
            for day in range(1, 10)
        ]
    )
    expected = [
        ServiceStatusInfo(
            "example1",
            f"runner{j}",
            ServiceStatusInfo.OK,
            message="",
            timestamp=datetime(2024, 1, 9),
        )
        for j in range(2)
    ]
    # noinspection PyTypeChecker
    assert_that(
        repository.list_current(service="example1"),
        contains_inanyorder(*expected),
    )


def test_list_current_filter_by_service_and_runner(raw_collection, repository):
    raw_collection.insert_many(
        [
            dict(
                service=f"example{i}",
                runner=f"runner{j}",
                state=ServiceStatusInfo.OK.value,
                message="",
                timestamp=datetime(2024, 1, day),
            )
            for i in range(3)
            for j in range(2)
            for day in range(1, 10)
        ]
    )
    expected = [
        ServiceStatusInfo(
            "example1",
            "runner0",
            ServiceStatusInfo.OK,
            message="",
            timestamp=datetime(2024, 1, 9),
        )
    ]
    # noinspection PyTypeChecker
    assert_that(
        repository.list_current(service="example1", runner="runner0"),
        contains_inanyorder(*expected),
    )
