class IrishRailCommuteCard extends HTMLElement {
  setConfig(config) {
    if (!config) throw new Error("Invalid configuration");
    if (!config.entity) throw new Error("You must define entity");

    this.config = {
      show_last_updated: true,
      show_day_view: true,
      show_recommendation: true,
      show_compact_times: true,
      ...config,
    };
  }

  getCardSize() {
    return 11;
  }

  set hass(hass) {
    this._hass = hass;

    if (!this.content) {
      const card = document.createElement("ha-card");
      card.className = "irish-rail-commute-card";

      const style = document.createElement("style");
      style.textContent = `
        ha-card.irish-rail-commute-card {
          overflow: hidden;
          border-radius: 20px;
          border: 1px solid rgba(255, 255, 255, 0.06);
          transition: box-shadow 180ms ease, border-color 180ms ease, background 180ms ease;
        }

        ha-card.irish-rail-commute-card.confidence-good {
          box-shadow: inset 0 0 0 1px rgba(46, 125, 50, 0.18);
          border-color: rgba(46, 125, 50, 0.22);
        }

        ha-card.irish-rail-commute-card.confidence-warn {
          box-shadow: inset 0 0 0 1px rgba(245, 124, 0, 0.18);
          border-color: rgba(245, 124, 0, 0.22);
        }

        ha-card.irish-rail-commute-card.confidence-bad {
          box-shadow: inset 0 0 0 1px rgba(198, 40, 40, 0.18);
          border-color: rgba(198, 40, 40, 0.22);
        }

        .top-accent {
          height: 4px;
          width: 100%;
          opacity: 0.95;
        }

        .accent-good {
          background: linear-gradient(90deg, rgba(46,125,50,0.75), rgba(46,125,50,0.25));
        }

        .accent-warn {
          background: linear-gradient(90deg, rgba(245,124,0,0.75), rgba(245,124,0,0.25));
        }

        .accent-bad {
          background: linear-gradient(90deg, rgba(198,40,40,0.75), rgba(198,40,40,0.25));
        }

        .wrap {
          padding: 16px;
        }

        .header {
          display: flex;
          justify-content: space-between;
          align-items: flex-start;
          gap: 12px;
          margin-bottom: 14px;
        }

        .route-block {
          min-width: 0;
          flex: 1;
        }

        .route {
          font-size: 1.15rem;
          font-weight: 700;
          line-height: 1.25;
          margin-bottom: 4px;
          word-break: break-word;
        }

        .subtle {
          color: var(--secondary-text-color);
          font-size: 0.92rem;
        }

        .micro {
          color: var(--secondary-text-color);
          font-size: 0.78rem;
          margin-top: 6px;
        }

        .status-badge {
          font-size: 0.78rem;
          font-weight: 700;
          padding: 6px 10px;
          border-radius: 999px;
          white-space: nowrap;
          border: 1px solid transparent;
        }

        .status-normal {
          background: rgba(46, 125, 50, 0.12);
          color: #2e7d32;
          border-color: rgba(46, 125, 50, 0.22);
        }

        .status-warning {
          background: rgba(245, 124, 0, 0.12);
          color: #c77700;
          border-color: rgba(245, 124, 0, 0.22);
        }

        .status-problem {
          background: rgba(198, 40, 40, 0.12);
          color: #c62828;
          border-color: rgba(198, 40, 40, 0.22);
        }

        .hero {
          display: grid;
          grid-template-columns: repeat(2, minmax(0, 1fr));
          gap: 12px;
          margin-bottom: 14px;
        }

        .hero-box {
          background: var(--secondary-background-color);
          border-radius: 16px;
          padding: 14px;
        }

        .hero-label {
          font-size: 0.78rem;
          color: var(--secondary-text-color);
          text-transform: uppercase;
          letter-spacing: 0.04em;
          margin-bottom: 6px;
        }

        .hero-value {
          font-size: 1.7rem;
          font-weight: 800;
          line-height: 1.1;
        }

        .hero-subvalue {
          margin-top: 4px;
          font-size: 0.9rem;
          color: var(--secondary-text-color);
        }

        .route-strip {
          display: grid;
          grid-template-columns: auto 1fr auto;
          align-items: center;
          gap: 10px;
          margin-bottom: 14px;
          padding: 12px 14px;
          border-radius: 16px;
          background: var(--secondary-background-color);
        }

        .route-stop {
          font-size: 0.9rem;
          font-weight: 600;
          min-width: 0;
        }

        .route-line {
          position: relative;
          height: 2px;
          background: rgba(128, 128, 128, 0.35);
          border-radius: 2px;
        }

        .route-line::before,
        .route-line::after {
          content: "";
          position: absolute;
          top: 50%;
          width: 10px;
          height: 10px;
          border-radius: 50%;
          background: var(--primary-color);
          transform: translateY(-50%);
        }

        .route-line::before {
          left: 0;
        }

        .route-line::after {
          right: 0;
        }

        .route-strip.interactive {
          grid-template-columns: 1fr;
          align-items: stretch;
          gap: 12px;
        }

        .route-strip-head {
          display: grid;
          grid-template-columns: auto 1fr auto;
          align-items: center;
          gap: 10px;
        }

        .route-progress {
          position: relative;
          height: 6px;
          background: rgba(128, 128, 128, 0.35);
          border-radius: 999px;
          overflow: hidden;
        }

        .route-progress-fill {
          position: absolute;
          inset: 0 auto 0 0;
          width: 0%;
          background: var(--primary-color);
          border-radius: 999px;
          transition: width 700ms ease;
          opacity: 0.95;
        }

        .route-progress-dot {
          position: absolute;
          top: 50%;
          width: 14px;
          height: 14px;
          border-radius: 50%;
          background: var(--primary-color);
          transform: translate(-50%, -50%);
          box-shadow: 0 0 0 4px rgba(3, 169, 244, 0.18);
          transition: left 700ms ease;
        }

        .route-progress-dot.live {
          animation: irishRailPulse 2.4s ease-in-out infinite;
        }

        .route-strip-meta {
          display: flex;
          justify-content: space-between;
          gap: 10px;
          flex-wrap: wrap;
          font-size: 0.8rem;
          color: var(--secondary-text-color);
        }

        @keyframes irishRailPulse {
          0% { transform: translate(-50%, -50%) scale(0.96); opacity: 0.88; }
          50% { transform: translate(-50%, -50%) scale(1.05); opacity: 1; }
          100% { transform: translate(-50%, -50%) scale(0.96); opacity: 0.88; }
        }

        @keyframes tlPulse {
          0%, 100% { box-shadow: 0 0 0 3px rgba(3,169,244,0.25); transform: scale(1); }
          50%       { box-shadow: 0 0 0 7px rgba(3,169,244,0.08); transform: scale(1.08); }
        }
        @keyframes tlTrainSlide {
          0%   { transform: translateX(0); }
          50%  { transform: translateX(3px); }
          100% { transform: translateX(0); }
        }
        .tl-wrap {
          display: flex;
          flex-direction: column;
          padding: 4px 2px 0;
        }
        .tl-stop {
          display: flex;
          align-items: flex-start;
          gap: 10px;
          position: relative;
          min-height: 36px;
        }
        .tl-gutter {
          display: flex;
          flex-direction: column;
          align-items: center;
          flex-shrink: 0;
          width: 18px;
        }
        .tl-dot {
          width: 12px;
          height: 12px;
          border-radius: 50%;
          border: 2px solid rgba(128,128,128,0.4);
          background: transparent;
          flex-shrink: 0;
          margin-top: 2px;
          transition: background 400ms, border-color 400ms, box-shadow 400ms;
          z-index: 1;
        }
        .tl-stop.passed .tl-dot {
          background: var(--primary-color);
          border-color: var(--primary-color);
          opacity: 0.55;
        }
        .tl-stop.current .tl-dot {
          width: 14px;
          height: 14px;
          background: var(--primary-color);
          border-color: var(--primary-color);
          box-shadow: 0 0 0 3px rgba(3,169,244,0.25);
          animation: tlPulse 2.2s ease-in-out infinite;
          opacity: 1;
        }
        .tl-line {
          flex: 1;
          width: 2px;
          min-height: 20px;
          background: rgba(128,128,128,0.25);
          margin: 1px 0;
          border-radius: 1px;
          transition: background 400ms;
        }
        .tl-stop.passed .tl-line,
        .tl-stop.current .tl-line {
          background: var(--primary-color);
          opacity: 0.45;
        }
        .tl-stop:last-child .tl-line {
          display: none;
        }
        .tl-label {
          flex: 1;
          padding-bottom: 16px;
          padding-top: 0;
        }
        .tl-name {
          font-size: 0.85rem;
          font-weight: 500;
          color: var(--secondary-text-color);
          line-height: 1.3;
          transition: color 300ms, font-weight 300ms;
        }
        .tl-stop.passed .tl-name {
          color: var(--secondary-text-color);
          opacity: 0.65;
        }
        .tl-stop.current .tl-name {
          color: var(--primary-text-color);
          font-weight: 700;
        }
        .tl-stop.next .tl-name {
          color: var(--primary-text-color);
          font-weight: 600;
        }
        .tl-stop:last-child .tl-label {
          padding-bottom: 4px;
        }
        .tl-time {
          font-size: 0.75rem;
          color: var(--secondary-text-color);
          opacity: 0.7;
          margin-top: 1px;
        }
        .tl-stop.current .tl-time {
          opacity: 1;
          color: rgba(3,169,244,0.9);
        }
        .tl-badge {
          display: inline-block;
          font-size: 0.65rem;
          font-weight: 700;
          letter-spacing: 0.05em;
          text-transform: uppercase;
          background: rgba(3,169,244,0.15);
          color: rgba(3,169,244,0.9);
          border: 1px solid rgba(3,169,244,0.3);
          border-radius: 999px;
          padding: 1px 6px;
          margin-left: 6px;
          vertical-align: middle;
          animation: tlTrainSlide 1.8s ease-in-out infinite;
        }

        .recommendation {
          margin-bottom: 14px;
          padding: 12px 14px;
          border-radius: 16px;
          background: var(--secondary-background-color);
          border: 1px solid rgba(255,255,255,0.05);
        }

        .recommendation-title {
          font-size: 0.78rem;
          color: var(--secondary-text-color);
          text-transform: uppercase;
          letter-spacing: 0.04em;
          margin-bottom: 6px;
        }

        .recommendation-main {
          font-size: 1rem;
          font-weight: 700;
          margin-bottom: 4px;
        }

        .recommendation-sub {
          color: var(--secondary-text-color);
          font-size: 0.88rem;
        }

        .chips {
          display: flex;
          flex-wrap: wrap;
          gap: 8px;
          margin-bottom: 14px;
        }

        .chip {
          padding: 8px 10px;
          border-radius: 12px;
          font-size: 0.88rem;
          background: var(--secondary-background-color);
        }

        .chip strong {
          font-weight: 700;
        }

        .section-title {
          font-size: 0.8rem;
          font-weight: 700;
          color: var(--secondary-text-color);
          text-transform: uppercase;
          letter-spacing: 0.04em;
          margin-bottom: 8px;
        }

        .day-view {
          display: flex;
          gap: 8px;
          overflow-x: auto;
          padding-bottom: 2px;
          margin-bottom: 14px;
        }

        .day-chip {
          min-width: 104px;
          padding: 10px 12px;
          border-radius: 14px;
          background: var(--secondary-background-color);
          border: 1px solid rgba(255,255,255,0.05);
          flex: 0 0 auto;
        }

        .day-chip.next {
          outline: 1px solid var(--primary-color);
        }

        .day-time {
          font-size: 0.98rem;
          font-weight: 800;
          margin-bottom: 4px;
        }

        .day-arrival {
          font-size: 0.78rem;
          color: var(--secondary-text-color);
          margin-bottom: 4px;
        }

        .day-status {
          font-size: 0.82rem;
          color: var(--secondary-text-color);
        }

        .day-status.delayed {
          color: #c77700;
        }

        .day-status.problem {
          color: #c62828;
        }

        .trains {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }

        .train-row {
          padding: 12px;
          border-radius: 14px;
          background: var(--secondary-background-color);
          border-left: 4px solid transparent;
        }

        .train-row.next {
          outline: 1px solid var(--primary-color);
        }

        .train-row.good {
          border-left-color: rgba(46, 125, 50, 0.75);
        }

        .train-row.delayed {
          background: rgba(245, 124, 0, 0.08);
          border-left-color: rgba(245, 124, 0, 0.75);
        }

        .train-row.problem {
          background: rgba(198, 40, 40, 0.08);
          border-left-color: rgba(198, 40, 40, 0.75);
        }

        .train-top {
          display: grid;
          grid-template-columns: 88px 1fr auto;
          gap: 10px;
          align-items: start;
        }

        .train-time {
          font-size: 1.08rem;
          font-weight: 800;
          line-height: 1.1;
        }

        .train-main {
          min-width: 0;
        }

        .train-status {
          font-size: 0.92rem;
          font-weight: 700;
          line-height: 1.25;
        }

        .train-detail {
          font-size: 0.82rem;
          color: var(--secondary-text-color);
          margin-top: 3px;
          line-height: 1.35;
        }

        .train-arrival {
          font-size: 0.86rem;
          color: var(--secondary-text-color);
          margin-top: 6px;
          line-height: 1.35;
        }

        .train-side {
          display: flex;
          flex-direction: column;
          align-items: flex-end;
          gap: 6px;
        }

        .delay-pill {
          font-size: 0.8rem;
          font-weight: 700;
          padding: 5px 8px;
          border-radius: 999px;
          white-space: nowrap;
        }

        .delay-ok {
          color: #2e7d32;
          background: rgba(46, 125, 50, 0.10);
        }

        .delay-warn {
          color: #c77700;
          background: rgba(245, 124, 0, 0.12);
        }

        .delay-bad {
          color: #c62828;
          background: rgba(198, 40, 40, 0.12);
        }

        .train-meta {
          display: flex;
          flex-wrap: wrap;
          gap: 10px;
          margin-top: 8px;
          padding-top: 8px;
          border-top: 1px solid rgba(255,255,255,0.05);
          font-size: 0.78rem;
          color: var(--secondary-text-color);
        }

        .progress {
          margin-top: 8px;
        }

        .progress-bar {
          height: 6px;
          border-radius: 999px;
          background: rgba(255,255,255,0.10);
          overflow: hidden;
        }

        .progress-fill {
          height: 100%;
          background: var(--primary-color);
          transition: width 600ms ease;
        }

        .progress-text {
          font-size: 0.78rem;
          color: var(--secondary-text-color);
          margin-top: 4px;
          line-height: 1.35;
        }

        .compact-times {
          margin-top: 14px;
          padding: 12px;
          border-radius: 16px;
          background: var(--secondary-background-color);
          border: 1px solid rgba(255,255,255,0.05);
        }

        .compact-times-grid {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }

        .compact-time-row {
          display: grid;
          grid-template-columns: auto auto auto 1fr;
          gap: 8px;
          align-items: center;
          font-size: 0.92rem;
        }

        .compact-departure,
        .compact-arrival {
          font-weight: 800;
          letter-spacing: 0.01em;
        }

        .compact-arrow {
          color: var(--secondary-text-color);
        }

        .compact-extra {
          justify-self: end;
          font-size: 0.8rem;
          color: var(--secondary-text-color);
        }

        .compact-extra.delayed {
          color: #c77700;
          font-weight: 700;
        }

        .compact-extra.problem {
          color: #c62828;
          font-weight: 700;
        }

        .empty-state {
          background: linear-gradient(
            180deg,
            rgba(255, 255, 255, 0.03),
            rgba(255, 255, 255, 0.015)
          );
          border: 1px solid rgba(255, 255, 255, 0.06);
          border-radius: 18px;
          padding: 16px;
        }

        .empty-title {
          font-size: 1.05rem;
          font-weight: 700;
          margin-bottom: 6px;
        }

        .empty-text {
          color: var(--secondary-text-color);
          font-size: 0.92rem;
          line-height: 1.45;
        }
      `;

      this.content = document.createElement("div");
      this.content.className = "wrap";

      card.appendChild(style);
      card.appendChild(this.content);
      this.appendChild(card);
    }

    this.renderCard();
  }

  _state(entityId) {
    if (!entityId || !this._hass || !this._hass.states || !this._hass.states[entityId]) {
      return null;
    }
    return this._hass.states[entityId];
  }

  _attr(attr, fallback = null) {
    const state = this._state(this.config.entity);
    return state && state.attributes && state.attributes[attr] !== undefined
      ? state.attributes[attr]
      : fallback;
  }

  _mainState(fallback = null) {
    const st = this._state(this.config.entity);
    if (!st) return fallback;
    if (st.state === "unknown" || st.state === "unavailable") return fallback;
    return st.state;
  }

  _escapeHtml(text) {
    return String(text ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  _statusClass(status) {
    const s = String(status || "").toLowerCase();
    if (s.includes("normal") || s.includes("on time")) return "status-normal";
    if (s.includes("minor") || s.includes("delay") || s.includes("warning")) {
      return "status-warning";
    }
    return "status-problem";
  }

  _confidenceClass(status) {
    const s = String(status || "").toLowerCase();
    if (s.includes("normal") || s.includes("on time")) return "good";
    if (s.includes("minor") || s.includes("delay")) return "warn";
    return "bad";
  }

  _delayClass(delay) {
    const n = Number(delay);
    if (Number.isNaN(n) || n <= 0) return "delay-ok";
    if (n < 10) return "delay-warn";
    return "delay-bad";
  }

  _rowClass(train) {
    if (train.cancelled) return "problem";
    const delayNum = Number(train.arrivalDelay ?? train.departureDelay ?? train.delay ?? 0);
    if (!Number.isNaN(delayNum) && delayNum > 0) return "delayed";
    return "good";
  }

  _formatLastUpdated(value) {
    if (!value) return null;
    const dt = new Date(value);
    if (Number.isNaN(dt.getTime())) return null;
    return dt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  }

  _isNoTrainText(value) {
    const text = String(value ?? "").trim().toLowerCase();
    return (
      text === "no trains" ||
      text === "no more trains" ||
      text === "no upcoming train" ||
      text === "—" ||
      text === "-" ||
      text === ""
    );
  }

  _normalizeStatus(text, isCancelled = false, delay = 0) {
    if (isCancelled) return "Cancelled";
    const s = String(text || "").trim().toLowerCase();

    if (s === "cancelled" || s === "canceled") return "Cancelled";
    if (Number(delay) > 0) return "Delayed";
    if (s === "on time" || s === "on_time" || s === "normal" || s === "ontime") {
      return "On Time";
    }
    if (s === "delayed" || s === "delay") return "Delayed";
    if (!s) return "No data";
    return String(text);
  }

  _formatArrivalText(train) {
    if (train.cancelled) return "Arrival cancelled";

    const scheduled = train.scheduledArrival;
    const expected = train.expectedArrival || train.arrival;

    if (scheduled && expected && scheduled !== expected) {
      return `Arr ${scheduled} → ${expected}`;
    }

    if (expected || scheduled) {
      return `Arrives ${expected || scheduled}`;
    }

    return "Arrival time unavailable";
  }

  _detailText(train, idx) {
    if (train.cancelled) {
      return idx === 0 ? "Next scheduled service is cancelled" : "Service cancelled";
    }

    const arrivalDelay = Number(train.arrivalDelay ?? 0);
    const departureDelay = Number(train.departureDelay ?? 0);

    if (!Number.isNaN(arrivalDelay) && arrivalDelay > 0) {
      return `Arrival running ${arrivalDelay} min late`;
    }

    if (!Number.isNaN(departureDelay) && departureDelay > 0) {
      return `Departure running ${departureDelay} min late`;
    }

    return idx === 0 ? "Next departure" : "Upcoming service";
  }

  _compactExtra(train) {
    if (train.cancelled) {
      return { text: "Cancelled", cls: "problem" };
    }

    const delayNum = Number(train.arrivalDelay ?? train.departureDelay ?? train.delay ?? 0);
    if (!Number.isNaN(delayNum) && delayNum > 0) {
      return { text: `+${delayNum} min`, cls: "delayed" };
    }

    return { text: "On Time", cls: "" };
  }

  _smoothedProgress(train) {
    const base = Number(train.progress ?? 0);
    if (Number.isNaN(base)) return 0;
    if (train.cancelled) return 0;
    if (!train.stopCount || train.stopCount <= 1) return Math.max(0, Math.min(100, base));

    // Give a little visual motion after departure and before the next stop
    // is officially marked passed.
    if (base > 0 && base < 100) {
      const segmentSize = 100 / Math.max(train.stopCount - 1, 1);
      const eased = Math.min(base + Math.max(2, Math.round(segmentSize * 0.18)), 98);
      return Math.max(0, Math.min(100, eased));
    }

    return Math.max(0, Math.min(100, base));
  }

  _progressText(train) {
    const bits = [];
    if (train.stopsCompleted === 0 && train.nextStop) {
      bits.push("Departing");
    } else if (train.currentStop) {
      bits.push(`Passed ${train.currentStop}`);
    }

    if (train.nextStop) {
      bits.push(`Next: ${train.nextStop}`);
    }

    if (train.stopCount > 0) {
      bits.push(`${train.stopsCompleted}/${train.stopCount} stops`);
    }

    return bits.join(" • ");
  }

  _formatStopEta(stop) {
    if (!stop) return "—";
    return stop.expected_arrival || stop.expected_departure || stop.scheduled_arrival || stop.scheduled_departure || "—";
  }

  _routeData(train) {
    const stops = Array.isArray(train?.routeStops) ? train.routeStops : [];
    const stopCount = Number(train?.stopCount ?? 0);
    const progress = this._smoothedProgress(train);

    return {
      stops,
      stopCount,
      progress,
      currentStop: train?.currentStop || null,
      nextStop: train?.nextStop || null,
    };
  }

  _featuredRouteTrain(upcoming, active) {
    if (Array.isArray(active) && active.length) {
      const activeUsable = active.find((train) => {
        return !train?.cancelled && Array.isArray(train?.routeStops) && train.routeStops.length > 1;
      });
      if (activeUsable) return activeUsable;
    }

    if (Array.isArray(upcoming) && upcoming.length) {
      const nextUsable = upcoming.find((train) => {
        return !train?.cancelled && Array.isArray(train?.routeStops) && train.routeStops.length > 1;
      });
      return nextUsable || upcoming[0];
    }

    return null;
  }

  _routeStripHtml(train, originName, destinationName) {
    const data = this._routeData(train || {});
    const stops = data.stops;
    const progress = data.progress;
    const currentStop = data.currentStop;
    const nextStop = data.nextStop;

    if (!train || !stops.length) {
      return `
        <div class="route-strip">
          <div class="route-stop">${this._escapeHtml(originName)}</div>
          <div class="route-line"></div>
          <div class="route-stop">${this._escapeHtml(destinationName)}</div>
        </div>
      `;
    }

    const metaLeft = currentStop ? `Current: ${currentStop}` : (nextStop ? "Planned route" : "Route loaded");
    const metaRight = nextStop ? `Next: ${nextStop}` : "Approaching destination";
    const dotClass = progress > 0 && progress < 100 ? "route-progress-dot live" : "route-progress-dot";

    const timelineHtml = stops.map((stop, idx) => {
      const name = stop?.name || stop?.code || `Stop ${idx + 1}`;
      const passed = !!stop?.passed;
      const isCurrent = !!(currentStop && name === currentStop);
      const isNext = !!(nextStop && name === nextStop && !isCurrent);
      const cls = ["tl-stop", passed ? "passed" : "", isCurrent ? "current" : "", isNext ? "next" : ""].filter(Boolean).join(" ");
      const eta = this._formatStopEta(stop);
      const timeHtml = eta ? `<div class="tl-time">${this._escapeHtml(eta)}</div>` : "";
      const badge = isCurrent ? `<span class="tl-badge">&#9654; live</span>` : (isNext ? `<span class="tl-badge" style="background:rgba(255,255,255,0.06);color:var(--secondary-text-color);border-color:rgba(255,255,255,0.12);animation:none">next</span>` : "");
      return `
        <div class="${cls}">
          <div class="tl-gutter">
            <div class="tl-dot"></div>
            <div class="tl-line"></div>
          </div>
          <div class="tl-label">
            <div class="tl-name">${this._escapeHtml(name)}${badge}</div>
            ${timeHtml}
          </div>
        </div>`;
    }).join("");

    return `
      <div class="route-strip interactive">
        <div class="route-strip-head">
          <div class="route-stop">${this._escapeHtml(originName)}</div>
          <div class="route-progress">
            <div class="route-progress-fill" style="width: ${progress}%"></div>
            <div class="${dotClass}" style="left: ${progress}%"></div>
          </div>
          <div class="route-stop">${this._escapeHtml(destinationName)}</div>
        </div>
        <div class="route-strip-meta">
          <span>${this._escapeHtml(metaLeft)}</span>
          <span>${this._escapeHtml(metaRight)}</span>
        </div>
        <div class="tl-wrap">
          ${timelineHtml}
        </div>
      </div>
    `;
  }

  _recommendation(countdown, status, hasLiveTrains) {
    if (!hasLiveTrains) {
      return {
        title: "Commute guidance",
        main: "No departure available",
        sub: "No live recommendation is available right now.",
      };
    }

    const s = String(status || "").toLowerCase();
    const c = String(countdown || "").toLowerCase();

    let minutes = null;
    const m = c.match(/^(\d+)\s*min$/);
    if (m) minutes = Number(m[1]);

    if (s.includes("severe") || s.includes("critical") || s.includes("major")) {
      return {
        title: "Commute guidance",
        main: "Watch service disruption",
        sub: "Allow extra buffer time before leaving.",
      };
    }

    if (minutes === null) {
      return {
        title: "Commute guidance",
        main: "Check the next departure",
        sub: "Live timing is available, but countdown confidence is limited.",
      };
    }

    if (minutes <= 5) {
      return {
        title: "Commute guidance",
        main: "Leave now",
        sub: "Your next train is approaching soon.",
      };
    }

    if (minutes <= 12) {
      return {
        title: "Commute guidance",
        main: "Leave soon",
        sub: "You have a short window before departure.",
      };
    }

    if (s.includes("minor") || s.includes("delay")) {
      return {
        title: "Commute guidance",
        main: "Comfortable, but watch delays",
        sub: "There is still time, though service reliability is slightly reduced.",
      };
    }

    return {
      title: "Commute guidance",
      main: "Comfortable",
      sub: "Service looks healthy and you still have time before departure.",
    };
  }

  renderCard() {
    if (!this.content || !this._hass) return;

    const card = this.querySelector("ha-card");
    const originName = this._attr("origin_name", this._attr("origin", "Origin"));
    const destinationName = this._attr("destination_name", this._attr("destination", "Destination"));
    const routeTitle =
      this._attr("route_name") ||
      `${originName || "Origin"} → ${destinationName || "Destination"}`;

    const status = this._attr("status") || this._attr("overall_status") || "Unknown";
    const summary = this._mainState("") || this._attr("summary", "");
    const countdown = this._attr("countdown", "—");
    const nextTrain = this._attr("next_train_time", "—");
    const delayedCount = this._attr("delayed_count", 0);
    const cancelledCount = this._attr("cancelled_count", 0);
    const lastUpdated = this._formatLastUpdated(this._attr("last_updated"));

    const upcomingTrainsRaw = this._attr("upcoming_trains", []);
    const activeTrainsRaw = this._attr("active_trains", []);
    const normalizeTrainArray = (raw) =>
      Array.isArray(raw)
        ? raw
            .map((t) => {
              const departure =
                t.departure_time ||
                t.departure ||
                t.expected_departure ||
                t.scheduled_departure ||
                "—";

              const arrival =
                t.arrival_time ||
                t.arrival ||
                t.expected_arrival ||
                t.scheduled_arrival ||
                null;

              const scheduledArrival = t.scheduled_arrival || null;
              const expectedArrival = t.expected_arrival || t.estimated_arrival || arrival;
              const delay = t.delay_minutes ?? 0;
              const arrivalDelay = t.arrival_delay_minutes ?? delay ?? 0;
              const departureDelay = t.departure_delay_minutes ?? 0;
              const cancelled = !!t.is_cancelled;

              return {
                time: departure,
                arrival,
                scheduledArrival,
                expectedArrival,
                status: this._normalizeStatus(t.status, cancelled, arrivalDelay || departureDelay),
                delay,
                arrivalDelay,
                departureDelay,
                cancelled,
                platform: t.platform || null,
                destination: t.destination || null,
                progress: t.progress_percent ?? 0,
                currentStop: t.current_stop || null,
                nextStop: t.next_stop || null,
                stopsCompleted: t.stops_completed ?? 0,
                stopCount: t.segment_stop_count ?? 0,
                routeStops: Array.isArray(t.route_stops) ? t.route_stops : [],
              };
            })
            .filter((t) => !this._isNoTrainText(t.time))
        : [];

    const liveTrains = normalizeTrainArray(upcomingTrainsRaw);
    const activeTrains = normalizeTrainArray(activeTrainsRaw);

    const hasLiveTrains = liveTrains.length > 0;
    const hasActiveTrains = activeTrains.length > 0;

    const noTrainMode =
      !hasLiveTrains &&
      this._isNoTrainText(nextTrain) &&
      this._isNoTrainText(countdown);

    const countdownDisplay = noTrainMode ? "No more trains" : countdown;
    const nextTrainDisplay = noTrainMode ? "—" : nextTrain;

    const summaryText = noTrainMode
      ? "No more departures in the current time window."
      : (summary || "No live service information available.");

    const recommendation = this._recommendation(countdownDisplay, status, hasLiveTrains);
    const confidence = this._confidenceClass(status);

    if (card) {
      card.classList.remove("confidence-good", "confidence-warn", "confidence-bad");
      card.classList.add(`confidence-${confidence}`);
    }

    const chipsHtml = hasLiveTrains
      ? `
        <div class="chips">
          <div class="chip"><strong>${this._escapeHtml(delayedCount)}</strong> delayed</div>
          <div class="chip"><strong>${this._escapeHtml(cancelledCount)}</strong> cancelled</div>
        </div>
      `
      : "";

    const recommendationHtml = this.config.show_recommendation
      ? `
        <div class="recommendation">
          <div class="recommendation-title">${this._escapeHtml(recommendation.title)}</div>
          <div class="recommendation-main">${this._escapeHtml(recommendation.main)}</div>
          <div class="recommendation-sub">${this._escapeHtml(recommendation.sub)}</div>
        </div>
      `
      : "";

    const dayViewHtml =
      this.config.show_day_view && hasLiveTrains
        ? `
          <div class="section-title">Today</div>
          <div class="day-view">
            ${liveTrains
              .map((train, idx) => {
                const delayNum = Number(train.arrivalDelay ?? train.departureDelay ?? train.delay ?? 0);
                const statusClass = train.cancelled
                  ? "problem"
                  : delayNum > 0
                    ? "delayed"
                    : "";
                const label = train.cancelled
                  ? "Cancelled"
                  : delayNum > 0
                    ? `+${delayNum} min`
                    : "On Time";

                return `
                  <div class="day-chip ${idx === 0 ? "next" : ""}">
                    <div class="day-time">${this._escapeHtml(train.time)}</div>
                    <div class="day-arrival">${this._escapeHtml(train.arrival ? `Arr ${train.arrival}` : "Arr —")}</div>
                    <div class="day-status ${statusClass}">${this._escapeHtml(label)}</div>
                  </div>
                `;
              })
              .join("")}
          </div>
        `
        : "";

    const departuresTitle = hasLiveTrains ? "Upcoming departures" : "Service status";

    const activeTrainsHtml = hasActiveTrains
      ? `
          <div class="section-title">Live on route</div>
          <div class="trains">
            ${activeTrains
              .map((train, idx) => {
                const delayNum = Number(train.arrivalDelay ?? train.departureDelay ?? train.delay ?? 0);
                const delayText = train.cancelled
                  ? "Cancelled"
                  : Number.isNaN(delayNum) || delayNum <= 0
                    ? "On Time"
                    : `+${delayNum} min`;

                const metaBits = [];
                if (train.platform) metaBits.push(`Platform ${train.platform}`);
                if (train.destination) metaBits.push(train.destination);

                return `
                  <div class="train-row ${idx === 0 ? "next" : ""} ${this._rowClass(train)}">
                    <div class="train-top">
                      <div class="train-time">${this._escapeHtml(train.time)}</div>
                      <div class="train-main">
                        <div class="train-status">${this._escapeHtml(train.status)}</div>
                        <div class="train-detail">${this._escapeHtml(this._detailText(train, idx))}</div>
                        <div class="train-arrival">${this._escapeHtml(this._formatArrivalText(train))}</div>
                        ${
                          train.stopCount > 0
                            ? `
                              <div class="progress">
                                <div class="progress-bar">
                                  <div class="progress-fill" style="width: ${this._smoothedProgress(train)}%"></div>
                                </div>
                                <div class="progress-text">${this._escapeHtml(this._progressText(train))}</div>
                              </div>
                            `
                            : ""
                        }
                      </div>
                      <div class="train-side">
                        <div class="delay-pill ${this._delayClass(delayNum)}">${this._escapeHtml(delayText)}</div>
                      </div>
                    </div>
                    ${
                      metaBits.length
                        ? `
                          <div class="train-meta">
                            ${metaBits
                              .map((bit) => `<span>${this._escapeHtml(bit)}</span>`)
                              .join("")}
                          </div>
                        `
                        : ""
                    }
                  </div>
                `;
              })
              .join("")}
          </div>
        `
      : "";

    const trainsHtml = hasLiveTrains
      ? liveTrains
          .map((train, idx) => {
            const delayNum = Number(train.arrivalDelay ?? train.departureDelay ?? train.delay ?? 0);
            const delayText = train.cancelled
              ? "Cancelled"
              : Number.isNaN(delayNum) || delayNum <= 0
                ? "On Time"
                : `+${delayNum} min`;

            const metaBits = [];
            if (train.platform) metaBits.push(`Platform ${train.platform}`);
            if (train.destination) metaBits.push(train.destination);

            return `
              <div class="train-row ${idx === 0 ? "next" : ""} ${this._rowClass(train)}">
                <div class="train-top">
                  <div class="train-time">${this._escapeHtml(train.time)}</div>
                  <div class="train-main">
                    <div class="train-status">${this._escapeHtml(train.status)}</div>
                    <div class="train-detail">${this._escapeHtml(this._detailText(train, idx))}</div>
                    <div class="train-arrival">${this._escapeHtml(this._formatArrivalText(train))}</div>
                    ${
                      train.stopCount > 0
                        ? `
                          <div class="progress">
                            <div class="progress-bar">
                              <div class="progress-fill" style="width: ${this._smoothedProgress(train)}%"></div>
                            </div>
                            <div class="progress-text">${this._escapeHtml(this._progressText(train))}</div>
                          </div>
                        `
                        : ""
                    }
                  </div>
                  <div class="train-side">
                    <div class="delay-pill ${this._delayClass(delayNum)}">${this._escapeHtml(delayText)}</div>
                  </div>
                </div>
                ${
                  metaBits.length
                    ? `
                      <div class="train-meta">
                        ${metaBits
                          .map((bit) => `<span>${this._escapeHtml(bit)}</span>`)
                          .join("")}
                      </div>
                    `
                    : ""
                }
              </div>
            `;
          })
          .join("")
      : `
        <div class="empty-state">
          <div class="empty-title">No upcoming trains</div>
          <div class="empty-text">
            No more departures were found for ${this._escapeHtml(routeTitle)}
            in the current time window.
          </div>
        </div>
      `;

    const compactTimesHtml =
      this.config.show_compact_times && hasLiveTrains
        ? `
          <div class="compact-times">
            <div class="section-title">Departure → arrival</div>
            <div class="compact-times-grid">
              ${liveTrains
                .map((train) => {
                  const extra = this._compactExtra(train);
                  return `
                    <div class="compact-time-row">
                      <div class="compact-departure">${this._escapeHtml(train.time || "—")}</div>
                      <div class="compact-arrow">→</div>
                      <div class="compact-arrival">${this._escapeHtml(train.arrival || "—")}</div>
                      <div class="compact-extra ${extra.cls}">${this._escapeHtml(
                        train.stopCount > 0
                          ? (train.nextStop ? `ETA ${train.nextStop}` : `${train.stopsCompleted}/${train.stopCount} stops`)
                          : extra.text
                      )}</div>
                    </div>
                  `;
                })
                .join("")}
            </div>
          </div>
        `
        : "";

    this.content.innerHTML = `
      <div class="top-accent accent-${confidence}"></div>
      <div class="header">
        <div class="route-block">
          <div class="route">${this._escapeHtml(routeTitle)}</div>
          <div class="subtle">${this._escapeHtml(summaryText)}</div>
          ${this.config.show_last_updated && lastUpdated ? `<div class="micro">Updated ${this._escapeHtml(lastUpdated)}</div>` : ""}
        </div>
        <div class="status-badge ${this._statusClass(status)}">${this._escapeHtml(status)}</div>
      </div>

      <div class="hero">
        <div class="hero-box">
          <div class="hero-label">Countdown</div>
          <div class="hero-value">${this._escapeHtml(countdownDisplay)}</div>
          <div class="hero-subvalue">
            ${noTrainMode ? "No departure currently available" : "to departure"}
          </div>
        </div>
        <div class="hero-box">
          <div class="hero-label">Next train</div>
          <div class="hero-value">${this._escapeHtml(nextTrainDisplay)}</div>
          <div class="hero-subvalue">
            ${noTrainMode ? "Check again later" : "Scheduled departure"}
          </div>
        </div>
      </div>

      ${this._routeStripHtml(this._featuredRouteTrain(liveTrains, activeTrains), originName, destinationName)}

      ${recommendationHtml}
      ${chipsHtml}
      ${dayViewHtml}
      ${activeTrainsHtml}

      <div class="section-title">${this._escapeHtml(departuresTitle)}</div>
      <div class="trains">
        ${trainsHtml}
      </div>

      ${compactTimesHtml}
    `;
  }
}

if (!customElements.get("irish-rail-commute-card")) {
  customElements.define("irish-rail-commute-card", IrishRailCommuteCard);
}

window.customCards = window.customCards || [];
window.customCards.push({
  type: "irish-rail-commute-card",
  name: "Irish Rail Commute Card",
  description: "Commute card for Irish Rail departures",
});