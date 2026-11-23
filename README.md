# Personal

## Task tracker

- `task-tracker/index.html`: the tracker in its classic look (the live "Praveen's Tasks" artifact).
- `task-tracker-glass/index.html`: the same tracker in an Apple-style glass design (see `task-tracker-glass/DESIGN.md`).

Both pages are built from `task-tracker/src/`:

- `app.js`: all the logic, shared by both pages.
- `classic.css` and `glass.css`: one stylesheet per look.
- `seed.json`: starting data, used only when a page's database is empty.

Edit the files in `src/`, then run `python3 task-tracker/build.py`.

### Work view

- Every work task can have a **project**, a **deadline** and a **high-priority** flag.
- **Timeline** groups tasks into Overdue, Today, This week, Coming up and Later. **Projects** shows one card per project.
- In quick add, `@takeda` sets the project (a prefix is enough), `fri` / `tomorrow` / `Dec 5` sets the date, and `!` marks it high priority.

### Inbox scan (Outlook, Teams, Wispr Flow)

- Skips messages addressed by name to someone else ("Hi Akash, …", "@Rokesh …").
- Tells Claude whether each Teams message came from a 1:1 chat, a group chat or a channel, and keeps each conversation together.
- Claude must name who owns each action item. Anything owned by someone else is dropped.
- Drops suggestions that match open tasks, tasks done in the last 30 days, or suggestions you dismissed. The match uses key words, so rewordings are still caught.
- Remembers which messages it has already read, so a later scan doesn't suggest them again.
