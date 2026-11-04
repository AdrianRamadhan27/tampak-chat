"use client";

import { useEffect, useState } from "react";
import { Timer } from "lucide-react";
import { api } from "@/lib/api";

type Usage = {
  usage: {
    bots: number;
    bytes: number;
    pages: number;
    turns: number;
    model_calls: number;
  };
  limits: {
    bots: number;
    bytes: number;
    pages: number;
    turns: number;
    model_calls: number;
  };
  expires_at: string | null;
  unlimited: boolean;
};

export function UsageSummary({ refreshKey }: { refreshKey: string }) {
  const [quota, setQuota] = useState<Usage | null>(null);
  useEffect(() => {
    let disposed = false;
    api<Usage>("/usage")
      .then((value) => {
        if (!disposed) setQuota(value);
      })
      .catch(() => {});
    return () => {
      disposed = true;
    };
  }, [refreshKey]);
  if (!quota || quota.unlimited) return null;
  return (
    <div className="rail-usage" aria-label="Remaining temporary demo quota">
      <span className="eyebrow">YOUR DEMO QUOTA</span>
      <div>
        <span>
          {Math.max(0, quota.limits.bots - quota.usage.bots)} bots remaining
        </span>
        <span>
          {Math.max(0, quota.limits.turns - quota.usage.turns)} turns today
        </span>
      </div>
      <div className="usage-meter" aria-hidden>
        <span
          style={{
            width: `${Math.min(100, (quota.usage.bytes / quota.limits.bytes) * 100)}%`,
          }}
        />
      </div>
      <p>
        {(quota.usage.bytes / 1048576).toFixed(1)} /{" "}
        {(quota.limits.bytes / 1048576).toFixed(0)} MB · {quota.usage.pages} /{" "}
        {quota.limits.pages} pages
      </p>
      <p>
        {quota.usage.model_calls} / {quota.limits.model_calls} model calls today
      </p>
      {quota.expires_at && (
        <p>
          <Timer size={10} />
          Expires{" "}
          {new Date(quota.expires_at).toLocaleString([], {
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
          })}
        </p>
      )}
    </div>
  );
}
