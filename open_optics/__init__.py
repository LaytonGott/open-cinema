"""Open Optics: physically based lens math for the Open Cinema node pack.

Pure Python (standard library only). The ComfyUI node wrappers come later and live elsewhere.

Units:
    All lengths (focal length, sensor size, focus and subject distance, circle of
    confusion) are in millimetres. Angles are in degrees at the public surface;
    radians appear only via the open_optics.units helpers. Every public function's
    docstring states its units and what it returns.
"""
