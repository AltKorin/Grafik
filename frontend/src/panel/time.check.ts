// npm run check — fails the build if the shared time rules drift.
import assert from "node:assert/strict";
import { addDays, addMonths, dayLabel, hours, inRange, monthLabel, shiftMinutes } from "./time.ts";

assert.equal(addDays("2026-10-31", 1), "2026-11-01");
assert.equal(addDays("2026-10-25", 1), "2026-10-26"); // DST change day
assert.equal(addDays("2026-03-02", -7), "2026-02-23");
assert.equal(shiftMinutes("08:00", "16:00"), 480);
assert.equal(shiftMinutes("22:00", "06:00"), 480);
assert.equal(shiftMinutes("08:00", "16:30"), 510);
assert.equal(hours(485), "8:05");
assert.equal(hours(0), "0:00");
assert.equal(dayLabel("2026-11-03"), "wt 3.11");
assert.equal(monthLabel("2026-11"), "listopad 2026");
assert.equal(addMonths("2026-12", 1), "2027-01");
assert.equal(addMonths("2026-01", -1), "2025-12");
assert.ok(inRange("2026-11-03", "2026-11-03", "2026-11-05"));
assert.ok(!inRange("2026-11-06", "2026-11-03", "2026-11-05"));
console.log("time.check: OK");
