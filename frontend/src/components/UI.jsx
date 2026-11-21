import { ArrowUpRight, Info } from 'lucide-react'

export function DemoNotice({ children = 'DEMO DATA · Illustrative content only. No live feeds are connected.' }) {
  return (
    <div className="demo-notice" role="note">
      <Info size={16} aria-hidden="true" />
      <span>{children}</span>
    </div>
  )
}

export function PageHeader({ eyebrow = 'FLOODGUARD AI', title, description, action }) {
  return (
    <div className="page-heading">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        {description && <p className="page-description">{description}</p>}
      </div>
      {action && <div className="heading-action">{action}</div>}
    </div>
  )
}

export function Panel({ title, subtitle, action, className = '', children }) {
  return (
    <section className={`panel ${className}`}>
      {(title || subtitle || action) && (
        <div className="panel-heading">
          <div>
            {title && <h2>{title}</h2>}
            {subtitle && <p>{subtitle}</p>}
          </div>
          {action}
        </div>
      )}
      {children}
    </section>
  )
}

export function TextLink({ children, href = '#' }) {
  return <a className="text-link" href={href}>{children}<ArrowUpRight size={15} /></a>
}

export function Pill({ children, tone = 'neutral' }) {
  return <span className={`pill pill-${tone}`}>{children}</span>
}
