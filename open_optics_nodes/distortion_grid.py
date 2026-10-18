"""Source-pixel grids for lens distortion remapping."""

from open_optics import distortion, pixels


def build_source_grid(width_px, height_px, focal_mm, sensor_width_mm,
                      k1, k2, k3, p1, p2, direction, zoom=1.0):
    """Build the source pixel position for every output pixel.

    width_px, height_px and the returned positions are in pixels (0-based,
    u the column, v the row); focal_mm and sensor_width_mm are in
    millimetres; k1, k2, k3, p1, p2 and zoom are unitless. direction 'remove'
    means the output is the undistorted image: the source is
    distort(x / zoom, y / zoom). direction 'apply' means the output is the
    distorted image: the source is undistort(x, y), and zoom is ignored.
    Returns a list of height_px rows, each a list of width_px (sx, sy) float
    tuples in source pixels. Raises ValueError for any other direction.
    """
    if direction not in ("remove", "apply"):
        raise ValueError("direction must be 'remove' or 'apply', got %r" % (direction,))
    grid = []
    for v in range(height_px):
        row = []
        for u in range(width_px):
            x, y = pixels.pixel_to_lens(u, v, width_px, height_px,
                                        sensor_width_mm, focal_mm)
            if direction == "remove":
                x, y = distortion.distort_point(x / zoom, y / zoom,
                                                k1, k2, k3, p1, p2)
            else:
                x, y = distortion.undistort_point(x, y, k1, k2, k3, p1, p2)
            row.append(tuple(float(c) for c in pixels.lens_to_pixel(
                x, y, width_px, height_px, sensor_width_mm, focal_mm)))
        grid.append(row)
    return grid
