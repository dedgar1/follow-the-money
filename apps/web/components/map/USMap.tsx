"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

// State abbreviation lookup by full name
const STATE_ABBR: Record<string, string> = {
  Alabama: "AL", Alaska: "AK", Arizona: "AZ", Arkansas: "AR",
  California: "CA", Colorado: "CO", Connecticut: "CT", Delaware: "DE",
  Florida: "FL", Georgia: "GA", Hawaii: "HI", Idaho: "ID",
  Illinois: "IL", Indiana: "IN", Iowa: "IA", Kansas: "KS",
  Kentucky: "KY", Louisiana: "LA", Maine: "ME", Maryland: "MD",
  Massachusetts: "MA", Michigan: "MI", Minnesota: "MN", Mississippi: "MS",
  Missouri: "MO", Montana: "MT", Nebraska: "NE", Nevada: "NV",
  "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM",
  "New York": "NY", "North Carolina": "NC", "North Dakota": "ND",
  Ohio: "OH", Oklahoma: "OK", Oregon: "OR", Pennsylvania: "PA",
  "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD",
  Tennessee: "TN", Texas: "TX", Utah: "UT", Vermont: "VT",
  Virginia: "VA", Washington: "WA", "West Virginia": "WV",
  Wisconsin: "WI", Wyoming: "WY",
};

// [stateName, defaultParty (from mockup class), svgPath]
const STATES: [string, "dem" | "rep", string][] = [
  ["Maine",          "rep", "M830 80 L860 80 L865 110 L835 115 Z"],
  ["New Hampshire",  "rep", "M820 115 L840 110 L845 135 L820 138 Z"],
  ["Vermont",        "dem", "M800 130 L820 125 L822 145 L800 148 Z"],
  ["New York",       "dem", "M780 140 L810 135 L812 165 L778 168 Z"],
  ["Massachusetts",  "dem", "M812 165 L842 160 L844 185 L810 188 Z"],
  ["Connecticut",    "dem", "M800 188 L820 184 L822 205 L798 208 Z"],
  ["Rhode Island",   "dem", "M820 195 L838 191 L840 212 L818 215 Z"],
  ["New Jersey",     "dem", "M780 200 L802 196 L804 225 L778 228 Z"],
  ["Pennsylvania",   "dem", "M755 220 L780 215 L782 250 L752 255 Z"],
  ["Delaware",       "dem", "M772 250 L795 245 L797 275 L770 278 Z"],
  ["Maryland",       "dem", "M752 268 L775 263 L777 292 L750 295 Z"],
  ["Virginia",       "rep", "M730 280 L758 275 L762 320 L728 325 Z"],
  ["North Carolina", "rep", "M710 320 L740 315 L744 365 L708 370 Z"],
  ["South Carolina", "rep", "M690 365 L720 360 L724 410 L688 415 Z"],
  ["Georgia",        "rep", "M660 385 L692 380 L696 435 L658 440 Z"],
  ["Florida",        "rep", "M640 400 L665 395 L668 455 L637 460 Z"],
  ["Alabama",        "rep", "M605 350 L638 344 L642 395 L602 400 Z"],
  ["Mississippi",    "rep", "M570 340 L606 334 L610 385 L568 390 Z"],
  ["West Virginia",  "rep", "M680 300 L712 294 L716 322 L678 328 Z"],
  ["Ohio",           "rep", "M540 220 L580 214 L584 265 L538 270 Z"],
  ["Indiana",        "rep", "M500 218 L542 212 L546 260 L498 265 Z"],
  ["Illinois",       "dem", "M455 200 L500 194 L504 242 L453 248 Z"],
  ["Wisconsin",      "dem", "M415 185 L457 178 L461 228 L413 234 Z"],
  ["Minnesota",      "dem", "M375 170 L417 163 L421 213 L373 219 Z"],
  ["Kentucky",       "rep", "M455 248 L500 242 L504 295 L453 300 Z"],
  ["Michigan",       "rep", "M415 230 L457 223 L461 270 L413 276 Z"],
  ["Tennessee",      "rep", "M500 265 L540 258 L544 308 L498 314 Z"],
  ["Iowa",           "rep", "M375 220 L415 213 L419 268 L373 274 Z"],
  ["South Dakota",   "rep", "M335 215 L377 208 L381 258 L333 264 Z"],
  ["North Dakota",   "rep", "M335 165 L377 158 L381 208 L333 215 Z"],
  ["Nebraska",       "rep", "M295 218 L337 211 L341 265 L293 272 Z"],
  ["Missouri",       "rep", "M375 268 L415 261 L419 318 L373 324 Z"],
  ["Kansas",         "rep", "M335 268 L377 261 L381 318 L333 325 Z"],
  ["Oklahoma",       "rep", "M295 295 L337 288 L341 348 L293 355 Z"],
  ["Arkansas",       "rep", "M415 318 L455 311 L459 368 L413 375 Z"],
  ["Texas",          "rep", "M295 355 L340 348 L344 410 L293 417 Z"],
  ["Louisiana",      "rep", "M455 368 L500 361 L504 418 L453 425 Z"],
  ["Colorado",       "rep", "M255 220 L297 213 L301 275 L253 282 Z"],
  ["Utah",           "rep", "M215 240 L257 233 L261 298 L213 305 Z"],
  ["Nevada",         "rep", "M175 258 L217 251 L221 318 L173 325 Z"],
  ["Wyoming",        "rep", "M215 180 L257 173 L261 235 L213 242 Z"],
  ["Idaho",          "rep", "M175 175 L217 168 L221 242 L173 249 Z"],
  ["Montana",        "rep", "M255 155 L297 148 L301 215 L253 222 Z"],
  ["Oregon",         "rep", "M215 138 L257 131 L261 172 L213 179 Z"],
  ["Washington",     "dem", "M165 100 L215 93 L219 175 L163 182 Z"],
  ["California",     "dem", "M105 260 L175 253 L179 380 L103 388 Z"],
  ["Arizona",        "rep", "M173 325 L215 318 L219 382 L171 389 Z"],
  ["New Mexico",     "rep", "M213 372 L255 365 L259 422 L211 429 Z"],
  ["Alaska",         "rep", "M100 460 L160 455 L165 510 L98 515 Z"],
  ["Hawaii",         "dem", "M200 490 L245 486 L248 520 L198 524 Z"],
];

// Centroid approximation for label positioning
function centroid(d: string): { x: number; y: number } {
  const nums = d
    .replace(/[MLZ]/g, " ")
    .trim()
    .split(/\s+/)
    .map(Number)
    .filter((n) => !isNaN(n));
  let sx = 0, sy = 0, count = 0;
  for (let i = 0; i < nums.length - 1; i += 2) {
    sx += nums[i]; sy += nums[i + 1]; count++;
  }
  return { x: sx / count, y: sy / count };
}

interface Props {
  /** If provided, highlight states matching the query */
  activeState?: string;
}

export function USMap({ activeState }: Props) {
  const router = useRouter();
  const [hovered, setHovered] = useState<string | null>(null);
  const [tipPos, setTipPos] = useState({ x: 0, y: 0 });

  function handleClick(stateName: string) {
    const abbr = STATE_ABBR[stateName];
    if (abbr) router.push(`/results?state=${abbr}`);
  }

  function handleMouseMove(e: React.MouseEvent<SVGPathElement>, stateName: string) {
    const rect = (e.currentTarget.closest("svg") as SVGSVGElement).getBoundingClientRect();
    setTipPos({ x: e.clientX - rect.left, y: e.clientY - rect.top });
    setHovered(stateName);
  }

  return (
    <div style={{ position: "relative", width: "100%" }}>
      <svg
        viewBox="0 0 900 550"
        style={{ width: "100%", display: "block" }}
        aria-label="United States map — click a state to see representatives"
      >
        {STATES.map(([name, party, path]) => {
          const isActive = activeState
            ? STATE_ABBR[name] === activeState.toUpperCase()
            : false;
          const c = centroid(path);
          const abbr = STATE_ABBR[name] ?? "";
          return (
            <g key={name}>
              <path
                d={path}
                className={`state-path ${party}${isActive ? " active" : ""}`}
                onClick={() => handleClick(name)}
                onMouseMove={(e) => handleMouseMove(e, name)}
                onMouseLeave={() => setHovered(null)}
                aria-label={name}
              />
              {abbr.length <= 2 && (
                <text
                  x={c.x}
                  y={c.y + 4}
                  textAnchor="middle"
                  fontSize={7}
                  fill="rgba(245,240,232,0.5)"
                  style={{ pointerEvents: "none", userSelect: "none" }}
                >
                  {abbr}
                </text>
              )}
            </g>
          );
        })}
      </svg>

      {/* Tooltip */}
      {hovered && (
        <div
          style={{
            position: "absolute",
            left: tipPos.x + 10,
            top: tipPos.y - 30,
            background: "#1c1c1c",
            border: "1px solid #444",
            borderRadius: 4,
            padding: "4px 8px",
            fontSize: 11,
            color: "var(--white)",
            pointerEvents: "none",
            whiteSpace: "nowrap",
            zIndex: 10,
          }}
        >
          {hovered}
        </div>
      )}
    </div>
  );
}
