"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowRight, Boxes, CheckCircle2, CloudUpload, Flame, GitBranch, Github, MessageSquareText, Plus, Radar, Search, TerminalSquare, Wrench } from "lucide-react";
import { api } from "@/lib/api";
import type { MissionSummary, RepositoryIndex, Skill } from "@/lib/types";
import { fmtDuration, timeAgo } from "@/lib/format";
import { Pill, ProgressBar } from "./Badge";

const MISSION_HINT =
  "Investigate a race condition in the checkout flow where a second confirm can fail or duplicate the order.";

const FLOW_STEPS = ["Init", "Index", "Plan", "Investigate", "Root cause", "Implement", "Validate", "Critic", "Release"];

const HOW_IT_WORKS = [
  {
    step: "1",
    icon: <MessageSquareText className="h-5 w-5 text-[#4F46E5]" />,
    title: "You describe the problem",
    body: "Type the bug or request in your own words — no code needed. Nobody has to understand programming to start.",
  },
  {
    step: "2",
    icon: <Search className="h-5 w-5 text-[#4F46E5]" />,
    title: "FORGE investigates",
    body: "It reads the code, finds the real cause, and shows you proof — the exact files, lines and tests that fail.",
  },
  {
    step: "3",
    icon: <CheckCircle2 className="h-5 w-5 text-[#4F46E5]" />,
    title: "You get a verified fix",
    body: "FORGE writes the fix, runs the tests, checks for security problems, and ships a result you can trust.",
  },
];

export default function CommandCenter() {
  const router = useRouter();
  const [text, setText] = useState("");
  const [title, setTitle] = useState("");
  const [launching, setLaunching] = useState(false);
  const [secret, setSecret] = useState("");
  const [missions, setMissions] = useState<MissionSummary[]>([]);
  const [repos, setRepos] = useState<RepositoryIndex[]>([]);
  const [skills, setSkills] = useState<Skill[]>([]);
  const [repo, setRepo] = useState("forgemart");
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const [connectUrl, setConnectUrl] = useState("");
  const [connecting, setConnecting] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const load = () => {
    api.missions().then(setMissions).catch(() => {});
    api.repositories().then(setRepos).catch(() => {});
    api.skills().then(setSkills).catch(() => {});
  };

  useEffect(() => {
    load();
    const t = setInterval(load, 4000);
    return () => clearInterval(t);
  }, []);

  const onUpload = async (file: File | undefined) => {
    if (!file) return;
    setUploading(true);
    setUploadError("");
    try {
      const idx = await api.uploadRepo(file);
      setRepo(idx.name);
      setMissions([]);
      await api.repositories().then(setRepos).catch(() => {});
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  };

  const onConnect = async () => {
    const url = connectUrl.trim();
    if (!url || connecting) return;
    setConnecting(true);
    setUploadError("");
    try {
      const idx = await api.connectRepo(url);
      setRepo(idx.name);
      setMissions([]);
      setConnectUrl("");
      await api.repositories().then(setRepos).catch(() => {});
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Connect failed");
    } finally {
      setConnecting(false);
    }
  };

  const launch = async () => {
    if (!text.trim() || launching) return;
    setLaunching(true);
    try {
      const { mission_id } = await api.launch({
        title: title.trim() || undefined,
        mission_text: text.trim(),
        repository: repo,
      });
      router.push(`/missions/${mission_id}`);
    } finally {
      setLaunching(false);
    }
  };

  const totalFiles = repos.reduce((n: number, r) => n + Number((r.stats.files ?? 0) ?? 0), 0);
  const totalTests = repos.reduce((n: number, r) => n + Number((r.stats.tests ?? 0) ?? 0), 0);
  const totalSkills = skills.length;

  return (
    <main className="min-h-screen">
      <div className="mx-auto max-w-7xl px-6 py-10">
        {/* header */}
        <header className="flex items-center justify-between">
          <Link href="/" className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-[#E5E7EB] bg-white transition-colors hover:border-[#4F46E5]/50">
              <Flame className="h-5 w-5 text-[#4F46E5]" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight text-gray-900">
                FORGE<span className="text-[#4F46E5]">.</span>
              </h1>
              <p className="text-[12px] text-gray-500">The AI software engineer — describe a bug, get a verified fix</p>
            </div>
          </Link>
          <div className="flex items-center gap-3">
            <span className="hidden text-[12px] text-gray-500 sm:inline">For everyone, not just engineers</span>
            <Pill text="AI Software Engineer" color="#4F46E5" />
          </div>
        </header>

        {/* hero */}
        <section className="mt-14">
          <AnimatePresence>
            {!secret && (
              <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }}>
                <h2 className="max-w-3xl text-3xl font-bold leading-tight tracking-tight text-gray-900 sm:text-5xl">
                  FORGE fixes your software bugs for you — and shows you exactly what it did.
                </h2>
                <p className="mt-4 max-w-2xl text-[15px] leading-relaxed text-gray-600">
                  It works for anyone. Describe a problem in plain words — like <em>“a customer pays twice when they
                  click the confirm button again”</em> — and FORGE reads your code, finds the real cause, writes the
                  fix, runs the tests, and checks for security issues. You end up with a simple report you can trust.
                  No engineering background needed.
                </p>
                <p className="mt-3 max-w-2xl text-[13px] text-gray-500">
                  For engineers: an observables-driven pipeline — repository intelligence → parallel investigation →
                  root cause → tested fix → security review → release gate — every claim backed by files, tests and diffs.
                </p>
              </motion.div>
            )}
          </AnimatePresence>
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.25 }} className="mt-10 flex flex-wrap items-center gap-2">
            {FLOW_STEPS.map((s, i) => (
              <div key={s} className="flex items-center gap-2">
                <span className="rounded-md border border-[#E5E7EB] bg-white px-2.5 py-1 text-[12px] font-medium text-gray-600">
                  {s}
                </span>
                {i < FLOW_STEPS.length - 1 && <span className="text-gray-300">→</span>}
              </div>
            ))}
          </motion.div>
        </section>

        {/* how it works — plain language, for everyone */}
        <section className="mt-12">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="panel-title">How it works — in plain words</h3>
            <span className="text-[12px] text-gray-400">No technical background required</span>
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            {HOW_IT_WORKS.map((c) => (
              <div key={c.step} className="panel p-6">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#4F46E5]/10">
                  {c.icon}
                </div>
                <p className="mt-4 text-[13px] font-bold text-[#4F46E5]">Step {c.step}</p>
                <h3 className="mt-1 text-[16px] font-bold text-gray-900">{c.title}</h3>
                <p className="mt-2 text-[13px] leading-relaxed text-gray-600">{c.body}</p>
              </div>
            ))}
          </div>
        </section>

        {/* mission input */}
        <section className="mt-12 grid gap-6 lg:grid-cols-5">
          <div className="panel p-6 lg:col-span-3">
            <div className="flex items-center justify-between">
              <h3 className="panel-title">Try it — launch a mission</h3>
              <TerminalSquare className="h-4 w-4 text-gray-400" />
            </div>
            <p className="mt-2 text-sm text-gray-600">
              Write the problem in your own words, pick a target repository, then click <span className="font-medium">Launch mission</span> and watch FORGE investigate, fix and verify — live.
            </p>
            <textarea
              value={text}
              onChange={(e) => setText(e.target.value)}
              rows={5}
              placeholder={MISSION_HINT}
              className="mt-4 w-full resize-none rounded-lg border border-[#E5E7EB] bg-[#F9FAFB] p-3 font-mono text-[13px] leading-relaxed text-gray-900 outline-none placeholder:text-gray-400 focus:border-[#4F46E5] focus:ring-2 focus:ring-[#4F46E5]/10"
            />
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Mission title (optional)"
                className="flex-1 rounded-lg border border-[#E5E7EB] bg-white px-3 py-2 text-sm text-gray-900 outline-none placeholder:text-gray-400 focus:border-[#4F46E5] focus:ring-2 focus:ring-[#4F46E5]/10"
              />
              <button onClick={launch} disabled={!text.trim() || launching} className="btn-forge flex items-center gap-2 px-5 py-2 text-sm">
                {launching ? <Radar className="h-4 w-4 animate-pulse" /> : <Plus className="h-4 w-4" />}
                {launching ? "Launching…" : "Launch mission"}
              </button>
            </div>
            {/* target repository + BYOS upload */}
            <div className="mt-3 flex flex-wrap items-center gap-3 rounded-lg border border-[#E5E7EB] bg-white p-3">
              <label className="text-[12px] font-medium text-gray-500" htmlFor="repo-select">
                Target repository
              </label>
              <select
                id="repo-select"
                value={repo}
                onChange={(e) => setRepo(e.target.value)}
                className="flex-1 rounded-lg border border-[#E5E7EB] bg-[#F9FAFB] px-2.5 py-1.5 text-sm text-gray-900 outline-none focus:border-[#4F46E5]"
              >
                <option value="forgemart">ForgeMart (sample repository)</option>
                {repos
                  .filter((r) => r.name !== "forgemart")
                  .map((r) => (
                    <option key={r.name} value={r.name}>
                      {r.name} ({Number(r.stats.files ?? 0)} files)
                    </option>
                  ))}
              </select>
              <button
                onClick={() => fileRef.current?.click()}
                disabled={uploading}
                className="btn-forge flex items-center gap-2 px-3 py-1.5 text-[13px]"
              >
                <CloudUpload className="h-4 w-4" />
                {uploading ? "Uploading…" : "Upload your code (ZIP)"}
              </button>
              <input
                ref={fileRef}
                type="file"
                accept=".zip,application/zip"
                className="hidden"
                onChange={(e) => onUpload(e.target.files?.[0])}
              />
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-2 rounded-lg border border-[#E5E7EB] bg-white p-2.5">
              <Github className="h-4 w-4 text-gray-400" />
              <input
                value={connectUrl}
                onChange={(e) => setConnectUrl(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && onConnect()}
                placeholder="Or paste a GitHub URL — e.g. octo/widgets"
                className="flex-1 rounded-lg border border-[#E5E7EB] bg-[#F9FAFB] px-2.5 py-1.5 text-[13px] text-gray-900 outline-none placeholder:text-gray-400 focus:border-[#4F46E5]"
              />
              <button
                onClick={onConnect}
                disabled={!connectUrl.trim() || connecting}
                className="btn-forge flex items-center gap-2 px-3 py-1.5 text-[13px]"
              >
                <GitBranch className="h-4 w-4" />
                {connecting ? "Connecting…" : "Connect repo"}
              </button>
            </div>
            {uploadError && <p className="mt-2 text-[12px] text-red-600">{uploadError}</p>}
            <div className="mt-3 flex items-center gap-2 text-[12px] text-gray-400">
              <Flame className="h-3 w-3 text-[#4F46E5]" />
              <span>
                Describe a bug in plain words and hit launch — or upload your code as a ZIP, or connect a GitHub
                repository. FORGE inspects it honestly and ships a fix only when a skill matches or it can{" "}
                <button onClick={() => setText(MISSION_HINT)} className="font-medium text-[#4F46E5] hover:underline">
                  try an example
                </button>{" "}
                vs. verify an AI repair against the real test suite.
              </span>
            </div>
          </div>

          {/* stat strip */}
          <div className="grid gap-4 lg:col-span-2">
            {[
              { label: "Indexed repos", icon: <Boxes className="h-4 w-4 text-[#4F46E5]" />, value: String(repos.length) },
              { label: "Files scanned", icon: <GitBranch className="h-4 w-4 text-[#4F46E5]" />, value: String(totalFiles) },
              { label: "Tests discovered", icon: <TerminalSquare className="h-4 w-4 text-[#4F46E5]" />, value: String(totalTests) },
              { label: "Skills registered", icon: <Wrench className="h-4 w-4 text-[#4F46E5]" />, value: String(totalSkills) },
            ].map((s) => (
              <div key={s.label} className="panel flex items-center gap-4 p-5">
                {s.icon}
                <div>
                  <p className="text-2xl font-bold text-gray-900">{s.value || "–"}</p>
                  <p className="text-[12px] text-gray-500">{s.label}</p>
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* recent missions */}
        <section className="mt-12">
          <div className="mb-4 flex items-center justify-between">
            <h3 className="panel-title">Recent missions</h3>
            <ArrowRight className="h-4 w-4 text-gray-400" />
          </div>
          {missions.length === 0 ? (
            <div className="panel p-8 text-center text-sm text-gray-400">No missions yet — launch one above.</div>
          ) : (
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {missions.map((m, i) => (
                <motion.button
                  key={m.id}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: i * 0.05 }}
                  onClick={() => router.push(`/missions/${m.id}`)}
                  className="panel group p-5 text-left transition-colors hover:border-[#4F46E5]/40"
                >
                  <div className="flex items-start justify-between gap-2">
                    <h4 className="text-[13px] font-semibold leading-snug text-gray-900 group-hover:text-[#4F46E5]">{m.title}</h4>
                    <Pill text={m.status} color="#4F46E5" />
                  </div>
                  <p className="mt-2 line-clamp-2 font-mono text-[11px] leading-relaxed text-gray-500">{m.summary || m.error || m.id}</p>
                  <div className="mt-3 flex items-center gap-3">
                    <div className="flex-1">
                      <ProgressBar value={m.progress} color={m.status === "completed" ? "#059669" : "#4F46E5"} />
                    </div>
                    <span className="text-[11px] text-gray-500">{fmtDuration(m.duration_ms)}</span>
                  </div>
                  <p className="mt-2 text-[11px] text-gray-400">{timeAgo(m.created_at)}</p>
                </motion.button>
              ))}
            </div>
          )}
        </section>

        {/* footer */}
        <footer className="mt-16 flex flex-col items-center gap-1 border-t border-[#E5E7EB] py-8 text-center">
          <p className="text-[12px] font-medium text-gray-500">FORGE — the AI software engineer for everyone</p>
          <p className="text-[12px] text-gray-400">Describe a bug · get a verified fix · everything it did is shown as proof</p>
        </footer>
      </div>
    </main>
  );
}