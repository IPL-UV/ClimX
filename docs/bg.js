(() => {
  // Only run on the landing page (hero exists).
  const hero = document.querySelector(".hero");
  if (!hero) return;

  // Respect accessibility preferences.
  const reduceMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
  if (reduceMotion) return;

  const canvas = document.getElementById("bg-canvas");
  if (!canvas) return;

  const ctx = canvas.getContext("2d", { alpha: true });
  if (!ctx) return;

  // Styling knobs: subtle, "data connections" vibe.
  const COLORS = {
    node: "rgba(255, 255, 255, 0.55)",
    nodeGlow: "rgba(39, 174, 96, 0.20)",
    line: "rgba(255, 255, 255, 0.14)",
    lineAccent: "rgba(39, 174, 96, 0.20)",
  };

  const DPR = Math.min(window.devicePixelRatio || 1, 2);
  const state = {
    w: 0,
    h: 0,
    nodes: [],
    mouseX: null,
    mouseY: null,
    mouseInfluence: 0, // 0 = wander, 1 = orbit around mouse
    raf: null,
    lastT: performance.now(),
    cx: 0,
    cy: 0,
    targetX: 0,
    targetY: 0,
  };

  function sizeCanvas() {
    // Render only over the hero region (so it’s always visible on top of the hero background).
    const rect = hero.getBoundingClientRect();
    const w = Math.max(1, Math.floor(rect.width));
    const h = Math.max(1, Math.floor(rect.height));
    state.w = w;
    state.h = h;
    canvas.width = Math.floor(w * DPR);
    canvas.height = Math.floor(h * DPR);
    canvas.style.width = `${w}px`;
    canvas.style.height = `${h}px`;
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
  }

  function rand(min, max) {
    return min + Math.random() * (max - min);
  }

  function randn() {
    // Box–Muller transform
    let u = 0;
    let v = 0;
    while (u === 0) u = Math.random();
    while (v === 0) v = Math.random();
    return Math.sqrt(-2.0 * Math.log(u)) * Math.cos(2.0 * Math.PI * v);
  }

  function lerp(a, b, t) {
    return a + (b - a) * t;
  }

  function makeNodes() {
    const isSmall = Math.min(state.w, state.h) < 820;
    // Orbit field: spread around the mouse with continuous radial oscillation.
    const count = isSmall ? 22 : 36;

    const minR = isSmall ? 28 : 40;
    const maxR = isSmall ? 190 : 280;

    state.nodes = Array.from({ length: count }, (_, i) => {
      // Evenly distribute angles to prevent clumping.
      const angle = (i / count) * Math.PI * 2 + rand(-0.15, 0.15);
      // Bias radii outward for a more “spread” feel.
      const t = Math.pow(Math.random(), 0.65);
      const baseR = minR + (maxR - minR) * t;

      const radialAmp = (isSmall ? 10 : 18) + Math.random() * (isSmall ? 18 : 28);
      const radialPhase = rand(0, Math.PI * 2);
      const radialVel = rand(0.6, 1.2);

      const angVel = rand(0.16, 0.34) * (Math.random() < 0.5 ? -1 : 1);
      const drift = randn() * 0.015;

      return {
        // Current draw position (blended between wander and orbit)
        x: rand(0, state.w),
        y: rand(0, state.h),
        // Wander state (free drift when mouse is away)
        wx: rand(0, state.w),
        wy: rand(0, state.h),
        vx: randn() * (isSmall ? 14 : 18),
        vy: randn() * (isSmall ? 14 : 18),
        wanderPhaseX: rand(0, Math.PI * 2),
        wanderPhaseY: rand(0, Math.PI * 2),
        r: rand(1.2, 2.4),
        angle,
        angVel,
        baseR,
        radialAmp,
        radialPhase,
        radialVel,
        drift,
      };
    });
  }

  function clamp(v, lo, hi) {
    return Math.max(lo, Math.min(hi, v));
  }

  function step(t) {
    const dt = clamp((t - state.lastT) / 1000, 0.008, 0.05);
    state.lastT = t;

    // Clear with slight transparency to avoid harshness.
    ctx.clearRect(0, 0, state.w, state.h);

    const mx = state.mouseX;
    const my = state.mouseY;
    const hasMouse = Number.isFinite(mx) && Number.isFinite(my);

    // Smoothly blend between wander and orbit influence.
    const influenceTarget = hasMouse ? 1 : 0;
    // Smaller rates = slower join/spread transitions.
    // Enter (mouse returns) slightly faster than exit (mouse leaves), but both are intentionally slow.
    const influenceRate = hasMouse ? 1.35 : 0.85;
    state.mouseInfluence = lerp(state.mouseInfluence, influenceTarget, 1 - Math.exp(-dt * influenceRate));

    // Orbit center: follow mouse when present, otherwise drift near center.
    state.targetX = hasMouse ? mx : state.w * 0.5;
    state.targetY = hasMouse ? my : state.h * 0.45;
    // Smaller rate = more inertia (cluster lags behind cursor, not "stuck" to it).
    const centerFollowRate = 2.2;
    state.cx = lerp(state.cx, state.targetX, 1 - Math.exp(-dt * centerFollowRate));
    state.cy = lerp(state.cy, state.targetY, 1 - Math.exp(-dt * centerFollowRate));

    const linkDist = Math.min(Math.max(state.w, state.h) * 0.13, 210);
    const linkDist2 = linkDist * linkDist;

    // Wander parameters (active mostly when mouse is away).
    const wanderStrength = (1 - state.mouseInfluence);
    const isSmall = Math.min(state.w, state.h) < 820;
    const maxSpeed = isSmall ? 44 : 58;
    const friction = Math.pow(0.02, dt); // time-step-independent-ish
    const noiseAmp = (isSmall ? 10 : 14) * wanderStrength;
    const repulseDist = (isSmall ? 28 : 34);
    const repulseDist2 = repulseDist * repulseDist;
    const repulseK = (isSmall ? 120 : 170) * wanderStrength;

    // Mild separation/repulsion so nodes "separate" while wandering.
    if (wanderStrength > 0.02) {
      for (let i = 0; i < state.nodes.length; i++) {
        const a = state.nodes[i];
        for (let j = i + 1; j < state.nodes.length; j++) {
          const b = state.nodes[j];
          const dx = a.wx - b.wx;
          const dy = a.wy - b.wy;
          const d2 = dx * dx + dy * dy;
          if (d2 <= 1e-6 || d2 > repulseDist2) continue;
          const d = Math.sqrt(d2);
          const ux = dx / d;
          const uy = dy / d;
          const f = (1 - d / repulseDist) * repulseK * dt;
          a.vx += ux * f;
          a.vy += uy * f;
          b.vx -= ux * f;
          b.vy -= uy * f;
        }
      }
    }

    // Update nodes: wander state + orbit target, then blend.
    for (const n of state.nodes) {
      // Wander: free drift with smooth pseudo-noise acceleration.
      n.wanderPhaseX += dt * (0.7 + Math.abs(n.drift) * 10);
      n.wanderPhaseY += dt * (0.6 + Math.abs(n.drift) * 9);
      n.vx += Math.cos(n.wanderPhaseX + n.angle * 0.2) * noiseAmp * dt;
      n.vy += Math.sin(n.wanderPhaseY + n.angle * 0.2) * noiseAmp * dt;

      // Friction + cap speed.
      n.vx *= friction;
      n.vy *= friction;
      const sp = Math.hypot(n.vx, n.vy);
      if (sp > maxSpeed) {
        n.vx = (n.vx / sp) * maxSpeed;
        n.vy = (n.vy / sp) * maxSpeed;
      }

      n.wx += n.vx * dt;
      n.wy += n.vy * dt;

      // Wrap around edges (keeps motion continuous).
      if (n.wx < -20) n.wx = state.w + 20;
      if (n.wx > state.w + 20) n.wx = -20;
      if (n.wy < -20) n.wy = state.h + 20;
      if (n.wy > state.h + 20) n.wy = -20;

      // Orbit: same as before.
      n.angle += (n.angVel + n.drift) * dt;
      n.radialPhase += n.radialVel * dt;
      const rr = n.baseR + n.radialAmp * Math.sin(n.radialPhase);
      const ox = state.cx + Math.cos(n.angle) * rr;
      const oy = state.cy + Math.sin(n.angle) * rr;

      // Blend: wander when mouse away, orbit around mouse when present.
      const x = lerp(n.wx, ox, state.mouseInfluence);
      const y = lerp(n.wy, oy, state.mouseInfluence);
      n.x = clamp(x, -10, state.w + 10);
      n.y = clamp(y, -10, state.h + 10);
    }

    // Draw links.
    for (let i = 0; i < state.nodes.length; i++) {
      const a = state.nodes[i];
      for (let j = i + 1; j < state.nodes.length; j++) {
        const b = state.nodes[j];
        const dx = a.x - b.x;
        const dy = a.y - b.y;
        const d2 = dx * dx + dy * dy;
        if (d2 > linkDist2) continue;

        const d = Math.sqrt(d2);
        const alpha = (1 - d / linkDist) * 0.9;

        ctx.strokeStyle = hasMouse ? COLORS.lineAccent : COLORS.line;
        ctx.globalAlpha = 0.55 * alpha;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.stroke();
      }
    }

    // Draw nodes on top.
    ctx.globalAlpha = 1;
    for (const n of state.nodes) {
      // soft glow
      ctx.fillStyle = COLORS.nodeGlow;
      ctx.beginPath();
      ctx.arc(n.x, n.y, n.r * 2.2, 0, Math.PI * 2);
      ctx.fill();

      // core
      ctx.fillStyle = COLORS.node;
      ctx.beginPath();
      ctx.arc(n.x, n.y, n.r, 0, Math.PI * 2);
      ctx.fill();
    }

    state.raf = window.requestAnimationFrame(step);
  }

  function onMouseMove(e) {
    const rect = hero.getBoundingClientRect();
    state.mouseX = e.clientX - rect.left;
    state.mouseY = e.clientY - rect.top;
  }

  function onMouseLeave() {
    state.mouseX = null;
    state.mouseY = null;
  }

  function onVisibilityChange() {
    if (document.hidden) {
      if (state.raf) cancelAnimationFrame(state.raf);
      state.raf = null;
      return;
    }
    if (!state.raf) {
      state.lastT = performance.now();
      state.raf = window.requestAnimationFrame(step);
    }
  }

  // Place canvas inside hero so it sits above hero background but below hero content.
  hero.style.position = hero.style.position || "relative";
  hero.style.overflow = "hidden";
  canvas.style.position = "absolute";
  canvas.style.inset = "0";
  canvas.style.pointerEvents = "none";
  canvas.style.zIndex = "0";
  // Move canvas into hero so it overlays the hero background.
  if (canvas.parentElement !== hero) {
    hero.prepend(canvas);
  }

  // Ensure hero content sits above the canvas.
  const heroContainer = hero.querySelector(".container");
  if (heroContainer) {
    heroContainer.style.position = "relative";
    heroContainer.style.zIndex = "1";
  }

  // Init
  sizeCanvas();
  state.cx = state.w * 0.5;
  state.cy = state.h * 0.45;
  makeNodes();

  window.addEventListener("resize", () => {
    sizeCanvas();
    state.cx = state.w * 0.5;
    state.cy = state.h * 0.45;
    makeNodes();
  }, { passive: true });

  hero.addEventListener("mousemove", onMouseMove, { passive: true });
  hero.addEventListener("mouseleave", onMouseLeave, { passive: true });
  document.addEventListener("visibilitychange", onVisibilityChange, { passive: true });

  state.raf = window.requestAnimationFrame(step);
})();

