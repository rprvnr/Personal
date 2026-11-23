# Praveen's Tasks: Glass

A second look for the tracker. It has the same features and logic as `task-tracker/`, restyled after Apple's Human Interface Guidelines (iOS "Liquid Glass") and the Goldman Sachs design system's approach to dense, precise interfaces.

Built from `task-tracker/src/` (shared `app.js`, its own `glass.css`) with `python3 task-tracker/build.py`.

## What we took from Apple

| Principle | How it shows up here |
|---|---|
| **Content first, controls on a floating glass layer** | The tab switcher, the add button, the floating add button and the undo toast sit on translucent, blurred glass above the lists. The lists themselves stay quiet. |
| **One consistent material** | Every glass surface uses the same recipe: a translucent fill, `saturate(180%) blur(28px)`, a 0.5px light edge and a highlight on the top edge. |
| **Concentric shapes** | The capsule tab switcher has capsule tabs inside it. Cards have 22px corners, with rows and chips nested inside them. |
| **Large titles, type-led hierarchy** | A 34pt date title, 20pt section titles, 17pt rows and 13pt secondary text, in SF Pro. |
| **System colours that carry meaning** | Orange is due today, red is overdue or high priority, green is done, yellow is the Today picks, and each project has its own colour. Colour is used for nothing else. |
| **Inset grouped lists** | Rounded cards with hairline separators that are inset to start where the text starts, as in Reminders and Settings. |
| **Touch targets of 44pt or more** | The add buttons, checkboxes, tab segments, chips and day arrows are all at least 34–58px. |
| **Respect user settings** | Light and dark mode follow the system. Reduced motion turns off the animations. Reduced transparency swaps the glass for solid fills. |

## What we took from Goldman Sachs' design system (GS UX)

- **Information density without noise.** The Work timeline shows due date, project and priority on one line under each task, so nothing important needs an extra tap.
- **Precision.** Numbers use tabular figures. Relative dates ("Tomorrow", "Thu", "3d overdue") make urgency readable at a glance.
- **Neutral base, purposeful accent.** Greys carry the structure. Only status and project identity get colour.
- **Predictable grouping.** Work sorts the same way in every group: high priority first, then by deadline, then in your own order.

## Layout

1. A sticky glass bar with the tab switcher (Personal / Work / Shop / Daily) and a **+** button that is always reachable.
2. A large title showing today's date and the done tally.
3. Personal: the routine chips, then Now / Next / Later / Done.
4. Work: a **Timeline | Projects** switch.
   - Timeline groups: Overdue, Today, This week, Coming up, Later.
   - Projects shows a card per project, with its count and next deadline.
5. A floating **+** button that sits above the phone app's bottom bar.
