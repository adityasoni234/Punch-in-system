export function initials(name) {
  if (!name) return '?';
  return name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('');
}

export function pluralise(count, singular, plural) {
  return `${count} ${count === 1 ? singular : plural || `${singular}s`}`;
}

export function metres(value) {
  if (value === null || value === undefined) return '--';
  return `${Math.round(value)} m`;
}

export function statusLabel(status) {
  switch (status) {
    case 'PRESENT':
      return 'Present';
    case 'CHECKED_OUT':
      return 'Checked out';
    case 'ABSENT':
    default:
      return 'Not present';
  }
}

export function statusModifier(status) {
  switch (status) {
    case 'PRESENT':
      return 'present';
    case 'CHECKED_OUT':
      return 'checked-out';
    default:
      return 'absent';
  }
}
