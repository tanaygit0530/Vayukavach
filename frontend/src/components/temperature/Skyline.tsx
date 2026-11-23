/** Light grey city skyline (original drawing): blocks, a dome, a minaret and a clock tower. */
export function Skyline({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 320 110" className={className} aria-hidden preserveAspectRatio="xMidYMax slice">
      <defs>
        <linearGradient id="sky-fade" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stopColor="#dfe4e9" stopOpacity="0.2" />
          <stop offset="1" stopColor="#cfd6dd" stopOpacity="0.95" />
        </linearGradient>
      </defs>
      <g fill="url(#sky-fade)">
        <rect x="0" y="62" width="26" height="48" rx="2" />
        <rect x="22" y="44" width="22" height="66" rx="2" />
        <rect x="46" y="70" width="30" height="40" rx="2" />
        {/* dome */}
        <path d="M78 110 V78 H122 V110 Z" />
        <path d="M82 78 C82 56 118 56 118 78 Z" />
        <rect x="98" y="46" width="4" height="12" />
        {/* minaret */}
        <rect x="126" y="38" width="9" height="72" rx="2" />
        <path d="M124 40 H137 L130.5 28 Z" />
        <rect x="138" y="58" width="34" height="52" rx="2" />
        {/* clock tower */}
        <rect x="176" y="30" width="18" height="80" rx="2" />
        <path d="M174 32 H196 L185 16 Z" />
        <circle cx="185" cy="44" r="4" fill="#e9edf1" />
        <rect x="198" y="66" width="26" height="44" rx="2" />
        <rect x="226" y="50" width="20" height="60" rx="2" />
        {/* arch gate */}
        <path d="M250 110 V62 H292 V110 H280 V86 C280 74 262 74 262 86 V110 Z" />
        <rect x="294" y="72" width="26" height="38" rx="2" />
      </g>
    </svg>
  )
}
