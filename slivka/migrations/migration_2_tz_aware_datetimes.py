from datetime import timezone
from zoneinfo import ZoneInfo

import click
from packaging.specifiers import SpecifierSet
from packaging.version import Version
from pymongo import MongoClient

name = "Timezone aware timestamps."
from_versions = SpecifierSet("<0.8.5b6", prereleases=True)
to_version = Version("0.8.5b6")


def apply(database, from_tz=None):
    collection = database['requests']
    for doc in collection.find({"timestamp": {"$exists": True}}):
        new_timestamp = doc["timestamp"] \
            .replace(tzinfo=from_tz) \
            .astimezone(timezone.utc)
        new_completion_time = (
            doc["completion_time"]
                .replace(tzinfo=from_tz)
                .astimezone(timezone.utc)
            if doc.get("completion_time") is not None
            else None
        )
        collection.update_one(
            {"_id": doc["_id"]},
            { "$set": {
                "timestamp": new_timestamp,
                "completion_time": new_completion_time
            }}
        )


@click.command(
    "2-tz-aware-timestamps",
    short_help=f"(ver. {to_version}) {name}",
)
@click.option(
    "--from-timezone",
    metavar="TIMEZONE",
    help="Specify the timezone from which to migrate.",
    show_default="detect from system"
)
@click.argument(
    "mongodb-uri",
    envvar=["SLIVKA_MONGODB_URI", "MONGODB_URI"],
    metavar="CONNECTION_STRING"
)
@click.argument(
    "database",
    envvar=["SLIVKA_MONGODB_DATABASE", "MONGODB_DATABASE"],
    metavar="DATABASE"
)
def tz_aware_timestamps_command(mongodb_uri, database, from_timezone):
    """Change timestamps to UTC.

    This database migration converts all existing datetime values from
    their implicitly assumed local time to Coordinated Universal Time.
    It prepares the database for an update that will exclusively store
    and retrieve timezone-aware datetimes in UTC.

    Specify the mongodb server with CONNECTION_STRING and
    provide a DATABASE which slivka uses.
    """
    mongo = MongoClient(mongodb_uri)
    from_tz = from_timezone and ZoneInfo(from_timezone)
    apply(database=mongo[database], from_tz=from_tz)


if __name__ == "__main__":
    tz_aware_timestamps_command()
