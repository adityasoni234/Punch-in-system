/**
 * Shared presentational primitives. Every screen composes these so spacing,
 * touch targets and states stay consistent across the app.
 */
import { AlertCircle, AlertTriangle, CheckCircle2, Inbox, Info, X } from 'lucide-react';
import { useEffect } from 'react';

export function Card({ children, className = '', flush = false, accent = false, ...rest }) {
  const classes = ['card', flush && 'card--flush', accent && 'card--accent', className]
    .filter(Boolean)
    .join(' ');
  return (
    <section className={classes} {...rest}>
      {children}
    </section>
  );
}

export function CardTitle({ children, action }) {
  return (
    <div className="row row--between" style={{ marginBottom: 'var(--sp-3)' }}>
      <h2 className="card__title" style={{ margin: 0 }}>
        {children}
      </h2>
      {action}
    </div>
  );
}

export function Button({
  children,
  variant = 'default',
  size,
  block = false,
  loading = false,
  disabled = false,
  icon: Icon,
  type = 'button',
  className = '',
  ...rest
}) {
  const classes = [
    'btn',
    variant !== 'default' && `btn--${variant}`,
    size === 'sm' && 'btn--sm',
    block && 'btn--block',
    className,
  ]
    .filter(Boolean)
    .join(' ');
  return (
    <button className={classes} type={type} disabled={disabled || loading} {...rest}>
      {loading ? <span className="spinner" aria-hidden="true" /> : Icon ? <Icon size={18} /> : null}
      {children}
    </button>
  );
}

export function Badge({ children, variant = 'default', dot = false }) {
  return (
    <span className={`badge badge--${variant}`}>
      {dot && <span className="dot" aria-hidden="true" />}
      {children}
    </span>
  );
}

export function Notice({ variant = 'info', title, children, icon, actions }) {
  const Icon = icon ?? { info: Info, warn: AlertTriangle, error: AlertCircle, success: CheckCircle2 }[variant];
  return (
    <div className={`notice notice--${variant}`} role={variant === 'error' ? 'alert' : 'status'}>
      <div className="notice__icon" aria-hidden="true">
        <Icon size={20} />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        {title && <div className="notice__title">{title}</div>}
        {children && <div className="notice__body">{children}</div>}
        {actions && (
          <div className="row" style={{ marginTop: 'var(--sp-3)', flexWrap: 'wrap' }}>
            {actions}
          </div>
        )}
      </div>
    </div>
  );
}

export function EmptyState({ icon: Icon = Inbox, title, children, action }) {
  return (
    <div className="empty">
      <div className="empty__icon">
        <Icon size={24} />
      </div>
      <div style={{ fontWeight: 620, color: 'var(--text)' }}>{title}</div>
      {children && <p style={{ marginTop: 6, fontSize: 14 }}>{children}</p>}
      {action && <div style={{ marginTop: 'var(--sp-4)' }}>{action}</div>}
    </div>
  );
}

export function ErrorState({ error, onRetry, title = 'Could not load this' }) {
  return (
    <Notice
      variant="error"
      title={title}
      actions={
        onRetry && (
          <Button size="sm" variant="outline" onClick={onRetry}>
            Try again
          </Button>
        )
      }
    >
      {error?.message || 'Something went wrong.'}
    </Notice>
  );
}

export function Skeleton({ height = 16, width = '100%', style }) {
  return <div className="skeleton" style={{ height, width, ...style }} aria-hidden="true" />;
}

export function SkeletonCard({ lines = 3 }) {
  return (
    <Card>
      <Skeleton height={20} width="45%" />
      <div style={{ height: 12 }} />
      {Array.from({ length: lines }).map((_, index) => (
        <div key={index} style={{ marginBottom: 10 }}>
          <Skeleton height={14} width={index === lines - 1 ? '60%' : '100%'} />
        </div>
      ))}
    </Card>
  );
}

export function StatTile({ label, value, tone }) {
  return (
    <div className={`stat${tone ? ` stat--${tone}` : ''}`}>
      <div className="stat__label">{label}</div>
      <div className="stat__value">{value}</div>
    </div>
  );
}

export function Field({ label, hint, error, children, htmlFor }) {
  return (
    <div className="field">
      {label && (
        <label className="field__label" htmlFor={htmlFor}>
          {label}
        </label>
      )}
      {children}
      {error ? (
        <span className="field__error">{error}</span>
      ) : hint ? (
        <span className="field__hint">{hint}</span>
      ) : null}
    </div>
  );
}

export function Input({ invalid = false, className = '', ...rest }) {
  return <input className={`input${invalid ? ' input--invalid' : ''} ${className}`} {...rest} />;
}

export function Select({ children, className = '', ...rest }) {
  return (
    <select className={`select ${className}`} {...rest}>
      {children}
    </select>
  );
}

export function SegmentedControl({ options, value, onChange, ariaLabel }) {
  return (
    <div className="segmented" role="tablist" aria-label={ariaLabel}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          role="tab"
          aria-selected={value === option.value}
          className={`segmented__item${value === option.value ? ' segmented__item--active' : ''}`}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

export function Sheet({ open, onClose, title, children, dismissible = true }) {
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (event) => {
      if (event.key === 'Escape' && dismissible) onClose?.();
    };
    document.addEventListener('keydown', onKey);
    const { overflow } = document.body.style;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = overflow;
    };
  }, [open, onClose, dismissible]);

  if (!open) return null;
  return (
    <div
      className="sheet-backdrop"
      onClick={dismissible ? onClose : undefined}
      role="presentation"
    >
      <div
        className="sheet"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={(event) => event.stopPropagation()}
      >
        {title && (
          <div className="row row--between" style={{ marginBottom: 'var(--sp-3)' }}>
            <h2 className="sheet__title" style={{ margin: 0 }}>
              {title}
            </h2>
            {dismissible && (
              <button className="icon-button" onClick={onClose} aria-label="Close">
                <X size={20} />
              </button>
            )}
          </div>
        )}
        {children}
      </div>
    </div>
  );
}

export function KeyValue({ label, children }) {
  return (
    <div className="kv">
      <span className="kv__key">{label}</span>
      <span className="kv__value">{children}</span>
    </div>
  );
}
