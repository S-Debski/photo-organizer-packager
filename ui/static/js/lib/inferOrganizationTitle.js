// Role: JavaScript module

// ui/lib/inferOrganizationTitle.js

export function inferOrganizationTitle(earliestDate, latestDate) {
  // Rule 5: No valid dates
  if (!earliestDate || !latestDate) {
    return "Photos – Undated Import";
  }

  const start = new Date(earliestDate);
  const end = new Date(latestDate);

  // Defensive ordering
  if (end < start) {
    return inferOrganizationTitle(end, start);
  }

  const sameDay =
    start.getFullYear() === end.getFullYear() &&
    start.getMonth() === end.getMonth() &&
    start.getDate() === end.getDate();

  const sameMonth =
    start.getFullYear() === end.getFullYear() &&
    start.getMonth() === end.getMonth();

  const sameYear =
    start.getFullYear() === end.getFullYear();

  let formattedRange;

  if (sameDay) {
    formattedRange = start.toISOString().slice(0, 10); // YYYY-MM-DD
  }
  else if (sameMonth) {
    formattedRange = start.toLocaleString("en-GB", {
      month: "long",
      year: "numeric",
    });
  }
  else if (sameYear) {
    const startMonth = start.toLocaleString("en-GB", { month: "long" });
    const endMonth = end.toLocaleString("en-GB", { month: "long" });
    formattedRange = `${startMonth}–${endMonth} ${start.getFullYear()}`;
  }
  else {
    const startStr = start.toLocaleString("en-GB", {
      month: "short",
      year: "numeric",
    });
    const endStr = end.toLocaleString("en-GB", {
      month: "short",
      year: "numeric",
    });
    formattedRange = `${startStr} – ${endStr}`;
  }

  return `Photos – ${formattedRange}`;
}
