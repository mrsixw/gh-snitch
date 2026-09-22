"""A clear-and-redraw refresh loop for ``--watch``.

Nothing in here knows about GitHub, operatives or tables: it calls a function,
stamps the time, sleeps and repeats. That is deliberate. The same loop is wanted
across the sibling CLIs (mrsixw/five-clis#11), and keeping it free of gh-snitch
specifics is what lets it move into the template without a rewrite.
"""

import time
from datetime import datetime

import click

__all__ = ["MIN_WATCH_INTERVAL", "run_watch"]

#: The floor on ``--interval``. Every refresh is a full sweep, costing one API
#: request per surveilled period, and the hourly GraphQL budget is shared with
#: everything else the token does. A minute keeps a long-running watch well
#: inside it; faster than that buys nothing, since contribution counts rarely
#: move second to second.
MIN_WATCH_INTERVAL = 60


def run_watch(  # noqa: PLR0913
    refresh,
    interval,
    *,
    on_error=(),
    clear=click.clear,
    sleep=time.sleep,
    now=datetime.now,
):
    """Call ``refresh`` every ``interval`` seconds until interrupted.

    Each cycle clears the screen, runs ``refresh``, then prints a footer saying
    when it ran and when the next one is due. Ctrl-C ends the loop cleanly,
    whether it lands mid-refresh or mid-sleep.

    Args:
        refresh: Zero-argument callable that renders one cycle.
        interval: Seconds to wait between the end of one cycle and the start
            of the next.
        on_error: Exception types that should not end the watch. The error is
            reported and the next cycle tries again, so a dropped connection or
            a spent rate limit costs one refresh rather than the session.
            Anything else propagates.
        clear: Clears the screen. Injectable for tests.
        sleep: Waits between cycles. Injectable for tests.
        now: Returns the current time. Injectable for tests.
    """
    error_types = tuple(on_error)
    try:
        while True:
            clear()
            try:
                refresh()
            except error_types as error:
                click.echo(str(error), err=True)
                click.echo("↻  Holding position; retrying next cycle.", err=True)
            click.echo(
                f"\n🕒 Last refreshed {now():%H:%M:%S} · next sweep in {interval}s"
                " · Ctrl-C to stand down",
                err=True,
            )
            sleep(interval)
    except KeyboardInterrupt:
        click.echo("\n🕶️  Operative went dark. Signing off.", err=True)
