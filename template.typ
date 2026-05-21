// ─────────────────────────────────────────────────────────────────────────────
// template.typ — Single-column, ATS-optimised resume
//
// Layout geometry is injected at compile time via --input flags so that
// agent.py can programmatically tighten the document to fit 1 page without
// re-editing this file.
//
// Required --input flags (all numeric strings):
//   font_size     float  pt units   default 11
//   top_margin    float  cm units   default 2.0
//   bottom_margin float  cm units   default 2.0
//   side_margin   float  cm units   default 1.5
//   line_spacing  float  multiplier default 1.15
//
// JSON data is read from the fixed relative path:
//   ./workspace/tailored_resume.json
// ─────────────────────────────────────────────────────────────────────────────

// ── Layout parameters ────────────────────────────────────────────────────────
#let fs          = float(sys.inputs.at("font_size",     default: "11"))   * 1pt
#let top-mg      = float(sys.inputs.at("top_margin",    default: "2.0"))  * 1cm
#let bot-mg      = float(sys.inputs.at("bottom_margin", default: "2.0"))  * 1cm
#let side-mg     = float(sys.inputs.at("side_margin",   default: "1.5"))  * 1cm
#let leading-mul = float(sys.inputs.at("line_spacing",  default: "1.15"))

// ── Page & typography setup ──────────────────────────────────────────────────
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
  leading:  leading-mul * 0.65em,
  justify:  false,
  spacing:  leading-mul * 0.65em,
)

// Bullet list — readable inter-item spacing
#set list(
  indent:      0.8em,
  body-indent: 0.4em,
  spacing:     leading-mul * 0.75em,
)

// Links: display text IS the URL string so ATS reads the actual address,
// while humans see a styled blue underlined clickable link.
#show link: it => text(fill: rgb("#1155cc"))[#underline(offset: 2pt, it)]

// Strip https://www. / https:// / trailing slash for clean display text
#let display-url(url) = {
  url
    .replace("https://www.", "")
    .replace("http://www.", "")
    .replace("https://", "")
    .replace("http://", "")
    .trim("/", at: end)
}

// ── Load resume data ─────────────────────────────────────────────────────────
#let r = json("./workspace/tailored_resume.json")

// ── Helper: section header with rule ─────────────────────────────────────────
#let section(title) = {
  v(0.55em)
  block(width: 100%, below: 0.2em)[
    #text(weight: "bold", size: fs + 0.5pt, tracking: 0.04em)[#upper(title)]
  ]
  line(length: 100%, stroke: 0.45pt + rgb("#000000"))
  v(0.08em)
}

// ── Helper: two-column entry header (title left, date right) ─────────────────
// above: 0.25em — a controlled ~1mm gap that replaces Typst's implicit
// par.spacing (~0.75em which was too loose). Gives intentional breathing room
// without floating the title away from its section.
#let entry-header(left-text, right-text) = {
  block(width: 100%, above: 0.25em, below: 0.45em)[
    #left-text #h(1fr) #right-text
  ]
}

// ═══════════════════════════════════════════════════════════════════════════════
// HEADER — Name + contact line
// ═══════════════════════════════════════════════════════════════════════════════

#align(center)[
  #text(size: fs + 7pt, weight: "bold", tracking: 0.06em)[#r.contact.name]
  #v(0.18em)

  // Line 1 — basic contact info
  #text(size: fs - 0.5pt)[
    #(r.contact.location, r.contact.phone, r.contact.email).join("  |  ")
  ]

  // Line 2 — profile links (only rendered when at least one URL is present)
  #let li-part = if r.contact.at("linkedin", default: none) != none {
    (link(r.contact.linkedin)[#display-url(r.contact.linkedin)],)
  } else { () }

  #let gh-part = if r.contact.at("github", default: none) != none {
    (link(r.contact.github)[#display-url(r.contact.github)],)
  } else { () }

  #let profile-links = li-part + gh-part
  #if profile-links.len() > 0 [
    #v(0.05em)
    #text(size: fs - 0.5pt)[
      #profile-links.join("  |  ")
    ]
  ]
]

// ═══════════════════════════════════════════════════════════════════════════════
// SUMMARY
// ═══════════════════════════════════════════════════════════════════════════════

#section("Summary")
#text(size: fs)[#r.summary]

// ═══════════════════════════════════════════════════════════════════════════════
// TECHNICAL SKILLS
// — Each category on its own line with clear vertical separation
// ═══════════════════════════════════════════════════════════════════════════════

#section("Technical Skills")
#for sg in r.skills [
  #block(above: 0.28em, below: 0.2em)[
    #text(weight: "bold")[#sg.category:] #sg.skills.join(", ")
  ]
]

// ═══════════════════════════════════════════════════════════════════════════════
// EXPERIENCE
// ═══════════════════════════════════════════════════════════════════════════════

#section("Experience")
#for exp in r.experience {
  entry-header(
    [*#exp.role* — #exp.company, #exp.location],
    [#text(style: "italic")[#exp.start_date – #exp.end_date]],
  )
  list(..exp.bullets.map(b => [#b]))
  v(0.15em)
}

// ═══════════════════════════════════════════════════════════════════════════════
// SELECT PROJECTS
// — Extra vertical gap between entries to prevent visual merging
// ═══════════════════════════════════════════════════════════════════════════════

#section("Select Projects")
#for proj in r.projects {
  entry-header(
    [*#proj.name* — #proj.role],
    [#text(style: "italic")[#proj.status]],
  )
  list(..proj.bullets.map(b => [#b]))
  v(0.38em)
}

// ═══════════════════════════════════════════════════════════════════════════════
// EDUCATION
// ═══════════════════════════════════════════════════════════════════════════════

#section("Education")
#for edu in r.education {
  entry-header(
    [*#edu.degree*, #edu.institution — #edu.location],
    [#text(style: "italic")[#edu.graduation_date]],
  )
}
