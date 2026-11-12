# Answer internal audit's questions

Goal: draft an answer to a question from internal audit, from the folder, for a person to send.

Reads: the question, the folder, and the plan's "Internal audit will test" column.

Writes: a draft answer outside closure/, handed to the consultant. Never closure/record.md: internal audit enters its own reference.

## Rules

- Each answer points at a file and a page with a cite, such as `[EV-22 p1]`.
- When internal audit tests the memo, tell it the fingerprint from `finding check` or the signature, so it can enter `Internal audit tested fingerprint:` in the record. The page then says if the folder moves on after its test.
- When internal audit sends something back, a person adds a line to closure/measures.md: `Sent back | 2026-11-02 | Line 8 | what it asked for | missed by the check` when the check had passed it. The check page counts those lines on its Measures line.
- If the folder cannot answer, say so and name who can.

## Passing

A person reads the answer against its cites and sends it. Nothing the assistant drafted goes to internal audit unread.
