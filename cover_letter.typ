// ─────────────────────────────────────────────────────────────────────────────
// cover_letter.typ — Professional cover letter template
//
// Reads data from: ./workspace/cover_letter_data.json
// Expected JSON shape:
//   {
//     "name":       string,
//     "location":   string,
//     "phone":      string,
//     "email":      string,
//     "linkedin":   string | null,
//     "github":     string | null,
//     "date":       string,   // e.g. "June 17, 2026"
//     "greeting":   string,   // e.g. "Dear Hiring Manager,"
//     "paragraphs": string[], // exactly 3 body paragraphs (1-page limit)
//     "closing":    string    // e.g. "Sincerely,"
//   }
// ─────────────────────────────────────────────────────────────────────────────

// Layout geometry is injected at compile time via --input flags so that
// agent.py can programmatically tighten the document to fit 1 page.
//
// Required --input flags (all numeric strings):
//   font_size     float  pt units   default 11
//   top_margin    float  cm units   default 2.2
//   bottom_margin float  cm units   default 2.2
//   side_margin   float  cm units   default 2.8
//   line_spacing  float  multiplier default 1.0

#let fs          = float(sys.inputs.at("font_size",     default: "11"))   * 1pt
#let top-mg      = float(sys.inputs.at("top_margin",    default: "2.2"))  * 1cm
#let bot-mg      = float(sys.inputs.at("bottom_margin", default: "2.2"))  * 1cm
#let side-mg     = float(sys.inputs.at("side_margin",   default: "2.8"))  * 1cm
#let leading-mul = float(sys.inputs.at("line_spacing",  default: "1.0"))

// ── Page & typography ────────────────────────────────────────────────────────

#set page(
  paper:  "us-letter",
  margin: (top: top-mg, bottom: bot-mg, left: side-mg, right: side-mg),
)

#set text(
  font:     ("New Computer Modern", "Libertinus Serif", "Georgia", "Times New Roman"),
  size:     fs,
  fallback: true,
  hyphenate: false,
)

#set par(
  leading:  0.72em * leading-mul,
  justify:  true,
  spacing:  0.72em * leading-mul,
)

// Links styled in blue underline — same as resume template
#show link: it => text(fill: rgb("#1155cc"))[#underline(offset: 2pt, it)]

// ── URL display helper ───────────────────────────────────────────────────────
#let display-url(url) = {
  url
    .replace("https://www.", "")
    .replace("http://www.", "")
    .replace("https://", "")
    .replace("http://", "")
    .trim("/", at: end)
}

// ── Load letter data ─────────────────────────────────────────────────────────
#let d = json("./workspace/cover_letter_data.json")

// ═══════════════════════════════════════════════════════════════════════════════
// HEADER — Name + contact (matches resume header styling)
// ═══════════════════════════════════════════════════════════════════════════════

#align(center)[
  #text(size: 18pt, weight: "bold", tracking: 0.06em)[#d.name]
  #v(0.18em)

  #text(size: 10.5pt)[
    #(d.location, d.phone, d.email).join("  |  ")
  ]

  #let li-part = if d.at("linkedin", default: none) != none and d.linkedin != "" {
    (link(d.linkedin)[#display-url(d.linkedin)],)
  } else { () }

  #let gh-part = if d.at("github", default: none) != none and d.github != "" {
    (link(d.github)[#display-url(d.github)],)
  } else { () }

  #let profile-links = li-part + gh-part
  #if profile-links.len() > 0 [
    #v(0.05em)
    #text(size: 10.5pt)[
      #profile-links.join("  |  ")
    ]
  ]
]

// Thin rule under header — mirrors resume style
#v(0.4em * leading-mul)
#line(length: 100%, stroke: 0.45pt + rgb("#000000"))
#v(1.4em * leading-mul)

// ═══════════════════════════════════════════════════════════════════════════════
// DATE
// ═══════════════════════════════════════════════════════════════════════════════

#text(size: 10.5pt)[#d.date]

#v(1.4em * leading-mul)

// ═══════════════════════════════════════════════════════════════════════════════
// SALUTATION
// ═══════════════════════════════════════════════════════════════════════════════

#text[#d.greeting]

#v(1.0em * leading-mul)

// ═══════════════════════════════════════════════════════════════════════════════
// BODY PARAGRAPHS
// ═══════════════════════════════════════════════════════════════════════════════

#for para in d.paragraphs [
  #par(justify: true, first-line-indent: 0pt)[#para]
  #v(0.9em * leading-mul)
]

// ═══════════════════════════════════════════════════════════════════════════════
// CLOSING + SIGNATURE
// ═══════════════════════════════════════════════════════════════════════════════

#text[#d.closing]

#v(0.4em)
#let has-sig = sys.inputs.at("has_sig", default: "0") == "1"
#if has-sig {
  image("./signature.png", width: 4.5cm)
  v(-0.4em)
} else {
  v(1.6em)
}

#text(weight: "bold")[#d.name]
