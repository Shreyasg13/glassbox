"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";

/** Header bell with the unread count, linking to the inbox. Polls once a minute; hidden for admins and signed-out visitors. */
export function NotificationBell() {
  const { token, role } = useAuth();
  const q = useQuery({
    queryKey: ["unread-count"],
    queryFn: () => apiFetch<{ unread: number }>("/api/me/notifications/unread-count", { token: token ?? undefined }),
    enabled: !!token && role !== "admin",
    refetchInterval: 60_000,
    retry: false,
  });
  if (!token || role === "admin") return null;
  const n = q.data?.unread ?? 0;
  return (
    <Link href="/notifications" aria-label={n ? `Inbox, ${n} unread` : "Inbox"} className="btn btn-ghost relative px-sp3 text-[15px]">
      <span aria-hidden>🔔</span>
      {n > 0 && (
        <span className="absolute -right-1 -top-1 flex h-[16px] min-w-[16px] items-center justify-center rounded-full bg-red px-1 text-[9.5px] font-bold text-white">{n > 99 ? "99+" : n}</span>
      )}
    </Link>
  );
}
