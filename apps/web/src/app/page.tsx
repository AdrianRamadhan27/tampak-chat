import { Suspense } from "react";
import { Workspace } from "@/components/workspace";

export default function Page() {
  return (
    <Suspense
      fallback={<main className="boot-screen">Opening Tampak-Chat…</main>}
    >
      <Workspace />
    </Suspense>
  );
}
