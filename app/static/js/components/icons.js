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
