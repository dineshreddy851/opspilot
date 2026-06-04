import boto3
import click


@click.group()
def main():
    """OpsPilot CLI."""
    pass


@main.command()
def whoami():
    """Show current AWS identity."""
    sts = boto3.client("sts")
    identity = sts.get_caller_identity()
    click.echo(identity)


if __name__ == "__main__":
    main()
