'use client';

type BadgeVariant = 'ready' | 'in-progress' | 'not-started' | 'error' | 'processing' | 'draft' | 'sent' | 'live' | 'disabled' | 'warning';

type StatusBadgeProps = {
  readonly status: BadgeVariant;
  readonly label?: string;
};

const VARIANT_CLASS: Record<BadgeVariant, string> = {
  'ready': 'tag-green',
  'in-progress': 'tag-orange',
  'not-started': '',
  'error': 'tag-red',
  'processing': 'tag-orange',
  'draft': '',
  'sent': 'tag-green',
  'live': 'tag-green',
  'disabled': '',
  'warning': 'tag-red',
};

const DEFAULT_LABELS: Record<BadgeVariant, string> = {
  'ready': 'Ready',
  'in-progress': 'In Progress',
  'not-started': 'Not Started',
  'error': 'Error',
  'processing': 'Processing',
  'draft': 'Draft',
  'sent': 'Sent',
  'live': 'Live',
  'disabled': 'Disabled',
  'warning': 'Warning',
};

export default function StatusBadge({ status, label }: StatusBadgeProps) {
  const displayLabel = label || DEFAULT_LABELS[status] || status;
  const className = `tag ${VARIANT_CLASS[status] || ''}`.trim();

  return <span className={className}>{displayLabel}</span>;
}

export type { BadgeVariant, StatusBadgeProps };
