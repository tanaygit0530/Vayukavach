/** VayuKavach mark: a shield (kavach) holding three wind lines (vayu). Original artwork. */
export function Logo({ size = 34 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" role="img" aria-label="VayuKavach">
      <path
        d="M20 3 L34 8.5 V19 C34 28 27.8 34.4 20 37 C12.2 34.4 6 28 6 19 V8.5 Z"
        fill="var(--accent)"
        opacity="0.14"
      />
      <path
        d="M20 3 L34 8.5 V19 C34 28 27.8 34.4 20 37 C12.2 34.4 6 28 6 19 V8.5 Z"
        fill="none"
        stroke="var(--accent)"
        strokeWidth="2.4"
        strokeLinejoin="round"
      />
      <g fill="none" stroke="var(--accent)" strokeWidth="2.4" strokeLinecap="round">
        <path d="M12 15 H23 a3 3 0 1 0 -3 -3" />
        <path d="M12 20.5 H27 a3 3 0 1 1 -3 3" />
        <path d="M14 26 H20" />
      </g>
    </svg>
  )
}
