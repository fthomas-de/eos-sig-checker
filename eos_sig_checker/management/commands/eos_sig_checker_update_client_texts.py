from django.core.management.base import BaseCommand, CommandError

from eos_sig_checker import client_text


class Command(BaseCommand):
    help = "Fetch the EVE client texts of every language whose file changed in the archive."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Fetch every language, changed or not.")

    def handle(self, *args, **options):
        try:
            updated = client_text.update(force=options["force"])
        except client_text.ClientTextError as error:
            raise CommandError(str(error)) from error
        self.stdout.write(f"Updated: {', '.join(updated)}" if updated else "Nothing changed.")
