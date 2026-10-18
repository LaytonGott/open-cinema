"""Exposure maths: unitless f-numbers in, photographic stops out."""

import math

from open_optics.validation import require_finite, require_positive


def f_number_to_stops(f_number):
    """Convert an f-number to stops.

    f_number is unitless and greater than 0. Returns 2 * log2(f_number) in
    stops: 0 for f/1, 1 for f/1.414, 2 for f/2.
    """
    return 2 * math.log2(require_positive("f_number", f_number))


def stops_to_f_number(stops):
    """Convert stops to an f-number.

    stops is in stops (0 is f/1) and must be finite. Returns 2 ** (stops / 2),
    the unitless f-number; the inverse of f_number_to_stops.
    """
    return 2 ** (require_finite("stops", stops) / 2)


def stop_difference(from_f_number, to_f_number):
    """Exposure change in stops between two apertures.

    from_f_number and to_f_number are unitless and greater than 0. Returns
    2 * log2(to_f_number / from_f_number) in stops: positive when the second
    aperture lets in less light, negative when it lets in more.
    """
    n_from = require_positive("from_f_number", from_f_number)
    n_to = require_positive("to_f_number", to_f_number)
    return 2 * math.log2(n_to / n_from)
