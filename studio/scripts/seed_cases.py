"""Seeds the Case Sourcing backlog: 30 candidate closed cases for
"The Turning Point", each hand-rated and scored.

blueprint.md Section 8: "closed cases aren't trend-driven the way news is —
building and scoring a curated backlog" comes before automation is worth
building on top of it. This is that manual seed. `case_sourcing.py` reads
from what this script writes; it does not itself decide what's a good case.

`turning_point` is a hypothesis to be verified by the Deep Research and
Fact Checker agents (Day 3), not an assertion — every case here needs a
real research pass before a script gets written on top of it.

Scoring rubric (see score_case()): rewards a clear, dramatic turning point
and strong public-record source availability; penalizes sensitivity
(recency, ongoing controversy, real living defendants/victims prominent in
current discourse) more heavily than it rewards anything else — consistent
with blueprint.md Friction 05 and Section 8's bias toward safer, closed
cases for the first videos.

Run:
    python scripts/seed_cases.py
"""

from studio import db

# (title, jurisdiction, era, turning_point, story_clarity, source_quality, sensitivity_risk)
# ratings are 1-5; sensitivity_risk is inverted (higher = riskier = penalized more)
CANDIDATES: list[tuple[str, str, str, str, int, int, int]] = [
    ("State v. Lizzie Borden", "Massachusetts, US", "1893",
     "The prosecution's own forensic evidence (an axe head with no blood, a "
     "contested timeline) failed to overcome reasonable doubt.", 4, 4, 1),
    ("The Trial of O. J. Simpson (criminal)", "California, US", "1995",
     "A courtroom glove demonstration undermined the prosecution's key "
     "physical evidence.", 5, 5, 4),
    ("Miranda v. Arizona", "US Supreme Court", "1966",
     "The Court's focus on the absence of any warning about the right to "
     "silence during interrogation.", 3, 5, 1),
    ("The Trial of Ted Bundy (Chi Omega case)", "Florida, US", "1979",
     "Bite-mark forensic evidence became the physical link tying him to the "
     "crime scene.", 4, 4, 2),
    ("R v. Sutcliffe (the Yorkshire Ripper)", "United Kingdom", "1981",
     "The jury rejected psychiatric evidence for diminished responsibility.", 3, 3, 2),
    ("The Menendez Brothers trials", "California, US", "1993-1996",
     "A change in how the self-defense/abuse claim was allowed to be argued "
     "produced a hung jury the first time and a conviction the second.", 4, 4, 3),
    ("The Trial of Amanda Knox", "Italy", "2009 + appeals",
     "DNA evidence on a knife and a clasp was successfully challenged as "
     "contaminated on appeal.", 4, 3, 3),
    ("The Central Park Five", "New York, US", "1989-2002",
     "A 2002 confession and DNA match from the actual perpetrator overturned "
     "convictions built on coerced confessions.", 5, 4, 3),
    ("The Trial of Casey Anthony", "Florida, US", "2011",
     "The prosecution's inability to establish a cause of death undercut the "
     "murder charge.", 4, 4, 3),
    ("The Scopes Trial", "Tennessee, US", "1925",
     "Clarence Darrow calling William Jennings Bryan to the stand as a "
     "witness on the Bible.", 4, 4, 1),
    ("The Nuremberg Trials", "International Military Tribunal", "1945-1946",
     "Prosecutors screened the Nazis' own film footage of the camps as "
     "evidence.", 4, 5, 2),
    ("The Trial of Adolf Eichmann", "Israel", "1961",
     "Survivor testimony shifted the proceeding from a legal case into a "
     "historical reckoning.", 4, 4, 2),
    ("Brown v. Board of Education", "US Supreme Court", "1954",
     "The 'doll test' psychological evidence on the effects of segregation "
     "on children.", 3, 5, 2),
    ("The Chicago Seven trial", "Illinois, US", "1969-1970",
     "The judge's handling of defendant Bobby Seale, including binding and "
     "gagging him in court.", 4, 4, 3),
    ("The West Memphis Three case", "Arkansas, US", "1994 + 2007 retesting",
     "New DNA testing years later found none of the physical evidence "
     "matched the convicted teenagers.", 4, 3, 2),
    ("The Trial of Michael Jackson", "California, US", "2005",
     "The accuser's family's credibility collapsed under cross-examination.", 3, 3, 4),
    ("The Trial of O. J. Simpson (civil)", "California, US", "1997",
     "A lower preponderance-of-evidence standard produced the opposite "
     "verdict from the criminal trial.", 4, 4, 3),
    ("The Steven Avery case", "Wisconsin, US", "2005-2007",
     "A prior wrongful-conviction exoneration for the same man complicated "
     "the new murder investigation.", 4, 3, 3),
    ("R v. Derek Bentley", "United Kingdom", "1953 (1998 posthumous pardon)",
     "A disputed phrase — 'let him have it' — was used to convict a man who "
     "did not fire the gun.", 5, 4, 1),
    ("The Trial of Timothy McVeigh", "Oklahoma, US", "1997",
     "A truck axle fragment, traced through a vehicle identification number, "
     "cracked the case.", 4, 4, 3),
    ("The Rodney King officers' trial", "California, US", "1992",
     "Videotape evidence was reframed frame-by-frame by the defense to argue "
     "the force used was justified.", 4, 4, 4),
    ("The Trial of Jodi Arias", "Arizona, US", "2013",
     "Deleted photos recovered from a camera's memory card contradicted her "
     "self-defense account.", 4, 3, 3),
    ("The Boston Strangler case", "Massachusetts, US", "1965 confession / 2013 DNA match",
     "A 2013 DNA match finally connected a case a confession alone couldn't "
     "prove in court decades earlier.", 4, 3, 2),
    ("The Sam Sheppard trials", "Ohio, US", "1954 / 1966",
     "The Supreme Court overturned the first conviction over a prejudicial "
     "media circus; he was acquitted at retrial.", 4, 4, 1),
    ("The Alger Hiss case", "US", "1948-1950",
     "Microfilm hidden inside a hollowed-out pumpkin became the case's "
     "central physical evidence.", 5, 4, 2),
    ("The Birmingham Six", "United Kingdom", "1975 (1991 convictions quashed)",
     "Forensic explosives testing was later found scientifically unreliable, "
     "overturning the convictions.", 4, 4, 2),
    ("The Dreyfus Affair", "France", "1894 / 1899 / 1906",
     "A handwriting comparison years later exposed the real forger behind a "
     "wrongful conviction.", 5, 4, 1),
    ("The Louise Woodward case", "Massachusetts, US", "1997",
     "A judge reduced a jury's murder verdict to manslaughter and time "
     "served, citing doubt about the medical evidence.", 3, 3, 3),
    ("State v. George Zimmerman", "Florida, US", "2013",
     "Jury instructions on self-defense and 'stand your ground' shaped the "
     "verdict.", 3, 3, 5),
    ("The Trial of Scott Peterson", "California, US", "2004",
     "Cell tower records and a pre-murder boat purchase built a "
     "circumstantial case without a confession.", 4, 4, 3),
]


def score_case(story_clarity: int, source_quality: int, sensitivity_risk: int) -> float:
    """0-100ish. Sensitivity is penalized harder than quality is rewarded —
    see the module docstring for why."""
    raw = (story_clarity + source_quality) * 10 - sensitivity_risk * 12
    return max(0.0, min(100.0, float(raw)))


def main() -> None:
    channel_id = db.get_channel_id("The Turning Point")

    scored = [
        (title, jurisdiction, era, turning_point, score_case(clarity, quality, risk))
        for title, jurisdiction, era, turning_point, clarity, quality, risk in CANDIDATES
    ]

    for title, jurisdiction, era, turning_point, score in scored:
        db.upsert_case(channel_id, title, jurisdiction, era, turning_point, score)

    print(f"Seeded {len(scored)} candidate cases.\n")
    print("Top 5 by score:")
    for title, _, era, _, score in sorted(scored, key=lambda c: c[4], reverse=True)[:5]:
        print(f"  {score:5.1f}  {title} ({era})")


if __name__ == "__main__":
    main()
