from django.core.management.base import BaseCommand, CommandError

from api.services.facility_import import import_official_facilities
from api.services.resources import ResourceAlreadyExists, ResourceDatabaseUnavailable


class Command(BaseCommand):
    help = (
        "Dry-run or import the curated public Odisha facility entries. "
        "Use --apply to write records."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Write imported or updated records to MongoDB.",
        )

    def handle(self, *args, **options):
        try:
            summary = import_official_facilities(apply=options["apply"])
        except ResourceDatabaseUnavailable as exc:
            raise CommandError("The emergency resources collection is unavailable.") from exc
        except ResourceAlreadyExists as exc:
            raise CommandError(
                "A duplicate facility conflicts with a unique MongoDB index."
            ) from exc

        mode = "Applied" if options["apply"] else "Dry run"
        self.stdout.write(
            f"{mode}: created={summary['created']}, updated={summary['updated']}, "
            f"unchanged={summary['unchanged']}, "
            f"preserved_verified={summary['preserved_verified']}."
        )
        if not options["apply"]:
            self.stdout.write("No records were written. Re-run with --apply to import.")
