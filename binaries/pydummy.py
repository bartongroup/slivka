import sys

import click


@click.command()
@click.option("-m", "--message")
@click.option("-e", "--error")
@click.option("-r", "--return_code", default=0)
@click.option("-o", "--out")
@click.option("-n", default=0)
def cli(message, error, return_code, out, n):
    click.echo(message)
    click.echo(error, file=sys.stderr)
    with open("DefaultOutput.txt", "w") as f:
        f.write("foo bar foo bar")
    with open(out, "w") as f:
        f.write("specific output file")
    for i in range(n):
        with open("part%03d.txt" % i, "w") as f:
            f.write("I'm file number %d" % i)

    sys.exit(return_code)

if __name__ == '__main__':
    cli()
