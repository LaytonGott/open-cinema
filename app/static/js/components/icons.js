// Inline framing diagrams: a 48x36 frame with a figure cropped per framing.

const OPEN = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 36" width="48" height="36" aria-hidden="true" focusable="false">';
const FRAME = '<rect x="1" y="1" width="46" height="34" rx="4" fill="none" stroke="currentColor" stroke-width="2"/>';

export const FRAMING_ICONS = {
  "close-up":
    OPEN + FRAME +
    '<circle cx="24" cy="15" r="8" fill="currentColor"/>' +
    '<path d="M6 35 C6 26 14 24 24 24 C34 24 42 26 42 35 Z" fill="currentColor"/></svg>',
  "waist-up":
    OPEN + FRAME +
    '<circle cx="24" cy="10" r="4.5" fill="currentColor"/>' +
    '<path d="M12 35 L12 22 C12 17 17 16 24 16 C31 16 36 17 36 22 L36 35 Z" fill="currentColor"/></svg>',
  "full-body":
    OPEN + FRAME +
    '<circle cx="24" cy="8" r="3" fill="currentColor"/>' +
    '<path d="M20 12.5 L28 12.5 L29 24 L27 24 L27 32 L25 32 L24 25 L23 32 L21 32 L21 24 L19 24 Z" fill="currentColor"/></svg>',
  "wide":
    OPEN + FRAME +
    '<line x1="1" y1="24" x2="47" y2="24" stroke="currentColor" stroke-width="1"/>' +
    '<circle cx="24" cy="19" r="1.5" fill="currentColor"/>' +
    '<path d="M22.6 21 L25.4 21 L25.8 26 L22.2 26 Z" fill="currentColor"/></svg>',
};

// Inline camera move icons: 24x24, stroked with currentColor.

const CAM_OPEN = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">';

export const CAMERA_ICONS = {
  "static":
    CAM_OPEN +
    '<rect x="5" y="4" width="10" height="7" rx="1"/><path d="M15 6.5 L19 5 V10 L15 8.5"/>' +
    '<path d="M10 11 V14 M10 14 L5 21 M10 14 L15 21 M10 14 V21"/></svg>',
  "dolly-in":
    CAM_OPEN +
    '<rect x="8" y="8" width="8" height="8" rx="1"/>' +
    '<path d="M3 3 L7 7 M7 4.5 V7 H4.5 M21 3 L17 7 M17 4.5 V7 H19.5 M3 21 L7 17 M7 19.5 V17 H4.5 M21 21 L17 17 M17 19.5 V17 H19.5"/></svg>',
  "dolly-out":
    CAM_OPEN +
    '<rect x="8" y="8" width="8" height="8" rx="1"/>' +
    '<path d="M7 7 L3 3 M3 5.5 V3 H5.5 M17 7 L21 3 M21 5.5 V3 H18.5 M7 17 L3 21 M3 18.5 V21 H5.5 M17 17 L21 21 M21 18.5 V21 H18.5"/></svg>',
  "pan-left":
    CAM_OPEN + '<path d="M20 12 H4 M9 7 L4 12 L9 17"/></svg>',
  "pan-right":
    CAM_OPEN + '<path d="M4 12 H20 M15 7 L20 12 L15 17"/></svg>',
  "tilt-up":
    CAM_OPEN + '<path d="M12 20 V4 M7 9 L12 4 L17 9"/></svg>',
  "orbit":
    CAM_OPEN +
    '<circle cx="12" cy="12" r="1.5"/>' +
    '<path d="M19 12 A7 7 0 1 1 12 5 M12 5 L15 3 M12 5 L15 7.5"/></svg>',
  "handheld":
    CAM_OPEN + '<path d="M2 12 C4 6 6 6 8 12 C10 18 12 18 14 12 C16 6 18 6 20 12 L22 14"/></svg>',
};
