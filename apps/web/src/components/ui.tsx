"use client";

import * as DialogPrimitive from "@radix-ui/react-dialog";
import * as Dropdown from "@radix-ui/react-dropdown-menu";
import * as Switch from "@radix-ui/react-switch";
import { AlertCircle, Check, ChevronDown, LoaderCircle, X } from "lucide-react";
import type { ReactNode } from "react";
import { clsx } from "clsx";

export function Button({
  children,
  className,
  variant = "secondary",
  busy,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  busy?: boolean;
}) {
  return (
    <button
      type="button"
      className={clsx("button", variant, className)}
      {...props}
      disabled={props.disabled || busy}
    >
      {busy && <LoaderCircle size={15} className="spin" />}
      {children}
    </button>
  );
}
export function IconButton({
  children,
  label,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { label: string }) {
  return (
    <button
      type="button"
      className="icon-button"
      title={label}
      aria-label={label}
      {...props}
    >
      {children}
    </button>
  );
}
export function Dialog({
  open,
  onOpenChange,
  title,
  description,
  children,
  className,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="dialog-overlay" />
        <DialogPrimitive.Content className={clsx("dialog-content", className)}>
          <div className="dialog-heading">
            <div>
              <DialogPrimitive.Title>{title}</DialogPrimitive.Title>
              <DialogPrimitive.Description>
                {description || "Tampak-Chat workspace"}
              </DialogPrimitive.Description>
            </div>
            <DialogPrimitive.Close asChild>
              <IconButton label="Close dialog">
                <X size={20} />
              </IconButton>
            </DialogPrimitive.Close>
          </div>
          {children}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
export function Menu({
  label,
  children,
  trigger,
  align = "end",
}: {
  label: string;
  children: ReactNode;
  trigger?: ReactNode;
  align?: "start" | "end";
}) {
  return (
    <Dropdown.Root>
      <Dropdown.Trigger asChild>
        <button className="button ghost" aria-label={label}>
          {trigger || (
            <>
              {label}
              <ChevronDown size={14} />
            </>
          )}
        </button>
      </Dropdown.Trigger>
      <Dropdown.Portal>
        <Dropdown.Content
          className="dropdown-content"
          sideOffset={7}
          align={align}
        >
          {children}
        </Dropdown.Content>
      </Dropdown.Portal>
    </Dropdown.Root>
  );
}
export function MenuItem({
  children,
  onSelect,
  disabled,
  danger,
}: {
  children: ReactNode;
  onSelect?: () => void;
  disabled?: boolean;
  danger?: boolean;
}) {
  return (
    <Dropdown.Item
      className={clsx("dropdown-item", danger && "text-danger")}
      onSelect={onSelect}
      disabled={disabled}
    >
      {children}
    </Dropdown.Item>
  );
}
export function Toggle({
  checked,
  onChange,
  children,
  icon,
}: {
  checked: boolean;
  onChange: (checked: boolean) => void;
  children: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <label className={clsx("toggle-label", checked && "is-on")}>
      {icon}
      <span>{children}</span>
      <Switch.Root
        className="switch"
        checked={checked}
        onCheckedChange={onChange}
      >
        <Switch.Thumb className="switch-thumb" />
      </Switch.Root>
    </label>
  );
}
export function ErrorBanner({
  message,
  dismiss,
}: {
  message: string;
  dismiss?: () => void;
}) {
  return (
    <div className="error-banner" role="alert">
      <AlertCircle size={17} />
      <span>{message}</span>
      {dismiss && (
        <IconButton label="Dismiss error" onClick={dismiss}>
          <X size={16} />
        </IconButton>
      )}
    </div>
  );
}
export function Badge({
  children,
  tone = "neutral",
}: {
  children: ReactNode;
  tone?: "neutral" | "green" | "amber" | "red";
}) {
  return <span className={clsx("badge", tone)}>{children}</span>;
}
export function StatusBadge({ status }: { status: string }) {
  const good = ["READY", "COMPLETED"].includes(status);
  const pending = [
    "AWAITING_REVIEW",
    "READY_LEXICAL",
    "PENDING_CONFIG",
    "CONSENT_REQUIRED",
  ].includes(status);
  return (
    <Badge
      tone={
        good
          ? "green"
          : pending
            ? "amber"
            : status === "FAILED"
              ? "red"
              : "neutral"
      }
    >
      {good && <Check size={11} />}
      {["RUNNING", "PROCESSING", "INDEXING", "QUEUED", "UPLOADED"].includes(
        status,
      ) && <LoaderCircle size={11} className="spin" />}
      {status.toLowerCase().replaceAll("_", " ")}
    </Badge>
  );
}
export function EmptyState({
  icon,
  title,
  children,
  action,
}: {
  icon: ReactNode;
  title: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="empty-state">
      <div className="empty-icon">{icon}</div>
      <h2>{title}</h2>
      <p>{children}</p>
      {action}
    </div>
  );
}
