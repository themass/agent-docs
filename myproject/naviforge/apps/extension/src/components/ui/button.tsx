import type { ButtonHTMLAttributes } from 'react'

import { cn } from '../../lib/cn'

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'default' | 'ghost' | 'outline' | 'destructive'
  size?: 'default' | 'sm' | 'icon'
}

export function Button({
  className,
  variant = 'default',
  size = 'default',
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(
        'inline-flex items-center justify-center gap-1.5 rounded-md font-medium transition-colors disabled:opacity-50 disabled:pointer-events-none cursor-pointer',
        variant === 'default' && 'bg-primary text-primary-foreground hover:opacity-90',
        variant === 'ghost' && 'hover:bg-muted text-muted-foreground hover:text-foreground',
        variant === 'outline' && 'border border-border bg-background hover:bg-muted',
        variant === 'destructive' && 'bg-destructive text-white hover:opacity-90',
        size === 'default' && 'h-9 px-3 text-sm',
        size === 'sm' && 'h-7 px-2 text-xs',
        size === 'icon' && 'h-9 w-9 p-0',
        className
      )}
      {...props}
    />
  )
}
