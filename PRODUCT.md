# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- A teacher prepares and runs a 45-minute Long Valley lesson, manages joining and site handoff, and projects selected group evidence for discussion.
- Two neighbouring student groups work on one device per group. They test how a railway crossing's construction could affect spring nesting habitat and try their design at the partner site.

## Product Purpose

SiMetropolis Edu helps students explain a railway planning decision using evidence from a model of Long Valley. The lesson gives groups two fixed stations and asks where and how to cross. A group can show which construction works overlap modelled habitat and explain what changes when it tries the same crossing at a different site.

## Positioning

The lesson combines two controlled comparisons. Groups compare the same spring site with and without their proposed works. During **Pass the City**, each group carries its own crossing to the partner site so it can investigate how different wetland geography affects the proposal.

## Operating Context

- The teacher runs the classroom service on a Mac or Windows computer and teaches in the browser. The private teacher view controls the session. A separate projection view shows joining details or selected comparisons.
- Groups join from a browser on the classroom network by QR code, link, or short code. Site A has a central wetland. Site B has a wetland closer to the river. One group starts at each site.
- **Start Lesson** starts the countdown immediately. If the classroom network drops, Edu withholds joining details and retries while the countdown continues. Reopening the teacher view while the service is running preserves the class. If a group loses access to its work, the teacher can issue a one-use rejoin code for the group's starting site.
- The Long Valley classroom is the product focus. The broader Northern Metropolis simulator is retained in the repository as source reference.

## Capabilities and Constraints

- Each crossing combines an alignment, an elevated or tunnel crossing, and a construction access route. Groups can test, compare, replay, and reset a crossing.
- The spring maps show where surface works such as access routes, bridge supports, and tunnel entrances overlap modelled nesting habitat. The classroom uses imagined sites and schematic habitat footprints to illustrate possible disturbance.
- **Share comparison** captures the tested design and both maps for the teacher to project. The comparison stays as shared while the group continues working.
- During **Pass the City**, each group takes its saved crossing, or its last tested crossing if it skipped saving. The group keeps its chosen language and can edit the crossing at the partner site.

## Evidence on Hand

- [Classroom guide](classroom/README.md) documents the teacher and group workflows and lists browser and device verification procedures.
- [Investigation model](classroom/investigation.py) defines the site geometry, crossing footprints, and overlap rules.
- [Issue 3 screenshots](docs/evidence/issue-3/) show examples of both sites, bilingual views, a phone layout, and tested crossing evidence.

## Product Principles

- Make each finding traceable to the work and habitat shown on the map.
- Keep the baseline tied to the same site and season so groups can isolate the effect of their proposed works.
- Preserve group choices through site handoff and recovery, and preserve shared evidence for class discussion.
- Give teachers control over the lesson timeline and what appears on the projector while groups continue investigating.

## Accessibility & Inclusion

- The classroom supports English and Traditional Chinese. The teacher sets the starting language, and groups can switch languages without losing their edits.
- Groups can inspect mapped overlaps with a pointer or keyboard. The **Possible disturbance** list also describes the findings in text.
