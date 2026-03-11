import { Suspense } from "react";
import { CompareView } from "@/components/compare/CompareView";

export default function ComparePage() {
  return (
    <Suspense fallback={
      <main style={{ minHeight: "100vh", background: "var(--black)", color: "var(--white)" }}>
        <div style={{ maxWidth: 1100, margin: "0 auto", padding: "40px 32px" }}>
          <div style={{ height: 300, display: "flex", alignItems: "center", justifyContent: "center", color: "#333", fontSize: 12 }}>
            Loading…
          </div>
        </div>
      </main>
    }>
      <CompareView />
    </Suspense>
  );
}
