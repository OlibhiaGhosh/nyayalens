/** NyayLens mark: a lens over a paper, with a check inside ("read it closely before you sign").
 *  Same drawing as the favicon in index.html; keep the two in sync. */
export function Logo({ className = "size-10" }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={className} role="img" aria-label="NyayLens">
      <rect width="32" height="32" rx="8" fill="#1d2433" />
      <path d="M8 7.5A1.5 1.5 0 0 1 9.5 6h8.2L22 10.3v12.2a1.5 1.5 0 0 1-1.5 1.5h-11A1.5 1.5 0 0 1 8 22.5z" fill="#faf8f4" />
      <path d="M17.7 6v4.3H22" fill="none" stroke="#1d2433" strokeWidth="1.2" strokeLinejoin="round" />
      <path d="M10.5 11h5M10.5 14h3.5M10.5 17h2.5" stroke="#1d2433" strokeWidth="1.3" strokeLinecap="round" />
      <circle cx="20" cy="19.5" r="5.6" fill="#1d2433" stroke="#faf8f4" strokeWidth="2" />
      <path d="M17.6 19.6l1.6 1.6 3.2-3.3" fill="none" stroke="#17b26a" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M24.3 23.8l3 3" stroke="#faf8f4" strokeWidth="2.6" strokeLinecap="round" />
    </svg>
  );
}
