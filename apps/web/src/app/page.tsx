"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function Home() {
  const router = useRouter();
  useEffect(() => {
    const token = localStorage.getItem("aicos_token");
    router.replace(token ? "/dashboard" : "/login");
  }, [router]);
  return (
    <div className="min-h-screen grid place-items-center bg-ink-950 bg-aurora">
      <p className="text-mist-400 text-sm">Opening your company…</p>
    </div>
  );
}
