"""Helper for browser tests: the player starts a muted play on load, so tests that start from paused stop it first."""


def pause_players(page):
    """Pause both videos and wait until the play toggle shows the paused state."""
    page.evaluate(
        "() => ['before-video', 'after-video'].forEach("
        "n => document.querySelector('[data-testid=' + n + ']').pause())"
    )
    page.wait_for_function(
        "() => document.querySelector('[data-testid=play-toggle]')"
        ".getAttribute('aria-pressed') === 'false'"
    )
