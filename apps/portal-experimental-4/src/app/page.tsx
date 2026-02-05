"use client";

import { useState, useEffect, useRef } from "react";
import {
  Volume2,
  ArrowRight,
  Sparkles,
  Mail,
  MessageSquare,
  CheckCircle2,
  Shield,
  Users,
  Zap,
  Star,
  Clock,
  Lock,
  TrendingUp,
  AlertCircle,
  Play,
  UserCheck,
  Calendar,
  RefreshCw,
  FileText,
  Target,
} from "lucide-react";

export default function Home() {
  const [isVisible, setIsVisible] = useState(false);
  const [allowMotion, setAllowMotion] = useState(true);
  const [orbHover, setOrbHover] = useState(false);
  const [showStickyCta, setShowStickyCta] = useState(false);
  const [isLogoHovered, setIsLogoHovered] = useState(false);
  const [montyStatusIndex, setMontyStatusIndex] = useState(0);
  const [chatInput, setChatInput] = useState("");
  const [chatMessages, setChatMessages] = useState<
    Array<{ role: "user" | "assistant"; content: string }>
  >([
    {
      role: "assistant",
      content:
        "Ask me anything about Monty—pricing, security, or how autopilot works.",
    },
  ]);
  const scenicRef = useRef<HTMLDivElement>(null);
  const orbRef = useRef<HTMLDivElement>(null);
  const highlightRef = useRef<SVGCircleElement>(null);
  const orbRAFRef = useRef<number | null>(null);
  const heroRef = useRef<HTMLElement>(null);

  const montyStatuses = [
    { state: "ready", text: "Monty is ready. What should we handle first?" },
    { state: "checking", text: "Checking your inbox now…" },
    { state: "drafting", text: "Drafting replies in your voice—ready for review." },
  ] as const;

  const portalUrl = process.env.NEXT_PUBLIC_PORTAL_URL || "http://localhost:3005";
  const loginHref = `${portalUrl.replace(/\/$/, "")}/login`;

  const scrollToSection = (id: string) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.scrollIntoView({ behavior: "smooth", block: "start" });
    window.history.replaceState(null, "", `#${id}`);
  };

  const getMontyPlaceholderAnswer = (question: string) => {
    const q = question.trim().toLowerCase();

    if (q.includes("security") || q.includes("secure") || q.includes("data")) {
      return "Monty uses scoped OAuth access and can run in approval-first mode so nothing sends without you. If you want, we can walk through exactly what permissions are granted during setup.";
    }

    if (q.includes("autopilot") || q.includes("send") || q.includes("automatic")) {
      return "By default, Monty drafts replies for review. Autopilot is optional and gated by rules/guardrails—so you stay in control.";
    }

    if (q.includes("price") || q.includes("pricing") || q.includes("cost") || q.includes("$")) {
      return "There’s a free Starter plan to try Monty, and a Team plan when you’re ready for shared controls. If you tell me your team size + inbox count, I can recommend the best fit.";
    }

    if (q.includes("setup") || q.includes("install") || q.includes("onboard") || q.includes("minutes")) {
      return "Setup is designed to be quick: connect an inbox, then Monty starts drafting within minutes. Early access includes personal onboarding so you’re not left guessing.";
    }

    return "Good question. This chat is a placeholder for the upcoming Monty copilot—if you share what you’re trying to achieve, we’ll address it during onboarding. For now, you can request early access or sign in to the portal.";
  };

  const handleChatSend = () => {
    const text = chatInput.trim();
    if (!text) return;
    setChatMessages((prev) => [
      ...prev,
      { role: "user", content: text },
      { role: "assistant", content: getMontyPlaceholderAnswer(text) },
    ]);
    setChatInput("");
  };

  // State for spring-physics highlight (executive-calm: slow, subtle)
  const orbStateRef = useRef({
    // target highlight position (relative to center, -1 to 1)
    tx: 0,
    ty: 0,
    // current position
    x: 0,
    y: 0,
    // velocity
    vx: 0,
    vy: 0,
  });

  useEffect(() => {
    const step = () => {
      const state = orbStateRef.current;
      const hl = highlightRef.current;

      // Soft spring: low stiffness, high damping = calm, deliberate motion
      const dt = 1 / 60;
      const k = 12; // stiffness (lower = slower)
      const d = 8;  // damping (higher = less overshoot)

      const ax = (state.tx - state.x) * k - state.vx * d;
      const ay = (state.ty - state.y) * k - state.vy * d;

      state.vx += ax * dt;
      state.vy += ay * dt;

      state.x += state.vx * dt * 60;
      state.y += state.vy * dt * 60;

      // Map to SVG coords: center is 80,80; max drift ~12px
      const hlX = 56 + state.x * 12;
      const hlY = 56 + state.y * 12;

      if (hl) {
        hl.setAttribute("cx", hlX.toFixed(2));
        hl.setAttribute("cy", hlY.toFixed(2));
      }

      orbRAFRef.current = requestAnimationFrame(step);
    };

    orbRAFRef.current = requestAnimationFrame(step);
    return () => {
      if (orbRAFRef.current) cancelAnimationFrame(orbRAFRef.current);
    };
  }, []);

  const handleOrbMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!allowMotion) return;
    const el = orbRef.current;
    if (!el) return;

    const rect = el.getBoundingClientRect();
    // Normalize to -1 to 1 (center = 0)
    const nx = ((e.clientX - rect.left) / rect.width - 0.5) * 2;
    const ny = ((e.clientY - rect.top) / rect.height - 0.5) * 2;

    const state = orbStateRef.current;
    state.tx = Math.max(-1, Math.min(1, nx));
    state.ty = Math.max(-1, Math.min(1, ny));
  };

  const handleOrbEnter = () => {
    if (!allowMotion) return;
    setOrbHover(true);
  };

  const handleOrbLeave = () => {
    setOrbHover(false);
    // Slowly drift highlight back to center
    const state = orbStateRef.current;
    state.tx = 0;
    state.ty = 0;
  };

  useEffect(() => {
    setIsVisible(true);

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    setAllowMotion(!reduced);

    // Smooth parallax via rAF easing (prevents snap on enter/leave)
    const target = { x: 0, y: 0 };
    const current = { x: 0, y: 0 };
    let rafId: number | null = null;

    const animate = () => {
      const el = scenicRef.current;
      if (el) {
        const ease = 0.04; // slower easing = no snap
        current.x += (target.x - current.x) * ease;
        current.y += (target.y - current.y) * ease;

        el.style.setProperty("--mx", current.x.toFixed(3));
        el.style.setProperty("--my", current.y.toFixed(3));
      }
      rafId = requestAnimationFrame(animate);
    };

    // Track target from global mouse position, not just the left panel.
    // This removes the snap that happens on enter/leave of the gradient area.
    const handleMouseMove = (e: MouseEvent) => {
      const w = window.innerWidth || 1;
      const h = window.innerHeight || 1;
      target.x = e.clientX / w - 0.5;
      target.y = e.clientY / h - 0.5;
    };

    const handleWindowLeave = (e: MouseEvent) => {
      if ((e.relatedTarget as Node | null) === null) {
        target.x = 0;
        target.y = 0;
      }
    };

    // Intro-only snap: scroll from hero -> next section (and back) snaps,
    // everything else remains normal smooth scrolling.
    let snapLocked = false;
    let snapUnlockTimer: number | null = null;

    const getIntroAndNext = () => {
      const intro = document.querySelector<HTMLElement>(".intro-panel");
      const next = intro?.nextElementSibling as HTMLElement | null;
      if (!intro || !next) return null;
      return { intro, next };
    };

    const snapTo = (top: number) => {
      snapLocked = true;
      window.scrollTo({ top, behavior: "smooth" });
      if (snapUnlockTimer) window.clearTimeout(snapUnlockTimer);
      snapUnlockTimer = window.setTimeout(() => {
        snapLocked = false;
      }, 650);
    };

    const handleWheel = (e: WheelEvent) => {
      if (reduced) return;
      if (snapLocked) return;

      const delta = e.deltaY;
      if (Math.abs(delta) < 8) return;

      const els = getIntroAndNext();
      if (!els) return;

      const y = window.scrollY;
      const navEl = document.querySelector<HTMLElement>("nav");
      const navOffset = navEl?.getBoundingClientRect().height ?? 64;
      const nextTop = els.next.offsetTop;
      const snapNextTop = Math.max(0, nextTop - navOffset);

      // Snap down only while still within the intro region.
      if (delta > 0 && y < snapNextTop - 2) {
        e.preventDefault();
        snapTo(snapNextTop);
        return;
      }

      // Snap up only when near the top boundary (prevents hijacking mid-page).
      if (delta < 0 && y > 0 && y <= snapNextTop + 24) {
        e.preventDefault();
        snapTo(0);
      }
    };

    if (!reduced) {
      window.addEventListener("mousemove", handleMouseMove);
      window.addEventListener("mouseout", handleWindowLeave);
      rafId = requestAnimationFrame(animate);

      // Non-passive so we can preventDefault only in the intro snap zone
      window.addEventListener("wheel", handleWheel, { passive: false });
    }

    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseout", handleWindowLeave);
      window.removeEventListener("wheel", handleWheel as EventListener);
      if (rafId) cancelAnimationFrame(rafId);
      if (snapUnlockTimer) window.clearTimeout(snapUnlockTimer);
    };
  }, []);

  useEffect(() => {
    if (!allowMotion) return;
    const interval = window.setInterval(() => {
      setMontyStatusIndex((i) => (i + 1) % montyStatuses.length);
    }, 4200);
    return () => window.clearInterval(interval);
  }, [allowMotion, montyStatuses.length]);

  // Sticky CTA bar visibility based on scroll
  useEffect(() => {
    const handleScroll = () => {
      const scrollY = window.scrollY;
      // Show sticky CTA after scrolling past ~400px (past hero)
      setShowStickyCta(scrollY > 400);
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <main className="min-h-screen">
      {/* Sticky CTA Bar */}
      <div 
        className={`fixed bottom-0 left-0 right-0 z-50 bg-white/95 backdrop-blur-md border-t border-border/50 py-3 px-6 transition-transform duration-300 ${
          showStickyCta ? "translate-y-0" : "translate-y-full"
        }`}
      >
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="h-2.5 w-2.5 rounded-full bg-emerald-500 animate-pulse" />
            <span className="text-sm font-medium">Early access now open · This week’s cohort nearly full</span>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-xs text-muted-foreground hidden sm:inline">Personal onboarding included</span>
            <a href={loginHref} className="btn-primary text-sm py-2 px-4">
              Sign in →
            </a>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 z-50 bg-white/80 backdrop-blur-md border-b border-border/50">
        <div className="max-w-7xl mx-auto px-6 py-3 flex items-center justify-between">
          {/* Logo */}
          <div className="flex items-center gap-6">
            <div
              className="flex items-center gap-2"
              onMouseEnter={() => setIsLogoHovered(true)}
              onMouseLeave={() => setIsLogoHovered(false)}
            >
              <div
                className={`relative h-10 w-10 rounded-xl bg-gradient-to-br from-emerald-400 via-emerald-500 to-teal-600 
                           flex items-center justify-center shadow-lg shadow-emerald-500/25 cursor-pointer
                           transition-all duration-500 ${isLogoHovered ? 'scale-105 rotate-2' : ''}`}
              >
                <div
                  className={`absolute inset-0 rounded-xl border-2 border-emerald-400/50 transition-opacity duration-500 ${isLogoHovered ? 'opacity-100' : 'opacity-0'}`}
                  style={{ animation: isLogoHovered ? 'ping-slow 2s cubic-bezier(0, 0, 0.2, 1) infinite' : 'none' }}
                />
                <div className={`absolute -inset-1 rounded-xl bg-gradient-to-br from-emerald-400 to-teal-500 opacity-0 blur-lg transition-opacity duration-500 ${isLogoHovered ? 'opacity-50' : ''}`} />
                <Sparkles className={`h-5 w-5 text-white relative z-10 transition-all duration-300 ${isLogoHovered ? 'scale-110' : ''}`} />
                {isLogoHovered && (
                  <>
                    <div
                      className="absolute h-2 w-2 rounded-full bg-white"
                      style={{ animation: 'orbit 2s linear infinite' }}
                    />
                    <div
                      className="absolute h-1.5 w-1.5 rounded-full bg-emerald-200"
                      style={{ animation: 'orbit 3s linear infinite', animationDelay: '0.5s' }}
                    />
                  </>
                )}
              </div>
              <span className="font-semibold text-lg">Monty</span>
              <span className="text-xs text-muted-foreground">by AgentFlow</span>
            </div>

            {/* Toggle Pills */}
            <div className="hidden md:flex items-center gap-1 bg-secondary rounded-full p-1">
              <button className="nav-pill nav-pill-active">For sales teams</button>
              <button className="nav-pill nav-pill-inactive">For agencies</button>
            </div>
          </div>

          {/* Nav Links */}
          <div className="hidden lg:flex items-center gap-8">
            <button type="button" className="nav-link" onClick={() => scrollToSection("how")}>
              How It Works
            </button>
            <button type="button" className="nav-link" onClick={() => scrollToSection("benefits")}>
              Features
            </button>
            <button type="button" className="nav-link" onClick={() => scrollToSection("pricing")}>
              Pricing
            </button>
            <button type="button" className="nav-link" onClick={() => scrollToSection("ask-monty")}>
              Ask Monty
            </button>
            <button type="button" className="nav-link" onClick={() => scrollToSection("mission")}>
              Our Mission
            </button>
          </div>

          {/* CTA */}
          <a href={loginHref} className="btn-primary text-sm">
            Sign in
          </a>
        </div>
      </nav>

      {/* Intro */}
      <section className="intro-panel">
      <div className="hero-split">
        {/* Left: Scenic Panel with Orb */}
        <div ref={scenicRef} className="tech-bg relative flex items-end justify-center pb-32 lg:pb-40">
          {/* Smooth, technical overlays */}
          <div className="tech-mesh" />
          <svg
            className="tech-network-svg"
            viewBox="0 0 1000 1000"
            preserveAspectRatio="none"
            aria-hidden="true"
          >
            <defs>
              <linearGradient id="netStroke" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stopColor="#ffffff" stopOpacity="0.14" />
                <stop offset="45%" stopColor="#34d399" stopOpacity="0.22" />
                <stop offset="100%" stopColor="#60a5fa" stopOpacity="0.16" />
              </linearGradient>
              <filter id="netGlow" x="-50%" y="-50%" width="200%" height="200%">
                <feGaussianBlur stdDeviation="4" result="blur" />
                <feColorMatrix
                  in="blur"
                  type="matrix"
                  values="0 0 0 0 0.203  0 0 0 0 0.827  0 0 0 0 0.600  0 0 0 0.9 0"
                />
              </filter>
            </defs>

            {/* Edges */}
            <g fill="none" stroke="url(#netStroke)" strokeWidth="1.6" opacity="0.75">
              <path d="M 150 740 C 260 610 360 690 470 560 S 720 360 870 280" />
              <path d="M 180 260 C 320 220 420 360 560 320 S 760 220 900 180" />
              <path d="M 260 880 C 360 820 440 720 560 700 S 770 640 920 520" />
              <path d="M 120 520 C 260 480 320 420 440 420 S 680 460 840 420" />
            </g>

            {/* Nodes */}
            <g opacity="0.9">
              <circle cx="150" cy="740" r="7" fill="#34d399" fillOpacity="0.5" />
              <circle cx="470" cy="560" r="7" fill="#34d399" fillOpacity="0.45" />
              <circle cx="870" cy="280" r="7" fill="#60a5fa" fillOpacity="0.45" />
              <circle cx="180" cy="260" r="6" fill="#ffffff" fillOpacity="0.35" />
              <circle cx="900" cy="180" r="6" fill="#ffffff" fillOpacity="0.28" />
              <circle cx="920" cy="520" r="7" fill="#34d399" fillOpacity="0.35" />
            </g>

            {/* Single tracer */}
            {allowMotion ? (
              <circle r="7" fill="#34d399" filter="url(#netGlow)" opacity="0.9">
                <animateMotion
                  dur="7s"
                  repeatCount="indefinite"
                  path="M 150 740 C 260 610 360 690 470 560 S 720 360 870 280"
                />
                <animate attributeName="opacity" values="0.3;0.9;0.3" dur="1.8s" repeatCount="indefinite" />
              </circle>
            ) : null}
          </svg>
          <div className="atmospheric-mist" />

          {/* Orb Avatar and Speech Bubble */}
          <div className="relative z-10 flex flex-col items-center">
            {/* Speech Bubble */}
            <div
              className={`speech-bubble mb-6 ${
                isVisible ? "animate-fade-up" : "opacity-0"
              }`}
            >
              <div className="flex items-center gap-3">
                <span className="text-sm text-foreground font-medium">
                  {montyStatuses[montyStatusIndex]?.text ?? montyStatuses[0].text}
                </span>
                <button className="sound-btn flex-shrink-0">
                  <Volume2 className="w-4 h-4 text-muted-foreground" />
                </button>
              </div>
            </div>

            {/* Glowing Orb with Breathing Aura */}
            <div
              className={`orb-container orb-state-${montyStatuses[montyStatusIndex]?.state ?? "ready"} ${orbHover ? "orb-hover" : ""} ${
                isVisible ? "animate-fade-up delay-100" : "opacity-0"
              }`}
              style={{ animationFillMode: "forwards" }}
              ref={orbRef}
              onMouseEnter={handleOrbEnter}
              onMouseMove={handleOrbMove}
              onMouseLeave={handleOrbLeave}
            >
              <div className="orb-aura-outer" />
              <div className="orb-aura" />
              <div className="orb-surface">
                <svg className="orb-svg" viewBox="0 0 160 160" aria-hidden="true">
                  <defs>
                    {/* Main shell gradient */}
                    <radialGradient id="orbShell" cx="0.35" cy="0.35" r="0.9">
                      <stop offset="0%" stopColor="rgba(255,255,255,0.98)" />
                      <stop offset="35%" stopColor="rgba(255,255,255,0.92)" />
                      <stop offset="70%" stopColor="rgba(245,252,248,0.84)" />
                      <stop offset="100%" stopColor="rgba(230,245,238,0.76)" />
                    </radialGradient>

                    {/* Inner life: misty green essence */}
                    <radialGradient id="orbEssence1" cx="0.5" cy="0.6" r="0.7">
                      <stop offset="0%" stopColor="rgba(52,211,153,0.30)" />
                      <stop offset="50%" stopColor="rgba(52,211,153,0.12)" />
                      <stop offset="100%" stopColor="rgba(52,211,153,0)" />
                    </radialGradient>
                    <radialGradient id="orbEssence2" cx="0.4" cy="0.35" r="0.6">
                      <stop offset="0%" stopColor="rgba(110,231,183,0.24)" />
                      <stop offset="60%" stopColor="rgba(110,231,183,0.08)" />
                      <stop offset="100%" stopColor="rgba(110,231,183,0)" />
                    </radialGradient>
                    <radialGradient id="orbEssence3" cx="0.6" cy="0.5" r="0.5">
                      <stop offset="0%" stopColor="rgba(16,185,129,0.22)" />
                      <stop offset="70%" stopColor="rgba(16,185,129,0.07)" />
                      <stop offset="100%" stopColor="rgba(16,185,129,0)" />
                    </radialGradient>

                    {/* Highlight that follows cursor (subtle, warm) */}
                    <radialGradient id="orbHighlight" cx="0.35" cy="0.35" r="0.6">
                      <stop offset="0%" stopColor="rgba(255,255,255,0.9)" />
                      <stop offset="50%" stopColor="rgba(255,255,255,0.3)" />
                      <stop offset="100%" stopColor="rgba(255,255,255,0)" />
                    </radialGradient>

                    <clipPath id="orbClip">
                      <circle cx="80" cy="80" r="80" />
                    </clipPath>
                  </defs>

                  {/* Base shell */}
                  <g clipPath="url(#orbClip)">
                    <circle cx="80" cy="80" r="80" fill="url(#orbShell)" />

                    {/* Inner essence layers (animated in CSS) */}
                    <circle className="orb-essence orb-essence-1" cx="80" cy="90" r="70" fill="url(#orbEssence1)" />
                    <circle className="orb-essence orb-essence-2" cx="70" cy="70" r="55" fill="url(#orbEssence2)" />
                    <circle className="orb-essence orb-essence-3" cx="95" cy="80" r="45" fill="url(#orbEssence3)" />

                    {/* Moving highlight (follows cursor with spring lag) */}
                    <circle
                      ref={highlightRef}
                      cx="56"
                      cy="56"
                      r="50"
                      fill="url(#orbHighlight)"
                      opacity="0.7"
                    />
                  </g>
                </svg>
              </div>
            </div>
          </div>
        </div>

        {/* Right: Content Panel */}
        <div className="bg-white flex items-end px-8 lg:px-16 py-16 pb-20">
          <div className="max-w-xl">
            {/* Early Access Badge */}
            <div
              className={`offer-badge mb-8 ${
                isVisible ? "animate-fade-up" : "opacity-0"
              }`}
            >
              <Sparkles className="w-3.5 h-3.5 text-primary" />
              <span className="highlight">EARLY ACCESS</span>
              <span>•</span>
              <span>Limited spots available</span>
              <span>•</span>
              <span className="highlight">Personal onboarding included</span>
            </div>

            {/* Headline */}
            <h1
              className={`text-4xl lg:text-5xl font-bold leading-[1.15] tracking-tight mb-5 ${
                isVisible ? "animate-fade-up delay-100" : "opacity-0"
              }`}
              style={{ animationFillMode: "forwards" }}
            >
              Meet Monty, your
              <br />
              <span className="text-accent">Executive Inbox Co‑Pilot.</span>
            </h1>

            {/* Description */}
            <p
              className={`text-base text-muted-foreground leading-relaxed mb-6 ${
                isVisible ? "animate-fade-up delay-200" : "opacity-0"
              }`}
              style={{ animationFillMode: "forwards" }}
            >
              Monty drafts your{" "}
              <span className="text-foreground font-medium">outreach, follow-ups, and replies</span>
              —in review mode or full autopilot (your choice). You stay in control while{" "}
              <span className="text-foreground font-medium">closing more deals, faster</span>.
            </p>

            {/* CTAs */}
            <div
              className={`flex items-center gap-6 ${
                isVisible ? "animate-fade-up delay-300" : "opacity-0"
              }`}
              style={{ animationFillMode: "forwards" }}
            >
              <button className="btn-primary flex items-center gap-2">
                Request early access
              </button>
              <button className="btn-text">
                See how it works
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
            <div
              className={`mt-4 flex items-center gap-4 text-xs text-muted-foreground ${
                isVisible ? "animate-fade-up delay-400" : "opacity-0"
              }`}
              style={{ animationFillMode: "forwards" }}
            >
              <span>No credit card required</span>
              <span>•</span>
              <span>Setup takes 2 minutes</span>
              <span>•</span>
              <span>Personal onboarding included</span>
            </div>
          </div>
        </div>
      </div>

      </section>

      {/* Section: Social Proof + Dashboard Preview */}
      <section className="bg-white border-t border-border/30">
        <div className="max-w-7xl mx-auto px-8 lg:px-16 py-16">
          {/* Credibility indicators row */}
          <div className="flex flex-wrap items-center justify-center gap-8 mb-12 pb-10 border-b border-border/40">
            <div className="flex items-center gap-2">
              <Shield className="h-5 w-5 text-primary" />
              <span className="text-sm font-medium">Review mode or full autopilot</span>
            </div>
            <div className="flex items-center gap-2">
              <Lock className="h-5 w-5 text-primary" />
              <span className="text-sm font-medium">Guardrails + sending rules</span>
            </div>
            <div className="flex items-center gap-2">
              <Mail className="h-5 w-5 text-primary" />
              <span className="text-sm font-medium">Gmail + Outlook (OAuth)</span>
            </div>
          </div>

          {/* Early access callout */}
          <div className="text-center mb-12">
            <div className="inline-flex items-center gap-3 px-6 py-3 rounded-full bg-primary/5 border border-primary/20">
              <div className="h-2 w-2 rounded-full bg-primary animate-pulse" />
              <span className="text-sm font-medium">Now accepting early access applications</span>
              <span className="text-xs text-muted-foreground">· Personal onboarding for first cohort</span>
            </div>
          </div>

          {/* Dashboard Preview */}
          <div className="max-w-4xl mx-auto">
            <div className="text-center mb-10">
              <p className="text-sm text-muted-foreground mb-3">See it in action</p>
              <h2 className="text-2xl lg:text-3xl font-bold tracking-tight">
                Your portal, with AI drafts ready to review
              </h2>
            </div>

            <div className="rounded-2xl border border-border/60 bg-secondary/20 p-2 shadow-lg">
              <div className="rounded-xl bg-white p-6 min-h-[360px]">
                {/* Mock portal header */}
                <div className="flex items-center justify-between mb-6 pb-4 border-b border-border/40">
                  <div className="flex items-center gap-3">
                    <Mail className="h-5 w-5 text-primary" />
                    <span className="font-medium">Dashboard</span>
                    <span className="px-2.5 py-1 rounded-full bg-primary/10 text-primary text-xs font-medium">
                      3 drafts pending
                    </span>
                  </div>
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <Clock className="h-3.5 w-3.5" />
                    <span>Updated 2 min ago</span>
                  </div>
                </div>

                {/* Stats row */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
                  {[
                    { label: 'Drafts pending', value: '3', color: 'bg-amber-500/10 text-amber-600' },
                    { label: 'Emails sent', value: '127', color: 'bg-blue-500/10 text-blue-600' },
                    { label: 'Active leads', value: '48', color: 'bg-emerald-500/10 text-emerald-600' },
                    { label: 'Response rate', value: '34%', color: 'bg-purple-500/10 text-purple-600' },
                  ].map((stat) => (
                    <div key={stat.label} className="rounded-xl border border-border/50 bg-secondary/20 p-3">
                      <div className={`inline-flex items-center justify-center rounded-lg px-2.5 py-1 text-xs font-medium ${stat.color}`}>
                        {stat.value}
                      </div>
                      <div className="mt-2 text-xs text-muted-foreground">{stat.label}</div>
                    </div>
                  ))}
                </div>

                {/* Pending drafts list */}
                <div className="space-y-3">
                  {[
                    { initials: 'SC', from: 'Sarah Chen', subject: 'Re: Pricing question for enterprise', time: '2m', gradient: 'from-emerald-400 to-teal-500', context: 'Uses past 4 emails for voice match' },
                    { initials: 'MJ', from: 'Marcus Johnson', subject: 'Following up on last week\'s demo', time: '5m', gradient: 'from-blue-400 to-indigo-500', context: 'Pulls product notes + last demo recap' },
                    { initials: 'ER', from: 'Elena Rodriguez', subject: 'Partnership inquiry - Q2 goals', time: '12m', gradient: 'from-purple-400 to-pink-500', context: 'Qualified as high-intent lead' },
                  ].map((email, i) => (
                    <div
                      key={i}
                      className="flex items-start gap-4 p-4 rounded-xl bg-secondary/30 border border-border/40 hover:border-primary/30 hover:bg-secondary/50 transition-all cursor-pointer group"
                    >
                      <div className={`h-10 w-10 rounded-full bg-gradient-to-br ${email.gradient} flex items-center justify-center text-white text-sm font-medium shadow-sm`}>
                        {email.initials}
                      </div>
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-medium truncate">{email.from}</span>
                          <span className="text-xs text-muted-foreground">{email.time}</span>
                        </div>
                        <div className="text-sm text-muted-foreground truncate group-hover:line-clamp-2 group-hover:whitespace-normal">
                          {email.subject}
                        </div>
                        <div className="text-[11px] text-muted-foreground mt-1 opacity-0 group-hover:opacity-100 transition-opacity">
                          {email.context}
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="text-right">
                          <span className="px-2.5 py-1 rounded-full bg-amber-50 text-amber-700 text-xs font-medium border border-amber-200 block">
                            AI Draft Ready
                          </span>
                          <span className="text-[10px] text-muted-foreground mt-1 block">Review queue</span>
                        </div>
                        <button className="px-3 py-1.5 rounded-lg bg-primary text-white text-xs font-medium hover:bg-primary/90 transition-colors opacity-0 group-hover:opacity-100">
                          Review
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
            <div className="mt-6 flex flex-col sm:flex-row items-center justify-center gap-4">
              <button className="inline-flex items-center gap-2 text-sm text-primary hover:text-primary/80 transition-colors font-medium">
                <Play className="h-4 w-4" />
                Watch a 2-minute demo
              </button>
              <button className="btn-text">
                Try the live demo
                <ArrowRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        </div>
      </section>

      {/* Section: How it works */}
      <section id="how" className="bg-gradient-to-b from-secondary/40 to-white scroll-mt-24">
        <div className="max-w-7xl mx-auto px-8 lg:px-16 py-20">
          <div className="text-center mb-14">
            <p className="text-sm text-muted-foreground mb-3">How it works</p>
            <h2 className="text-3xl lg:text-4xl font-bold tracking-tight">
              From inbox chaos to calm in 3 steps
            </h2>
            <p className="mt-4 text-base text-muted-foreground max-w-2xl mx-auto">
              Most teams see their first AI-drafted reply within 5 minutes of connecting.
            </p>
          </div>

          {/* Timeline visual */}
          <div className="flex items-center justify-center gap-4 mb-10 text-xs text-muted-foreground">
            <div className="flex items-center gap-2">
              <div className="h-2 w-2 rounded-full bg-primary" />
              <span>Day 1: First drafts</span>
            </div>
            <div className="h-px w-8 bg-border" />
            <div className="flex items-center gap-2">
              <div className="h-2 w-2 rounded-full bg-primary/60" />
              <span>Day 3: Voice calibrated</span>
            </div>
            <div className="h-px w-8 bg-border" />
            <div className="flex items-center gap-2">
              <div className="h-2 w-2 rounded-full bg-primary/40" />
              <span>Day 7: 50% faster replies</span>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            <div className="relative rounded-2xl border border-border/60 bg-white p-8 shadow-sm hover:shadow-md hover:-translate-y-1 transition-all">
              <div className="h-11 w-11 rounded-xl bg-primary/10 text-primary flex items-center justify-center mb-4">
                <Mail className="h-5 w-5" />
              </div>
              <span className="text-4xl font-bold text-muted-foreground/15 absolute top-6 right-6">01</span>
              <h3 className="text-lg font-semibold mb-2">Connect in 2 minutes</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">
                Link Gmail or Outlook securely. We only read what you authorize—your data never leaves your control.
              </p>
              <div className="hidden md:block absolute top-1/2 -right-4 w-8 h-0.5 bg-border z-10" />
            </div>

            <div className="relative rounded-2xl border border-border/60 bg-white p-8 shadow-sm hover:shadow-md hover:-translate-y-1 transition-all">
              <div className="h-11 w-11 rounded-xl bg-primary/10 text-primary flex items-center justify-center mb-4">
                <MessageSquare className="h-5 w-5" />
              </div>
              <span className="text-4xl font-bold text-muted-foreground/15 absolute top-6 right-6">02</span>
              <h3 className="text-lg font-semibold mb-2">Monty drafts replies in your voice</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">
                Monty learns from your sent emails and drafts replies that sound like you—fast, consistent, and on-brand.
              </p>
              <div className="hidden md:block absolute top-1/2 -right-4 w-8 h-0.5 bg-border z-10" />
            </div>

            <div className="relative rounded-2xl border border-border/60 bg-white p-8 shadow-sm hover:shadow-md hover:-translate-y-1 transition-all">
              <div className="h-11 w-11 rounded-xl bg-primary/10 text-primary flex items-center justify-center mb-4">
                <CheckCircle2 className="h-5 w-5" />
              </div>
              <span className="text-4xl font-bold text-muted-foreground/15 absolute top-6 right-6">03</span>
              <h3 className="text-lg font-semibold mb-2">Review or autopilot—your choice</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">
                Start with a review queue, or enable full automation with rules and guardrails when you're ready.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Section: Stats */}
      <section className="bg-white">
        <div className="max-w-5xl mx-auto px-8 lg:px-16 py-16">
          <div className="rounded-2xl bg-gradient-to-br from-primary/5 via-transparent to-accent/5 border border-border/40 p-10">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-8 text-center">
              {[
                { value: '73%', label: 'Faster response times' },
                { value: '10+', label: 'Hours saved per week' },
                { value: '94%', label: 'Customer satisfaction' },
                { value: '3x', label: 'More leads handled' },
              ].map((stat, i) => (
                <div key={i}>
                  <div className="text-3xl md:text-4xl font-bold text-primary mb-1">{stat.value}</div>
                  <div className="text-sm text-muted-foreground">{stat.label}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Section: Full Capabilities */}
      <section className="bg-white border-t border-border/30">
        <div className="max-w-7xl mx-auto px-8 lg:px-16 py-20">
          <div className="text-center mb-14">
            <p className="text-sm text-muted-foreground mb-3">More than drafts</p>
            <h2 className="text-3xl lg:text-4xl font-bold tracking-tight">
              Your complete sales automation engine
            </h2>
            <p className="mt-4 text-base text-muted-foreground max-w-2xl mx-auto">
              Monty doesn't just reply—it builds prospect profiles, qualifies leads, re-engages cold contacts, and books meetings. You only step in for the final call.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {/* Prospect Profiles */}
            <div className="rounded-2xl border border-border/60 bg-secondary/20 p-6 hover:shadow-md transition-shadow">
              <div className="h-11 w-11 rounded-xl bg-blue-100 text-blue-600 flex items-center justify-center mb-4">
                <UserCheck className="h-5 w-5" />
              </div>
              <h3 className="text-lg font-semibold mb-2">Custom Prospect Profiles</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">
                Monty researches each prospect and builds a profile—company, role, interests, past interactions—so every touchpoint feels personal.
              </p>
            </div>

            {/* Lead Qualification */}
            <div className="rounded-2xl border border-border/60 bg-secondary/20 p-6 hover:shadow-md transition-shadow">
              <div className="h-11 w-11 rounded-xl bg-emerald-100 text-emerald-600 flex items-center justify-center mb-4">
                <Target className="h-5 w-5" />
              </div>
              <h3 className="text-lg font-semibold mb-2">Automatic Qualification</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">
                Define your ideal customer criteria once. Monty scores and qualifies prospects automatically, surfacing your hottest leads first.
              </p>
            </div>

            {/* Re-engagement */}
            <div className="rounded-2xl border border-border/60 bg-secondary/20 p-6 hover:shadow-md transition-shadow">
              <div className="h-11 w-11 rounded-xl bg-amber-100 text-amber-600 flex items-center justify-center mb-4">
                <RefreshCw className="h-5 w-5" />
              </div>
              <h3 className="text-lg font-semibold mb-2">Smart Re-engagement</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">
                Cold leads don't stay cold. Monty monitors stalled conversations and drafts timely re-engagement messages to bring prospects back.
              </p>
            </div>

            {/* Meeting Booking */}
            <div className="rounded-2xl border border-border/60 bg-secondary/20 p-6 hover:shadow-md transition-shadow">
              <div className="h-11 w-11 rounded-xl bg-purple-100 text-purple-600 flex items-center justify-center mb-4">
                <Calendar className="h-5 w-5" />
              </div>
              <h3 className="text-lg font-semibold mb-2">Automated Meeting Booking</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">
                Once a prospect is ready, Monty handles the back-and-forth scheduling and books the call directly on your calendar.
              </p>
            </div>

            {/* Exec Briefings */}
            <div className="rounded-2xl border border-border/60 bg-secondary/20 p-6 hover:shadow-md transition-shadow">
              <div className="h-11 w-11 rounded-xl bg-indigo-100 text-indigo-600 flex items-center justify-center mb-4">
                <FileText className="h-5 w-5" />
              </div>
              <h3 className="text-lg font-semibold mb-2">Pre-Call Briefings</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">
                Before every call, you get a one-page brief: prospect profile, conversation history, pain points, and suggested talking points.
              </p>
            </div>

            {/* Final stage focus */}
            <div className="rounded-2xl border border-primary/40 bg-primary/5 p-6 hover:shadow-md transition-shadow">
              <div className="h-11 w-11 rounded-xl bg-primary/20 text-primary flex items-center justify-center mb-4">
                <Zap className="h-5 w-5" />
              </div>
              <h3 className="text-lg font-semibold mb-2">You Only Close</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">
                Your time goes where it matters most: the final sales call. Everything before that—Monty handles.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Section: Benefits & proof */}
      <section id="benefits" className="bg-secondary/20 scroll-mt-24">
        <div className="max-w-7xl mx-auto px-8 lg:px-16 py-20">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-start">
            <div>
              <p className="text-sm text-muted-foreground mb-3">Why teams choose Monty</p>
              <h2 className="text-3xl lg:text-4xl font-bold tracking-tight">
                Stop losing deals
                <br />
                to slow replies.
              </h2>
              <p className="mt-4 text-base text-muted-foreground max-w-prose">
                Every hour you wait to reply, your prospect gets colder. Monty keeps you fast without sacrificing quality.
              </p>

              {/* Before/After comparison */}
              <div className="mt-8 grid grid-cols-2 gap-4 text-sm">
                <div className="rounded-xl bg-red-50 border border-red-100 p-4">
                  <p className="font-medium text-red-700 mb-3 flex items-center gap-2">
                    <AlertCircle className="h-4 w-4" />
                    Without Monty
                  </p>
                  <ul className="space-y-2 text-red-600/80">
                    <li>4-hour avg response time</li>
                    <li>Typing same follow-ups daily</li>
                    <li>Prospects going cold</li>
                  </ul>
                </div>
                <div className="rounded-xl bg-emerald-50 border border-emerald-100 p-4">
                  <p className="font-medium text-emerald-700 mb-3 flex items-center gap-2">
                    <TrendingUp className="h-4 w-4" />
                    With Monty
                  </p>
                  <ul className="space-y-2 text-emerald-600/80">
                    <li>27-minute avg response</li>
                    <li>Approve or autopilot</li>
                    <li>Warm replies, always</li>
                  </ul>
                </div>
              </div>
            </div>

            <div className="space-y-6">
              <div className="rounded-2xl border border-border/60 bg-secondary/40 p-6">
                <div className="flex items-center gap-3 mb-3">
                  <Shield className="h-5 w-5 text-primary" />
                  <p className="font-semibold">Review mode or autopilot</p>
                </div>
                <p className="text-sm text-muted-foreground">
                  Start with review, then automate sends when you're ready—with rules, schedules, and guardrails.
                </p>
              </div>
              <div className="rounded-2xl border border-border/60 bg-secondary/40 p-6">
                <div className="flex items-center gap-3 mb-3">
                  <Zap className="h-5 w-5 text-primary" />
                  <p className="font-semibold">Faster response cycles</p>
                </div>
                <p className="text-sm text-muted-foreground">
                  Respond in minutes, not days—without sacrificing tone or context.
                </p>
              </div>
              <div className="rounded-2xl border border-border/60 bg-secondary/40 p-6">
                <div className="flex items-center gap-3 mb-3">
                  <Users className="h-5 w-5 text-primary" />
                  <p className="font-semibold">Team-ready from day one</p>
                </div>
                <p className="text-sm text-muted-foreground">
                  Shared templates, unified tone, and clear ownership across the team.
                </p>
              </div>

              {/* Use case scenarios */}
              <div className="rounded-2xl border border-border/60 bg-white p-6">
                <p className="text-xs text-muted-foreground uppercase tracking-wider mb-4">Built for</p>
                <div className="space-y-4">
                  <div className="flex items-start gap-3">
                    <div className="h-8 w-8 rounded-lg bg-blue-50 flex items-center justify-center text-blue-600 text-xs font-medium">SDR</div>
                    <div>
                      <p className="font-medium text-sm">Sales Development Reps</p>
                      <p className="text-xs text-muted-foreground">Auto-qualify leads & book meetings on autopilot</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <div className="h-8 w-8 rounded-lg bg-emerald-50 flex items-center justify-center text-emerald-600 text-xs font-medium">AE</div>
                    <div>
                      <p className="font-medium text-sm">Account Executives</p>
                      <p className="text-xs text-muted-foreground">Pre-call briefs & warm nurturing on autopilot</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <div className="h-8 w-8 rounded-lg bg-purple-50 flex items-center justify-center text-purple-600 text-xs font-medium">CEO</div>
                    <div>
                      <p className="font-medium text-sm">Founders & Execs</p>
                      <p className="text-xs text-muted-foreground">Only step in for the final close—everything else is handled</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Section: Use cases */}
      <section className="bg-white border-t border-border/30">
        <div className="max-w-7xl mx-auto px-8 lg:px-16 py-20">
          <div className="text-center mb-12">
            <p className="text-sm text-muted-foreground mb-3">Use cases</p>
            <h2 className="text-3xl lg:text-4xl font-bold tracking-tight">
              Built for real conversations
            </h2>
            <p className="mt-4 text-base text-muted-foreground max-w-2xl mx-auto">
              Monty helps you stay fast and human across every stage—from first touch to follow-up to inbound replies.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="rounded-2xl border border-border/60 bg-secondary/20 p-7 hover:shadow-md transition-shadow">
              <div className="h-11 w-11 rounded-xl bg-primary/10 text-primary flex items-center justify-center mb-4">
                <Mail className="h-5 w-5" />
              </div>
              <h3 className="text-lg font-semibold mb-2">Cold outreach</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">
                You upload a lead list. Monty researches each prospect, writes personalized first touches, and sends on your schedule.
              </p>
            </div>

            <div className="rounded-2xl border border-border/60 bg-secondary/20 p-7 hover:shadow-md transition-shadow">
              <div className="h-11 w-11 rounded-xl bg-primary/10 text-primary flex items-center justify-center mb-4">
                <RefreshCw className="h-5 w-5" />
              </div>
              <h3 className="text-lg font-semibold mb-2">Follow-up sequences</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">
                Monty tracks who hasn’t replied and drafts perfectly-timed follow-ups—so conversations don’t stall.
              </p>
            </div>

            <div className="rounded-2xl border border-border/60 bg-secondary/20 p-7 hover:shadow-md transition-shadow">
              <div className="h-11 w-11 rounded-xl bg-primary/10 text-primary flex items-center justify-center mb-4">
                <Target className="h-5 w-5" />
              </div>
              <h3 className="text-lg font-semibold mb-2">Inbound qualification</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">
                A lead emails you. Monty qualifies intent, drafts a response, and routes the conversation based on your rules.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Section: Pricing */}
      <section id="pricing" className="bg-secondary/40 scroll-mt-24">
        <div className="max-w-7xl mx-auto px-8 lg:px-16 py-20">
          <div className="text-center mb-14">
            <p className="text-sm text-muted-foreground mb-3">Pricing</p>
            <h2 className="text-3xl lg:text-4xl font-bold tracking-tight">
              Simple plans for focused teams
            </h2>
            <p className="mt-4 text-base text-muted-foreground max-w-2xl mx-auto">
              Start free, upgrade when you're ready. No credit card required.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-4xl mx-auto">
            <div className="rounded-2xl border border-border/60 bg-white p-8 shadow-sm hover:shadow-md transition-shadow">
              <p className="text-sm font-medium text-muted-foreground">Starter</p>
              <div className="mt-3 flex items-baseline gap-1">
                <span className="text-4xl font-bold">$0</span>
                <span className="text-muted-foreground">/month</span>
              </div>
              <p className="text-sm text-muted-foreground mt-2">Perfect for trying Monty solo</p>
              <ul className="mt-8 space-y-4 text-sm">
                <li className="flex items-start gap-3">
                  <CheckCircle2 className="h-5 w-5 text-primary shrink-0 mt-0.5" />
                  <span>1 inbox connection (Gmail or Outlook)</span>
                </li>
                <li className="flex items-start gap-3">
                  <CheckCircle2 className="h-5 w-5 text-primary shrink-0 mt-0.5" />
                  <span>AI-drafted replies & follow-ups</span>
                </li>
                <li className="flex items-start gap-3">
                  <CheckCircle2 className="h-5 w-5 text-primary shrink-0 mt-0.5" />
                  <span>Configurable automation (review or autopilot)</span>
                </li>
                <li className="flex items-start gap-3">
                  <CheckCircle2 className="h-5 w-5 text-primary shrink-0 mt-0.5" />
                  <span>50 drafts/month — plenty for most solo sellers</span>
                </li>
              </ul>
              <button className="btn-primary mt-8 w-full">Request early access</button>
              <p className="text-xs text-center text-muted-foreground mt-3">Personal onboarding included</p>
            </div>

            <div className="relative rounded-2xl border-2 border-primary/50 bg-white p-8 shadow-lg">
              <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                <span className="text-xs font-medium bg-primary text-primary-foreground px-4 py-1.5 rounded-full shadow-sm">
                  Recommended
                </span>
              </div>
              <p className="text-sm font-medium text-muted-foreground">Team</p>
              <div className="mt-3 flex items-baseline gap-1">
                <span className="text-4xl font-bold">$49</span>
                <span className="text-muted-foreground">/seat/month</span>
              </div>
              <p className="text-xs text-primary mt-1">$39/seat billed annually (save 20%)</p>
              <p className="text-sm text-muted-foreground mt-2">For sales & support teams</p>
              <ul className="mt-8 space-y-4 text-sm">
                <li className="flex items-start gap-3">
                  <CheckCircle2 className="h-5 w-5 text-primary shrink-0 mt-0.5" />
                  <span>Unlimited inbox connections</span>
                </li>
                <li className="flex items-start gap-3">
                  <CheckCircle2 className="h-5 w-5 text-primary shrink-0 mt-0.5" />
                  <span>Shared voice & template library</span>
                </li>
                <li className="flex items-start gap-3">
                  <CheckCircle2 className="h-5 w-5 text-primary shrink-0 mt-0.5" />
                  <span>Team review queue + automation rules</span>
                </li>
                <li className="flex items-start gap-3">
                  <CheckCircle2 className="h-5 w-5 text-primary shrink-0 mt-0.5" />
                  <span>Advanced analytics & reporting</span>
                </li>
                <li className="flex items-start gap-3">
                  <CheckCircle2 className="h-5 w-5 text-primary shrink-0 mt-0.5" />
                  <span>Priority support & onboarding</span>
                </li>
              </ul>
              <button className="btn-primary mt-8 w-full">Request team access</button>
              <p className="text-xs text-center text-muted-foreground mt-3">We'll reach out within 24 hours</p>
            </div>
          </div>

          {/* Enterprise tier */}
          <div className="mt-8 max-w-4xl mx-auto">
            <div className="rounded-2xl border border-border/60 bg-white p-8 flex flex-col md:flex-row items-center justify-between gap-6">
              <div>
                <p className="text-sm font-medium text-muted-foreground">Enterprise</p>
                <p className="text-2xl font-bold mt-1">Custom pricing</p>
                <p className="text-sm text-muted-foreground mt-1">
                  For large teams with custom security, compliance, and integration needs.
                </p>
              </div>
              <div className="flex flex-col sm:flex-row items-center gap-4">
                <div className="flex items-center gap-3 text-sm text-muted-foreground">
                  <div className="flex items-center gap-1.5">
                    <Lock className="h-4 w-4" />
                    <span>SSO</span>
                  </div>
                  <span>•</span>
                  <span>SLA</span>
                  <span>•</span>
                  <span>Dedicated support</span>
                </div>
                <button className="btn-text whitespace-nowrap">Talk to sales →</button>
              </div>
            </div>
          </div>

          {/* Early access note */}
          <p className="text-center text-sm text-muted-foreground mt-8">
            Early access pricing · <span className="text-primary font-medium">First cohort gets lifetime rate lock</span>
          </p>

          {/* Pricing mini-FAQ */}
          <div className="mt-10 max-w-4xl mx-auto grid grid-cols-1 md:grid-cols-3 gap-4">
            {[
              {
                q: 'Can I switch plans anytime?',
                a: 'Yes. Upgrade or downgrade instantly from your dashboard.',
              },
              {
                q: 'What happens after 50 drafts?',
                a: 'You can upgrade or wait until the next month resets.',
              },
              {
                q: 'Do unused drafts roll over?',
                a: 'Not yet. We keep pricing simple and predictable.',
              },
            ].map((item) => (
              <div key={item.q} className="rounded-xl border border-border/60 bg-white p-5">
                <p className="text-sm font-semibold">{item.q}</p>
                <p className="mt-2 text-sm text-muted-foreground">{item.a}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Section: Ask Monty (placeholder copilot) */}
      <section id="ask-monty" className="bg-white scroll-mt-24">
        <div className="max-w-7xl mx-auto px-8 lg:px-16 py-20">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-14 items-start">
            <div>
              <p className="text-sm text-muted-foreground mb-3">Talk to Monty</p>
              <h2 className="text-3xl lg:text-4xl font-bold tracking-tight">
                Questions before you sign up?
              </h2>
              <p className="mt-4 text-base text-muted-foreground max-w-prose">
                This is a placeholder for the internal Monty copilot. It’s here so prospects can ask quick FAQ-style questions
                (pricing, security, autopilot rules) and reduce objections before onboarding.
              </p>

              <div className="mt-8">
                <p className="text-sm font-medium mb-3">Try a common question:</p>
                <div className="flex flex-wrap gap-2">
                  {["Is Monty secure with our email data?", "Does Monty send emails automatically?", "What does pricing look like for a team?", "How fast is setup?"]
                    .map((prompt) => (
                      <button
                        key={prompt}
                        type="button"
                        className="px-3 py-1.5 rounded-full bg-secondary text-sm text-foreground hover:bg-secondary/80 transition-colors"
                        onClick={() => setChatInput(prompt)}
                      >
                        {prompt}
                      </button>
                    ))}
                </div>
              </div>
            </div>

            <div className="rounded-2xl border border-border/60 bg-secondary/20 p-6">
              <div className="flex items-center justify-between">
                <p className="font-semibold">Ask Monty</p>
                <span className="text-xs text-muted-foreground">Placeholder</span>
              </div>

              <div className="mt-4 h-72 overflow-y-auto pr-1 space-y-3">
                {chatMessages.map((m, idx) => (
                  <div
                    key={idx}
                    className={
                      m.role === "user"
                        ? "flex justify-end"
                        : "flex justify-start"
                    }
                  >
                    <div
                      className={
                        m.role === "user"
                          ? "max-w-[85%] rounded-2xl bg-primary text-primary-foreground px-4 py-3 text-sm"
                          : "max-w-[85%] rounded-2xl bg-white border border-border/60 px-4 py-3 text-sm"
                      }
                    >
                      {m.content}
                    </div>
                  </div>
                ))}
              </div>

              <div className="mt-4 flex gap-2">
                <input
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      handleChatSend();
                    }
                  }}
                  placeholder="Ask about pricing, security, or autopilot…"
                  className="flex-1 rounded-xl border border-border/60 bg-white px-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-primary/20"
                />
                <button
                  type="button"
                  className="btn-primary"
                  onClick={handleChatSend}
                  disabled={!chatInput.trim()}
                >
                  Send
                </button>
              </div>

              <p className="mt-3 text-xs text-muted-foreground">
                This is a UI placeholder today (no backend). Next step is wiring it to your RAG + policy layer for accurate,
                tenant-safe answers.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* Section: FAQ + Mission + CTA */}
      <section id="faq" className="bg-white scroll-mt-24">
        <div className="max-w-7xl mx-auto px-8 lg:px-16 py-20">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-16">
            <div>
              <p className="text-sm text-muted-foreground mb-3">FAQ</p>
              <h2 className="text-3xl lg:text-4xl font-bold tracking-tight">
                Clarity before you commit
              </h2>
              <div className="mt-8 space-y-4">
                {[
                  {
                    q: "Does Monty send emails automatically?",
                    a: "Yes—if you want it to. Monty supports review mode and full automation. Start with approvals, then switch to autopilot with rules and guardrails when you're ready.",
                  },
                  {
                    q: "What if the AI writes something wrong?",
                    a: "In review mode, you can edit or reject drafts before they send. In autopilot, you set rules/guardrails so Monty only sends within your boundaries.",
                  },
                  {
                    q: "Can Monty match our company's voice?",
                    a: "Yes. Monty learns from your sent emails and examples you provide. The more context it has, the better it adapts to your style.",
                  },
                  {
                    q: "How does the early access work?",
                    a: "We onboard a small cohort at a time so we can give personal attention to each team. You'll get a 1-on-1 setup call and direct access to our founding team.",
                  },
                  {
                    q: "Is my email data secure?",
                    a: "Enterprise-grade security. We use OAuth (scoped permissions) and can share the exact access model and data handling details during onboarding.",
                  },
                  {
                    q: "Can I use this with my team?",
                    a: "Absolutely. Our Team plan includes shared templates, unified voice settings, and team controls—review queues and/or automation rules—so everyone stays consistent.",
                  },
                ].map((item) => (
                  <div key={item.q} className="rounded-xl border border-border/60 p-5 hover:border-primary/30 transition-colors">
                    <p className="font-medium">{item.q}</p>
                    <p className="mt-2 text-sm text-muted-foreground">{item.a}</p>
                  </div>
                ))}
              </div>
            </div>

            <div id="mission" className="lg:sticky lg:top-8 h-fit scroll-mt-24">
              <p className="text-sm text-muted-foreground mb-3">Our mission</p>
              <h3 className="text-2xl font-semibold">Make every reply feel human—and on time.</h3>
              <p className="mt-4 text-base text-muted-foreground">
                We built Monty to remove the busywork while protecting the relationship. Fast drafts, clear controls,
                and a calm system that helps your team show up consistently.
              </p>

              <div className="mt-8 rounded-2xl border border-border/60 bg-gradient-to-br from-primary/5 to-primary/10 p-8">
                <div className="flex items-center gap-3">
                  <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center">
                    <Clock className="h-5 w-5 text-primary" />
                  </div>
                  <p className="font-semibold text-lg">Ready in minutes</p>
                </div>
                <p className="mt-4 text-sm text-muted-foreground">
                  Connect your inbox now and see your first AI-drafted reply within 5 minutes. No training period, no complex setup.
                </p>
                <div className="mt-6 flex flex-col sm:flex-row gap-3">
                  <button className="btn-primary">Request early access →</button>
                  <button className="btn-text">Talk to the team</button>
                </div>
                
                {/* Early access promise */}
                <div className="mt-6 p-4 rounded-xl bg-white/60 border border-border/40">
                  <p className="text-sm text-muted-foreground">
                    <span className="font-medium text-foreground">Early access includes:</span> 1-on-1 onboarding, direct Slack access to founders, and your feedback shapes the product.
                  </p>
                </div>

                <p className="mt-4 text-xs text-muted-foreground flex items-center gap-2">
                  <Shield className="h-3.5 w-3.5" />
                  Limited spots · No credit card required
                </p>
              </div>

              {/* Early access note */}
              <div className="mt-6 p-4 rounded-xl bg-secondary/50 border border-border/40">
                <p className="text-sm text-muted-foreground">
                  <span className="font-medium text-foreground">Early access includes:</span> Personal onboarding call, priority support, and direct line to the founding team.
                </p>
              </div>
            </div>
          </div>

          <div className="mt-20 border-t border-border/60 pt-12">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
              <div>
                <p className="font-semibold">Monty</p>
                <p className="mt-2 text-sm text-muted-foreground">
                  AI-powered email assistant that drafts, queues, and helps you respond faster—without losing your voice.
                </p>
              </div>
              <div>
                <p className="font-medium text-sm">Product</p>
                <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
                  <li><a href="#" className="hover:text-foreground transition-colors">Features</a></li>
                  <li><a href="#pricing" className="hover:text-foreground transition-colors">Pricing</a></li>
                  <li><a href="#" className="hover:text-foreground transition-colors">Integrations</a></li>
                  <li><a href="#" className="hover:text-foreground transition-colors">Changelog</a></li>
                </ul>
              </div>
              <div>
                <p className="font-medium text-sm">Company</p>
                <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
                  <li><a href="#" className="hover:text-foreground transition-colors">About</a></li>
                  <li><a href="#" className="hover:text-foreground transition-colors">Blog</a></li>
                  <li><a href="#" className="hover:text-foreground transition-colors">Careers</a></li>
                  <li><a href="#" className="hover:text-foreground transition-colors">Contact</a></li>
                </ul>
              </div>
              <div>
                <p className="font-medium text-sm">Legal</p>
                <ul className="mt-3 space-y-2 text-sm text-muted-foreground">
                  <li><a href="#" className="hover:text-foreground transition-colors">Privacy Policy</a></li>
                  <li><a href="#" className="hover:text-foreground transition-colors">Terms of Service</a></li>
                  <li><a href="#" className="hover:text-foreground transition-colors">Security</a></li>
                  <li><a href="#" className="hover:text-foreground transition-colors">GDPR</a></li>
                </ul>
              </div>
            </div>

            {/* Trust badges */}
            <div className="mt-10 pt-6 border-t border-border/40">
              <p className="text-xs text-muted-foreground uppercase tracking-wider mb-4">Security & Compliance</p>
              <div className="flex flex-wrap items-center gap-6 text-sm text-muted-foreground">
                <div className="flex items-center gap-2">
                  <Shield className="h-4 w-4" />
                  <span>SOC 2 Compliant</span>
                </div>
                <div className="flex items-center gap-2">
                  <Lock className="h-4 w-4" />
                  <span>256-bit Encryption</span>
                </div>
                <div className="flex items-center gap-2">
                  <Shield className="h-4 w-4" />
                  <span>GDPR Ready</span>
                </div>
                <div className="flex items-center gap-2 text-xs px-3 py-1.5 rounded-full bg-secondary/50">
                  Your data never trains our AI
                </div>
              </div>
            </div>

            <div className="mt-8 pt-6 border-t border-border/40 text-sm text-muted-foreground flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
              <span>© 2026 AgentFlow AI. All rights reserved.</span>
              <div className="flex items-center gap-4">
                <a href="#" className="hover:text-foreground transition-colors">Twitter</a>
                <a href="#" className="hover:text-foreground transition-colors">LinkedIn</a>
                <a href="#" className="hover:text-foreground transition-colors">GitHub</a>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Bottom padding for sticky CTA */}
      <div className="h-16" />
    </main>
  );
}
